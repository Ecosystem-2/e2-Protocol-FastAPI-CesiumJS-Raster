"""Asset management endpoints: list, search, and retrieve asset metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.climate_indices.repository import AssetRepository
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# Asset Discovery & Retrieval Endpoints
# ============================================================================


@router.get(
    "/assets",
    summary="List all ingested climate index assets.",
    description="Retrieve a paginated list of all assets stored in MongoDB.",
)
async def list_assets(
    limit: int = 100,
    skip: int = 0,
) -> dict:
    """List all assets with pagination."""
    repo = AssetRepository()
    assets = repo.list_assets(limit=limit, skip=skip)
    total = repo.count_assets()
    
    return {
        "total": total,
        "limit": limit,
        "skip": skip,
        "count": len(assets),
        "assets": [asset.model_dump() for asset in assets],
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
        "assets": [asset.model_dump() for asset in assets],
    }


@router.get(
    "/assets/by-filename/{filename}",
    summary="Get asset by exact filename match.",
    description="Retrieve asset metadata using the original uploaded filename.",
)
async def get_asset_by_filename(filename: str) -> dict:
    """Get asset by exact filename."""
    repo = AssetRepository()
    asset = repo.get_asset_by_filename(filename)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with filename '{filename}' not found."
        )
    
    return asset.model_dump()


@router.get(
    "/assets/{asset_id}",
    summary="Get details for a specific asset by ID.",
    description="Retrieve full metadata for an asset by its MongoDB ObjectId.",
)
async def get_asset_details(asset_id: str) -> dict:
    """Get full asset details including storage URIs and raster metadata."""
    repo = AssetRepository()
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    
    return asset.model_dump()
