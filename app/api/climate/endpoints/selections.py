# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Polygon selection management endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Path, Query, status
from fastapi.responses import Response, JSONResponse

from app.climate_indices import (
    PolygonSelectionRecord,
    PolygonGeometry,
    SelectionStatistics,
    PolygonWithStatistics,
    AssetRepository,
    SelectionRepository,
)
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


def _parse_polygon(polygon_geojson: str) -> list[tuple[PolygonGeometry, Optional[str]]]:
    """Parse and validate polygon GeoJSON, extracting optional per-polygon title.

    Accepts a single polygon object or an array of polygon objects. Each object
    may include an optional ``title`` field alongside the standard GeoJSON fields
    (``type``, ``coordinates``). Returns a list of (geometry, title) tuples.
    """
    try:
        raw = json.loads(polygon_geojson)

        # Normalise to a list so the rest of the code is uniform
        items = raw if isinstance(raw, list) else [raw]

        if not items:
            raise ValueError("Empty polygon array")

        result = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Expected a polygon object, got {type(item).__name__}")
            poly_title = item.get("title") or None
            result.append((PolygonGeometry(**item), poly_title))

        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid polygon GeoJSON: {exc}"
        ) from exc


def _resolve_asset(asset_id: str, asset_repo: AssetRepository):
    """
    Resolve asset by ID, supporting both MongoDB ObjectId and frontend raster_id.
    
    Tries MongoDB ObjectId first. If that fails (invalid format or not found),
    falls back to raster_id lookup.
    
    Returns:
        tuple[AssetRecord | None, str]: (asset, resolved_id)
            - resolved_id is the MongoDB ObjectId string for storage
    """
    # Try MongoDB ObjectId first
    asset = asset_repo.get_asset(asset_id)
    if asset:
        return asset, asset.id
    
    # Fall back to raster_id lookup
    asset = asset_repo.get_asset_by_raster_id(asset_id)
    if asset:
        logger.info("Resolved raster_id %s to MongoDB id %s", asset_id, asset.id)
        return asset, asset.id
    
    return None, asset_id


def _build_polygon_with_stats(
    polygon_geom: PolygonGeometry,
    asset_ids: list[str],
    asset_repo: AssetRepository,
    title: Optional[str] = None,
) -> PolygonWithStatistics:
    """Build a PolygonWithStatistics object for a single polygon."""
    # Compute centroid
    centroid = _compute_centroid(polygon_geom.model_dump())
    
    # Compute statistics for all assets
    statistics = []
    polygon_geojson = polygon_geom.model_dump()
    
    for asset_id in asset_ids:
        asset, resolved_id = _resolve_asset(asset_id, asset_repo)
        if not asset:
            logger.warning("Asset not found during selection save: %s", asset_id)
            continue

        try:
            stats = zonal_stats_from_cog(asset.storage.cog.uri, polygon_geojson)

            statistics.append(SelectionStatistics(
                asset_ref=resolved_id,  # Always store MongoDB ObjectId
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
        title=title,
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
    asset_ids: str = Form(..., alias="assetIds", description="Comma-separated asset IDs (MongoDB ObjectId or rasterID UUID)"),
    description: Optional[str] = Form(None, max_length=2000),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    locale_id: Optional[str] = Form(None, alias="localeID", description="Locale UUID for grouping selections"),
    site_id: Optional[str] = Form(None, alias="siteID", description="Site UUID (auto-generated if not provided)"),
    user_id: Optional[str] = Form(None, alias="userID", description="Owner user UUID for access control"),
    project_id: Optional[str] = Form(None, alias="projectID", description="Project UUID for grouping selections"),
    selection_id: Optional[str] = Form(None, alias="selectionID", description="Frontend-generated UUID for cross-system reference"),
) -> JSONResponse:
    """
    Save polygon selection to polygon_selections collection.

    Re-uploading the same title **replaces** the existing selection.
    """
    # Parse inputs
    polygon_list = _parse_polygon(geometry)  # list of (PolygonGeometry, title) tuples
    asset_id_list = [aid.strip() for aid in asset_ids.split(",") if aid.strip()]
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    if not asset_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one assetId is required"
        )

    # Generate site_id if not provided
    if not site_id:
        site_id = str(uuid.uuid4())

    # Build PolygonWithStatistics objects for each polygon
    asset_repo = AssetRepository()

    polygons_with_stats = []
    for poly_geom, poly_title in polygon_list:
        poly_with_stats = _build_polygon_with_stats(poly_geom, asset_id_list, asset_repo, title=poly_title)
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
        selection_id=selection_id,
        locale_id=locale_id,
        site_id=site_id,
        user_id=user_id,
        project_id=project_id,
        title=title,
        description=description,
        tags=tag_list,
        polygons=polygons_with_stats,
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
            "polygonCount": len(sel.polygons),
            "statisticsCount": sum(len(p.statistics) for p in sel.polygons),
            "createdAt": sel.created_at.isoformat(),
            "updatedAt": sel.updated_at.isoformat()
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
async def get_selection_by_name(
    name: str = Path(..., description="Selection title (case-insensitive match)")
) -> JSONResponse:
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
    "/selections/{id}",
    summary="Retrieve selection by ID",
    description="Fetch full selection details by MongoDB ObjectId."
)
async def get_selection(
    id: str = Path(..., description="MongoDB ObjectId of the selection")
) -> JSONResponse:
    """Retrieve selection by ID."""
    repo = SelectionRepository()
    selection = repo.get_selection(id)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {id}"
        )

    return JSONResponse(content=selection.model_dump(by_alias=True, mode='json'))


@router.get(
    "/selections/by-selection-id/{selectionID}",
    summary="Retrieve selection by selectionID (UUID)",
    description="Fetch full selection details by frontend-generated UUID."
)
async def get_selection_by_selection_id(
    selectionID: str = Path(..., description="Frontend-generated UUID (selectionID)")
) -> JSONResponse:
    """Retrieve selection by frontend-generated selectionID (UUID)."""
    repo = SelectionRepository()
    selection = repo.get_selection_by_selection_id(selectionID)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found with selectionID: {selectionID}"
        )

    return JSONResponse(content=selection.model_dump(by_alias=True, mode='json'))


@router.delete(
    "/selections/{id}",
    summary="Delete selection",
    description="Remove a saved polygon selection permanently."
)
async def delete_selection(
    id: str = Path(..., description="MongoDB ObjectId of the selection")
) -> JSONResponse:
    """Delete selection by ID."""
    repo = SelectionRepository()
    deleted = repo.delete_selection(id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {id}"
        )

    return JSONResponse(content={"message": "Selection deleted", "id": id})


@router.put(
    "/selections/{id}",
    summary="Update selection metadata",
    description="Update metadata fields for an existing selection. Only provided fields are updated. "
                "This does not update geometry or statistics — use /selections/save with the same selectionID for that."
)
async def update_selection(
    id: str = Path(..., description="MongoDB ObjectId of the selection"),
    title: Optional[str] = Form(None, min_length=1, max_length=200, description="Selection title"),
    description: Optional[str] = Form(None, max_length=2000, description="Selection description"),
    tags: Optional[str] = Form(None, description="Comma-separated tags (replaces existing tags)"),
    user_id: Optional[str] = Form(None, alias="userID", description="Owner user UUID"),
    project_id: Optional[str] = Form(None, alias="projectID", description="Project UUID"),
) -> JSONResponse:
    """Update selection metadata fields."""
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Check at least one field is provided
    if all(v is None for v in [title, description, tag_list, user_id, project_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title, description, tags, userID, projectID) must be provided."
        )

    repo = SelectionRepository()
    updated = repo.update_selection_metadata(
        id,
        title=title,
        description=description,
        tags=tag_list,
        user_id=user_id,
        project_id=project_id,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {id}"
        )

    return JSONResponse(content={
        "message": "Selection updated successfully",
        "selection": updated.model_dump(by_alias=True, mode='json')
    })
