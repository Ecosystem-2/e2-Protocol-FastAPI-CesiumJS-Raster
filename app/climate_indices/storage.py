from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)


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
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        if not payload:
            raise ValueError("Cannot store empty payload.")

        name = filename or f"upload-{uuid.uuid4().hex}.tif"
        if self.prefix:
            name = f"{self.prefix}/{name}"

        blob = self._bucket.blob(name)
        blob.upload_from_string(payload, content_type=content_type or "image/tiff")
        uri = f"gs://{self.bucket_name}/{name}"
        logger.info("Stored blob in GCS at %s (%s bytes)", uri, len(payload))
        return uri
