"""GeoTIFF ingestion endpoints: validate, upload, and persist climate index assets."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Optional, Tuple
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.climate_indices import (
    AssetIngestRequest,
    AssetIngestResult,
    AssetStyle,
    TimeRange,
    persist_climate_index,
    GCSBlobStore,
    AssetRepository,
)
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
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and persist a GeoTIFF climate index.",
    description="Stores the raw GeoTIFF and COG to Google Cloud Storage and records metadata in MongoDB. "
                "If a rasterID is provided and an asset with that rasterID exists, it will be replaced.",
)
async def ingest_and_store_climate_index(
    file: UploadFile = File(...),
    index_type: str = Form(..., alias="indexType", description="Climate index name, e.g., humid-heat-stress."),
    time_start: Optional[datetime] = Form(
        None,
        alias="timeStart",
        description="Start timestamp for the asset.",
        examples=["2041-01-01T00:00:00Z"],
    ),
    time_end: Optional[datetime] = Form(
        None,
        alias="timeEnd",
        description="End timestamp for the asset.",
        examples=["2070-12-30T23:59:59Z"],
    ),
    units: Optional[str] = Form(None, description="Units of the raster values."),
    raster_id: Optional[str] = Form(
        None,
        alias="rasterID",
        description=(
            "Frontend-generated UUID for cross-system reference. "
            "If provided and an asset with this rasterID exists, it will be replaced. "
            "Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (e.g., 550e8400-e29b-41d4-a716-446655440000). "
            "Generate with: JavaScript `crypto.randomUUID()` or Python `uuid.uuid4()`."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
    user_id: Optional[str] = Form(
        None,
        alias="userID",
        description="Owner user UUID for access control. Frontend responsibility to manage user records.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    ),
    project_id: Optional[str] = Form(
        None,
        alias="projectID",
        description="Project UUID for grouping assets. Frontend responsibility to manage project records.",
        examples=["proj-1234-5678-9abc-def012345678"],
    ),
    custom_group: Optional[str] = Form(
        None,
        alias="customGroup",
        description="Custom grouping identifier for organising assets.",
        examples=["my-custom-group"],
    ),
    pallete: Optional[str] = Form(
        None,
        description="Colour palette for asset visualisation.",
        examples=["viridis", "plasma", "inferno"],
    ),
) -> dict:
    """Ingest and persist GeoTIFF to storage with metadata in MongoDB."""
    payload = await file.read()
    _validate_upload(file, payload)

    style = AssetStyle(pallete=pallete) if pallete else None

    request = AssetIngestRequest(
        raster_id=raster_id,
        index_type=index_type,
        time_range=TimeRange(start=time_start, end=time_end),
        units=units,
        filename=file.filename,
        user_id=user_id,
        project_id=project_id,
        custom_group=custom_group,
        style=style,
    )

    blob_store, repo = _initialise_storage()
    persisted = persist_climate_index(payload, request, blob_store=blob_store, repo=repo)

    response = AssetIngestResult(asset=request, raster=persisted.raster)
    response_dict = response.model_dump(by_alias=True)
    response_dict["assetID"] = persisted.asset_id
    response_dict["rasterID"] = persisted.raster_id
    response_dict["userID"] = persisted.user_id
    response_dict["projectID"] = persisted.project_id
    response_dict["storage"] = persisted.storage.model_dump(by_alias=True)
    response_dict["replaced"] = persisted.replaced
    return response_dict
