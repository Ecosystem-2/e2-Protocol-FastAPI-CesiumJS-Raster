"""GeoTIFF ingestion endpoints: validate, upload, and persist climate index assets."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Optional, Tuple
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.climate_indices.models import AssetIngestRequest, AssetIngestResult, TimeRange
from app.climate_indices.service import ingest_upload, persist_climate_index
from app.climate_indices.repository import AssetRepository
from app.climate_indices.storage import GCSBlobStore
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

ACCEPTED_CONTENT_TYPES: Final[set[str]] = {
    "image/tiff",
    "image/tif",
    "image/geotiff",
    "application/octet-stream",
}


# ============================================================================
# Helper Functions
# ============================================================================


def _validate_upload(file: UploadFile, payload: bytes) -> None:
    """Validate uploaded file content type and size."""
    if file.content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )


def _initialise_storage() -> Tuple[GCSBlobStore, AssetRepository]:
    """Initialise GCS storage and asset repository."""
    bucket = os.getenv("GCS_BUCKET")
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS_BUCKET env var is required for storage.",
        )
    
    prefix = os.getenv("GCS_PREFIX", "").strip("/")
    blob_store = GCSBlobStore(bucket=bucket, prefix=prefix)
    repo = AssetRepository()
    return blob_store, repo


# ============================================================================
# Ingestion Endpoints
# ============================================================================


@router.post(
    "/ingest",
    response_model=AssetIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a GeoTIFF climate index and return metadata only.",
    description="Uses existing geotif_converter utilities; does not persist yet.",
)
async def ingest_climate_index(
    file: UploadFile = File(...),
    index_type: str = Form(..., description="Climate index name, e.g., humid-heat-stress."),
    time_start: Optional[datetime] = Form(None, description="Start timestamp for the asset."),
    time_end: Optional[datetime] = Form(None, description="End timestamp for the asset."),
    units: Optional[str] = Form(None, description="Units of the raster values."),
) -> AssetIngestResult:
    """Ingest GeoTIFF and return metadata without persisting to storage."""
    payload = await file.read()
    _validate_upload(file, payload)

    request = AssetIngestRequest(
        index_type=index_type,
        time_range=TimeRange(start=time_start, end=time_end),
        units=units,
        filename=file.filename,
    )

    return ingest_upload(payload, request)


@router.post(
    "/ingest/store",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and persist a GeoTIFF climate index.",
    description="Stores the raw GeoTIFF and COG to Google Cloud Storage and records metadata in MongoDB.",
)
async def ingest_and_store_climate_index(
    file: UploadFile = File(...),
    index_type: str = Form(..., description="Climate index name, e.g., humid-heat-stress."),
    time_start: Optional[datetime] = Form(None, description="Start timestamp for the asset."),
    time_end: Optional[datetime] = Form(None, description="End timestamp for the asset."),
    units: Optional[str] = Form(None, description="Units of the raster values."),
) -> dict:
    """Ingest and persist GeoTIFF to storage with metadata in MongoDB."""
    payload = await file.read()
    _validate_upload(file, payload)

    request = AssetIngestRequest(
        index_type=index_type,
        time_range=TimeRange(start=time_start, end=time_end),
        units=units,
        filename=file.filename,
    )

    blob_store, repo = _initialise_storage()
    persisted = persist_climate_index(payload, request, blob_store=blob_store, repo=repo)

    response = AssetIngestResult(asset=request, raster=persisted.raster)
    response_dict = response.model_dump()
    response_dict["asset_id"] = persisted.asset_id
    response_dict["storage"] = persisted.storage.model_dump()
    return response_dict
