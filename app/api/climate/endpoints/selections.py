"""Polygon selection management endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, status
from fastapi.responses import Response, JSONResponse

from app.climate_indices.models import (
    PolygonSelectionRecord,
    PolygonGeometry,
    SelectionStatistics,
    PolygonWithStatistics,
)
from app.climate_indices.repository import AssetRepository
from app.climate_indices.selections_repository import SelectionRepository
from app.api.climate.query import zonal_stats_from_cog
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# %% ============================================================================
# Helper Functions
# ============================================================================


def _compute_centroid(polygon_geojson: dict) -> dict[str, float]:
    """Compute polygon centroid for quick visualisation."""
    from shapely.geometry import shape
    geom = shape(polygon_geojson)
    c = geom.centroid
    return {"lon": c.x, "lat": c.y}


def _parse_polygon(polygon_geojson: str) -> PolygonGeometry | list[PolygonGeometry]:
    """Parse and validate polygon GeoJSON (handles single polygon or array)."""
    try:
        geom = json.loads(polygon_geojson)
        
        # Handle array of polygons - preserve all
        if isinstance(geom, list):
            if not geom:
                raise ValueError("Empty polygon array")
            return [PolygonGeometry(**g) for g in geom]
        
        # Single polygon
        return PolygonGeometry(**geom)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid polygon GeoJSON: {exc}"
        ) from exc


def _build_polygon_with_stats(
    polygon_geom: PolygonGeometry,
    asset_ids: list[str],
    asset_repo: AssetRepository
) -> PolygonWithStatistics:
    """Build a PolygonWithStatistics object for a single polygon."""
    # Compute centroid
    centroid = _compute_centroid(polygon_geom.model_dump())
    
    # Compute statistics for all assets
    statistics = []
    polygon_geojson = polygon_geom.model_dump()
    
    for asset_id in asset_ids:
        asset = asset_repo.get_asset(asset_id)
        if not asset:
            logger.warning("Asset not found during selection save: %s", asset_id)
            continue

        try:
            stats = zonal_stats_from_cog(asset.storage.cog.uri, polygon_geojson)

            statistics.append(SelectionStatistics(
                asset_id=asset_id,
                index_type=asset.index_type,
                units=asset.units,
                count=stats["count"],
                min=stats.get("min"),
                max=stats.get("max"),
                mean=stats.get("mean"),
                std=stats.get("std"),
                asset_filename=asset.filename,
                time_range=asset.time_range
            ))
        except Exception as exc:
            logger.error("Failed to compute stats for asset %s: %s", asset_id, exc)
            continue
    
    return PolygonWithStatistics(
        geometry=polygon_geom,
        centroid=centroid,
        statistics=statistics
    )


# %% ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/selections/save",
    summary="Save polygon selection with statistics",
    description="Store a named polygon selection with computed zonal statistics."
)
async def save_selection(
    title: str = Form(..., min_length=1, max_length=200),
    geometry: str = Form(..., description="GeoJSON polygon geometry as JSON string (single or array)"),
    asset_ids: str = Form(..., description="Comma-separated asset IDs to query"),
    description: Optional[str] = Form(None, max_length=2000),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    locale_id: Optional[str] = Form(None, description="Locale UUID for grouping selections"),
    site_id: Optional[str] = Form(None, description="Site UUID (auto-generated if not provided)"),
    user_id: Optional[str] = Form(None, description="User UUID"),
) -> JSONResponse:
    """
    Save polygon selection to polygon_selections collection.

    Re-uploading the same title **replaces** the existing selection.
    """
    # Parse inputs
    polygon = _parse_polygon(geometry)
    asset_id_list = [aid.strip() for aid in asset_ids.split(",") if aid.strip()]
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    if not asset_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one asset_id is required"
        )

    # Generate site_id if not provided
    if not site_id:
        site_id = str(uuid.uuid4())

    # Build PolygonWithStatistics objects for each polygon
    asset_repo = AssetRepository()
    polygon_list = polygon if isinstance(polygon, list) else [polygon]
    
    polygons_with_stats = []
    for poly in polygon_list:
        poly_with_stats = _build_polygon_with_stats(poly, asset_id_list, asset_repo)
        if not poly_with_stats.statistics:
            logger.warning("No statistics computed for polygon")
        polygons_with_stats.append(poly_with_stats)

    if not polygons_with_stats or not any(p.statistics for p in polygons_with_stats):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid statistics computed for provided assets and polygons"
        )

    # Build and save PolygonSelectionRecord
    record = PolygonSelectionRecord(
        locale_id=locale_id,
        site_id=site_id,
        title=title,
        description=description,
        tags=tag_list,
        polygons=polygons_with_stats,
        created_by=user_id
    )
    
    selection_repo = SelectionRepository()
    selection_id, was_replaced = selection_repo.save_selection(record)

    # Fetch the complete saved record from database
    saved_selection = selection_repo.get_selection(selection_id)
    if not saved_selection:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved selection record"
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if was_replaced else status.HTTP_201_CREATED,
        content={
            **saved_selection.model_dump(by_alias=True, mode='json'),
            "replaced": was_replaced,
            "message": "Selection updated" if was_replaced else "Selection created"
        }
    )


@router.get(
    "/selections",
    summary="List all saved selections",
    description="Retrieve all polygon selections with optional tag filtering."
)
async def list_selections(
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0)
) -> JSONResponse:
    """List saved selections with pagination and tag filtering."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    repo = SelectionRepository()
    selections = repo.list_selections(tags=tag_list, limit=limit, skip=skip)

    # Return lightweight summaries
    summaries = [
        {
            "id": sel.id,
            "title": sel.title,
            "description": sel.description,
            "tags": sel.tags,
            "polygon_count": len(sel.polygons),
            "statistics_count": sum(len(p.statistics) for p in sel.polygons),
            "created_at": sel.created_at.isoformat(),
            "updated_at": sel.updated_at.isoformat()
        }
        for sel in selections
    ]

    return JSONResponse(content={
        "total": len(summaries),
        "selections": summaries
    })


@router.get(
    "/selections/by-name/{name}",
    summary="Retrieve selection by title",
    description="Fetch full selection details including geometry and statistics."
)
async def get_selection_by_name(name: str) -> JSONResponse:
    """Retrieve selection by case-insensitive title (endpoint name kept for compatibility)."""
    repo = SelectionRepository()
    selection = repo.get_selection_by_name(name)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {name}"
        )

    return JSONResponse(content=selection.model_dump(by_alias=True, mode='json'))


@router.get(
    "/selections/{selection_id}",
    summary="Retrieve selection by ID",
    description="Fetch full selection details by MongoDB ObjectId."
)
async def get_selection(selection_id: str) -> JSONResponse:
    """Retrieve selection by ID."""
    repo = SelectionRepository()
    selection = repo.get_selection(selection_id)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {selection_id}"
        )

    return JSONResponse(content=selection.model_dump(by_alias=True, mode='json'))


@router.delete(
    "/selections/{selection_id}",
    summary="Delete selection",
    description="Remove a saved polygon selection permanently."
)
async def delete_selection(selection_id: str) -> JSONResponse:
    """Delete selection by ID."""
    repo = SelectionRepository()
    deleted = repo.delete_selection(selection_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {selection_id}"
        )

    return JSONResponse(content={"message": "Selection deleted", "id": selection_id})
