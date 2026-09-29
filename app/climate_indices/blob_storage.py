# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Google Cloud Storage service for raster blob storage."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import pathlib
import uuid
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def _env_flag_enabled(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_vsigs_uri(uri: str) -> str:
    """Convert gs://bucket/path to GDAL's /vsigs/bucket/path URI."""
    if uri.startswith("gs://"):
        return "/vsigs/" + uri.removeprefix("gs://")
    return uri


def _clear_gdal_vsi_cache() -> None:
    """Clear GDAL's VSI curl cache so newly uploaded GCS files are immediately accessible.

    GDAL caches GCS directory listings and negative results (file-not-found) via its
    /vsigs/ virtual filesystem layer. Without clearing this cache, a file uploaded to
    GCS after the process started will appear missing to GDAL/rio-tiler until the
    cache expires or the container restarts.

    Strategy:
      1. System-installed GDAL (Linux/Docker with libgdal-dev installed via apt).
      2. rasterio's bundled GDAL dylib/so (macOS .dylibs/, Linux .libs/).

    Both are attempted unconditionally — in Docker the system GDAL and rasterio's
    bundled GDAL are separate in-process library instances with independent caches.
    COGReader uses rasterio's bundled instance, so clearing only the system GDAL is
    not sufficient.
    """
    cleared = False

    # 1. System GDAL (Linux/Docker)
    lib_name = ctypes.util.find_library("gdal")
    if lib_name:
        try:
            lib = ctypes.CDLL(lib_name)
            lib.VSICurlClearCache.restype = None
            lib.VSICurlClearCache()
            logger.debug("Cleared GDAL VSI cache via system library: %s", lib_name)
            cleared = True
        except OSError as exc:
            logger.debug("Could not clear GDAL VSI cache via system library %s: %s", lib_name, exc)

    # 2. rasterio's bundled GDAL (macOS .dylibs/, Linux .libs/) — always try even if
    # system GDAL succeeded, as COGReader uses rasterio's own libgdal instance
    try:
        import rasterio  # type: ignore
        rasterio_dir = pathlib.Path(rasterio.__file__).parent
        for dylib_dir in [rasterio_dir / ".dylibs", rasterio_dir / ".libs"]:
            if dylib_dir.exists():
                gdal_libs = [f for f in dylib_dir.iterdir() if "libgdal" in f.name.lower()]
                if gdal_libs:
                    lib = ctypes.CDLL(str(gdal_libs[0]))
                    lib.VSICurlClearCache.restype = None
                    lib.VSICurlClearCache()
                    logger.debug("Cleared GDAL VSI cache via rasterio bundled library: %s", gdal_libs[0])
                    cleared = True
    except Exception as exc:
        logger.debug("Could not clear GDAL VSI cache via rasterio bundled library: %s", exc)

    if not cleared:
        logger.warning("Could not clear GDAL VSI cache: no suitable GDAL library found")


def _log_rasterio_visibility(uri: str) -> None:
    """Log whether rasterio/GDAL can see a freshly uploaded object in this process."""
    if not _env_flag_enabled("GDAL_VERIFY_AFTER_UPLOAD"):
        return

    try:
        import rasterio  # type: ignore

        vsi_uri = _to_vsigs_uri(uri)
        logger.info(
            "GDAL/rasterio visibility probe starting: uri=%s vsi_uri=%s "
            "rasterio=%s gdal_version=%s GDAL_DISABLE_READDIR_ON_OPEN=%s VSI_CACHE=%s",
            uri,
            vsi_uri,
            getattr(rasterio, "__file__", "unknown"),
            getattr(rasterio, "__gdal_version__", "unknown"),
            os.getenv("GDAL_DISABLE_READDIR_ON_OPEN"),
            os.getenv("VSI_CACHE"),
        )
        with rasterio.open(vsi_uri) as dataset:
            logger.info(
                "GDAL/rasterio visibility probe succeeded: uri=%s driver=%s size=%sx%s count=%s crs=%s",
                uri,
                dataset.driver,
                dataset.width,
                dataset.height,
                dataset.count,
                dataset.crs,
            )
    except Exception as exc:
        logger.warning("GDAL/rasterio visibility probe failed for %s: %s", uri, exc)


class GCSBlobStore:
    """Store blobs in Google Cloud Storage."""

    kind = "gcs"

    def __init__(self, bucket: str, prefix: str = ""):
        self.bucket_name = bucket
        self.prefix = prefix.strip("/")
        self._client = self._get_client()
        self._bucket = self._client.bucket(bucket)

    @staticmethod
    def _get_client():
        try:
            from google.cloud import storage  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise ImportError("google-cloud-storage is required for GCSBlobStore") from exc
        return storage.Client()

    def save_bytes(
        self,
        payload: bytes,
        *,
        blob_id: Optional[str] = None,
        suffix: str = ".tif",
        content_type: Optional[str] = None,
    ) -> str:
        """Save bytes to GCS using blob_id (rasterID) for naming.

        Args:
            payload: The file content to store.
            blob_id: The rasterID (UUID) to use as the filename. If not provided,
                     a random UUID is generated.
            suffix: File extension to append (default: .tif, use .cog.tif for COGs).
            content_type: MIME type for the blob.

        Returns:
            The GCS URI (gs://bucket/prefix/blob_id.suffix).
        """
        if not payload:
            raise ValueError("Cannot store empty payload.")

        # Use blob_id (rasterID) for naming, fallback to random UUID
        file_id = blob_id or uuid.uuid4().hex
        name = f"{file_id}{suffix}"
        if self.prefix:
            name = f"{self.prefix}/{name}"

        blob = self._bucket.blob(name)

        # Check if blob exists and delete it first to avoid duplicates
        if blob.exists():
            logger.info("Replacing existing blob at gs://%s/%s", self.bucket_name, name)
            blob.delete()
            # Recreate blob reference after deletion
            blob = self._bucket.blob(name)

        blob.upload_from_string(payload, content_type=content_type or "image/tiff")
        uri = f"gs://{self.bucket_name}/{name}"
        logger.info("Stored blob in GCS at %s (%s bytes)", uri, len(payload))
        try:
            blob.reload()
            logger.info(
                "Verified GCS blob after upload: uri=%s exists=true size=%s generation=%s updated=%s",
                uri,
                blob.size,
                blob.generation,
                blob.updated,
            )
        except Exception as exc:
            logger.warning("Could not verify GCS blob metadata after upload: uri=%s error=%s", uri, exc)
        _clear_gdal_vsi_cache()
        _log_rasterio_visibility(uri)
        return uri

    def delete_blob(self, uri: str) -> bool:
        """Delete a blob from GCS by its URI.

        Args:
            uri: The GCS URI (gs://bucket/path/to/blob).

        Returns:
            True if the blob was deleted, False if it didn't exist.
        """
        # Parse URI to get blob name
        if not uri.startswith(f"gs://{self.bucket_name}/"):
            logger.warning("URI %s does not belong to bucket %s", uri, self.bucket_name)
            return False

        blob_name = uri.replace(f"gs://{self.bucket_name}/", "")
        blob = self._bucket.blob(blob_name)

        if not blob.exists():
            logger.warning("Blob does not exist: %s", uri)
            return False

        blob.delete()
        logger.info("Deleted blob from GCS: %s", uri)
        _clear_gdal_vsi_cache()
        return True

    def delete_blobs_by_id(self, blob_id: str) -> int:
        """Delete all blobs matching a blob_id (rasterID).

        Deletes both .tif and .cog.tif variants.

        Args:
            blob_id: The rasterID (UUID) used to name the blobs.

        Returns:
            Number of blobs deleted.
        """
        deleted_count = 0
        suffixes = [".tif", ".cog.tif"]

        for suffix in suffixes:
            name = f"{blob_id}{suffix}"
            if self.prefix:
                name = f"{self.prefix}/{name}"

            blob = self._bucket.blob(name)
            if blob.exists():
                blob.delete()
                logger.info("Deleted blob gs://%s/%s", self.bucket_name, name)
                deleted_count += 1

        if deleted_count:
            _clear_gdal_vsi_cache()
        return deleted_count
