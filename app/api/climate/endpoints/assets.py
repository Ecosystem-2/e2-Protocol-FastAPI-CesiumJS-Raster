"""Asset management endpoints: list, search, and retrieve asset metadata."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Path, Query, status

from app.climate_indices import AssetRepository, GCSBlobStore
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# Asset Discovery & Retrieval Endpoints
# ============================================================================


@router.get(
    "/assets",
    summary="List all ingested climate index assets.",
    description="Retrieve a paginated list of assets stored in MongoDB. "
                "Filter by user_id and/or project_id to retrieve only assets owned by a specific user or project.",
)
async def list_assets(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of assets to return"),
    skip: int = Query(0, ge=0, description="Number of assets to skip for pagination"),
    user_id: Optional[str] = Query(None, description="Filter by owner user UUID"),
    project_id: Optional[str] = Query(None, description="Filter by project UUID"),
) -> dict:
    """List assets with pagination and optional ownership filtering."""
    repo = AssetRepository()
    assets = repo.list_assets(limit=limit, skip=skip, user_id=user_id, project_id=project_id)
    total = repo.count_assets(user_id=user_id, project_id=project_id)
    
    return {
        "total": total,
        "limit": limit,
        "skip": skip,
        "count": len(assets),
        "userID": user_id,
        "projectID": project_id,
        "assets": [asset.model_dump(by_alias=True) for asset in assets],
    }


@router.get(
    "/assets/search",
    summary="Search assets by filename, index type, or units.",
    description="Fuzzy search across filename, index_type, and units fields using case-insensitive regex.",
)
async def search_assets(
    q: str,
    limit: int = 50,
) -> dict:
    """Search assets using fuzzy matching on filename, index_type, or units."""
    repo = AssetRepository()
    assets = repo.search_assets(query=q, limit=limit)
    
    return {
        "query": q,
        "count": len(assets),
        "limit": limit,
        "assets": [asset.model_dump(by_alias=True) for asset in assets],
    }


@router.get(
    "/assets/by-filename/{filename}",
    summary="Get asset by exact filename match.",
    description="Retrieve asset metadata using the original uploaded filename.",
)
async def get_asset_by_filename(
    filename: str = Path(..., description="Original uploaded filename")
) -> dict:
    """Get asset by exact filename."""
    repo = AssetRepository()
    asset = repo.get_asset_by_filename(filename)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with filename '{filename}' not found."
        )

    return asset.model_dump(by_alias=True)


@router.get(
    "/assets/by-raster-id/{raster_id}",
    summary="Get asset by frontend-generated raster_id (UUID).",
    description="Retrieve asset metadata using the frontend-generated UUID for cross-system reference.",
)
async def get_asset_by_raster_id(
    raster_id: str = Path(..., description="Frontend-generated UUID (raster_id)")
) -> dict:
    """Get asset by frontend-generated rasterID (UUID)."""
    repo = AssetRepository()
    asset = repo.get_asset_by_raster_id(raster_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with rasterID '{raster_id}' not found."
        )

    return asset.model_dump(by_alias=True)


@router.get(
    "/assets/{id}",
    summary="Get details for a specific asset by ID.",
    description="Retrieve full metadata for an asset by its MongoDB ObjectId.",
)
async def get_asset_details(
    id: str = Path(..., description="MongoDB ObjectId of the asset")
) -> dict:
    """Get full asset details including storage URIs and raster metadata."""
    repo = AssetRepository()
    asset = repo.get_asset(id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    return asset.model_dump(by_alias=True)


# ============================================================================
# Asset Update & Delete Endpoints
# ============================================================================


def _get_blob_store() -> GCSBlobStore:
    """Initialise GCS blob store from environment."""
    bucket = os.getenv("GCS_BUCKET")
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS_BUCKET env var is required for storage operations.",
        )
    prefix = os.getenv("GCS_PREFIX", "").strip("/")
    return GCSBlobStore(bucket=bucket, prefix=prefix)


@router.delete(
    "/assets/{id}",
    summary="Delete an asset and its GCS blobs.",
    description="Permanently removes the asset record from MongoDB and deletes associated "
                "GeoTIFF files from Google Cloud Storage. This action cannot be undone.",
)
async def delete_asset(
    id: str = Path(..., description="MongoDB ObjectId of the asset")
) -> dict:
    """Delete asset from MongoDB and GCS."""
    repo = AssetRepository()

    # Fetch asset first to get storage URIs
    asset = repo.get_asset(id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{id}' not found."
        )

    # Delete from GCS
    blob_store = _get_blob_store()
    gcs_deleted = 0

    if asset.storage and asset.storage.raw:
        if blob_store.delete_blob(asset.storage.raw.uri):
            gcs_deleted += 1

    if asset.storage and asset.storage.cog:
        if blob_store.delete_blob(asset.storage.cog.uri):
            gcs_deleted += 1

    # Delete from MongoDB
    mongo_deleted = repo.delete_asset(id)

    if not mongo_deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete asset from MongoDB."
        )

    logger.info("Deleted asset %s: MongoDB=%s, GCS blobs=%d", id, mongo_deleted, gcs_deleted)

    return {
        "message": "Asset deleted successfully",
        "id": id,
        "rasterID": asset.raster_id,
        "mongoDeleted": mongo_deleted,
        "gcsBlobsDeleted": gcs_deleted,
    }


@router.put(
    "/assets/{id}",
    summary="Update asset metadata.",
    description="Update metadata fields for an existing asset. Only provided fields are updated. "
                "This does not replace the GeoTIFF file — use /ingest with the same raster_id for that.",
)
async def update_asset(
    id: str = Path(..., description="MongoDB ObjectId of the asset"),
    index_type: Optional[str] = Form(None, description="Climate index name to update"),
    units: Optional[str] = Form(None, description="Units of the raster values"),
    user_id: Optional[str] = Form(None, description="Owner user UUID to update"),
    project_id: Optional[str] = Form(None, description="Project UUID to update"),
) -> dict:
    """Update asset metadata fields."""
    repo = AssetRepository()

    # Check at least one field is provided
    if all(v is None for v in [index_type, units, user_id, project_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (index_type, units, user_id, project_id) must be provided."
        )

    updated_asset = repo.update_asset_metadata(
        id,
        index_type=index_type,
        units=units,
        user_id=user_id,
        project_id=project_id,
    )

    if not updated_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{id}' not found."
        )

    return {
        "message": "Asset updated successfully",
        "asset": updated_asset.model_dump(by_alias=True),
    }
