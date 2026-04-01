from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Union

from app.core.logging import get_logger
from app.geotif_converter.raster_io import get_raster_metadata, read_geotiff

from app.climate_indices.models import (
    AssetIngestRequest,
    AssetIngestResult,
    AssetStorage,
    AssetPersistenceResult,
    AssetRecord,
    RasterSummary,
    StorageInfo,
)
from app.climate_indices.repository import AssetRepository
from app.climate_indices.storage import GCSBlobStore

PathLike = Union[str, Path]
BytesLike = Union[bytes, bytearray, memoryview]
GeoTiffSource = Union[PathLike, BytesLike, BinaryIO]

logger = get_logger(__name__)


def ingest_upload(source: GeoTiffSource, request: AssetIngestRequest) -> AssetIngestResult:
    """Load a GeoTIFF with existing geotif_converter utilities and return a serialisable summary.

    This wires the domain layer to the shared raster primitives without persisting anything yet.
    """
    raster = read_geotiff(source, masked=True, load=False, target_crs="EPSG:4326")
    raw_meta = get_raster_metadata(raster)

    summary = RasterSummary.from_raster_metadata(raw_meta)
    logger.info(
        "Ingested GeoTIFF for index %s with bounds %s and resolution %s",
        request.index_type,
        summary.bounds,
        summary.resolution,
    )

    return AssetIngestResult(asset=request, raster=summary)


def persist_climate_index(
    payload: BytesLike,
    request: AssetIngestRequest,
    *,
    blob_store: GCSBlobStore,
    repo: AssetRepository,
) -> AssetPersistenceResult:
    """
    Persist an uploaded GeoTIFF: store blob, record metadata in Mongo, and return identifiers.

    If the request includes a raster_id and an asset with the same raster_id exists,
    it will be replaced. Otherwise, a new asset is created.
    """
    ingest = ingest_upload(payload, request)

    checksum = hashlib.sha256(payload).hexdigest()
    raw_uri = blob_store.save_bytes(payload, filename=request.filename, content_type="image/tiff")
    cog_uri = blob_store.save_bytes(payload, filename=f"{Path(request.filename or 'upload').stem}.cog.tif", content_type="image/tiff")
    storage = AssetStorage(
        raw=StorageInfo(
            kind=getattr(blob_store, "kind", "unknown"),
            uri=raw_uri,
            checksum=checksum,
            size_bytes=len(payload),
        ),
        cog=StorageInfo(
            kind=getattr(blob_store, "kind", "unknown"),
            uri=cog_uri,
            checksum=checksum,
            size_bytes=len(payload),
        ),
    )

    record = AssetRecord(
        raster_id=request.raster_id,
        index_type=request.index_type,
        time_range=request.time_range,
        units=request.units,
        filename=request.filename,
        storage=storage,
        raster=ingest.raster,
    )

    # Use upsert to replace existing record if raster_id matches
    asset_id, was_replaced = repo.upsert_asset(record)

    if was_replaced:
        logger.info("Replaced existing asset %s with raster_id %s", asset_id, request.raster_id)

    return AssetPersistenceResult(
        asset=request,
        asset_id=asset_id,
        raster_id=request.raster_id,
        storage=storage,
        raster=ingest.raster,
        replaced=was_replaced
    )
