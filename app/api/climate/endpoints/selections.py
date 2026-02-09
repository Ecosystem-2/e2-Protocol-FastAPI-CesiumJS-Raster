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
    CZMLExportOptions,
    SiteData,
    SiteLocation,
)
from app.climate_indices.repository import AssetRepository
from app.climate_indices.selections_repository import SelectionRepository
from app.climate_indices.locale_site_repository import LocaleSiteRepository
from app.climate_indices.czml_generate import CZMLExportService
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


def _compute_stats_for_assets(
    asset_ids: list[str],
    polygon_geojson: dict,
    asset_repo: AssetRepository
) -> list[SelectionStatistics]:
    """Compute zonal statistics for multiple assets (single polygon)."""
    statistics = []

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

    return statistics


def _compute_stats_for_polygons(
    asset_ids: list[str],
    polygons: list[PolygonGeometry],
    asset_repo: AssetRepository
) -> list[SelectionStatistics]:
    """Compute zonal statistics for multiple assets and multiple polygons."""
    statistics = []

    for polygon_idx, polygon in enumerate(polygons):
        polygon_geojson = polygon.model_dump()
        
        for asset_id in asset_ids:
            asset = asset_repo.get_asset(asset_id)
            if not asset:
                logger.warning("Asset not found during selection save: %s", asset_id)
                continue

            try:
                stats = zonal_stats_from_cog(asset.storage.cog.uri, polygon_geojson)

                # Note: We could add polygon_index to SelectionStatistics model
                # For now, all stats are stored flat - consumers can group by asset_id
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
                logger.error(
                    "Failed to compute stats for asset %s, polygon %d: %s",
                    asset_id, polygon_idx, exc
                )
                continue

    return statistics


# %% ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/selections/save",
    summary="Save polygon selection with statistics",
    description="Store a named polygon selection in siteData and update localeData."
)
async def save_selection(
    title: str = Form(..., min_length=1, max_length=200),
    geometry: str = Form(..., description="GeoJSON polygon geometry as JSON string"),
    asset_ids: str = Form(..., description="Comma-separated asset IDs to query"),
    description: Optional[str] = Form(None, max_length=2000),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    locale_id: Optional[str] = Form(None, description="Locale UUID (required for demo3)"),
    user_id: Optional[str] = Form(None, description="Optional user UUID"),
    project_id: Optional[str] = Form(None, description="Optional project UUID"),
    category: Optional[str] = Form(None, description="Comma-separated categories"),
) -> JSONResponse:
    """
    Save polygon selection to siteData and localeData collections.

    Re-uploading the same title **replaces** the existing site.
    """
    # Parse inputs
    polygon = _parse_polygon(geometry)
    asset_id_list = [aid.strip() for aid in asset_ids.split(",") if aid.strip()]
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    category_list = [c.strip() for c in category.split(",")] if category else []

    if not asset_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one asset_id is required"
        )

    # Require locale_id for proper E2 structure
    if not locale_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="locale_id is required"
        )

    # Compute statistics for all polygons
    first_polygon = polygon[0] if isinstance(polygon, list) else polygon
    asset_repo = AssetRepository()
    
    if isinstance(polygon, list):
        # Multiple polygons: compute stats for each
        statistics = _compute_stats_for_polygons(asset_id_list, polygon, asset_repo)
    else:
        # Single polygon: use original method
        statistics = _compute_stats_for_assets(
            asset_id_list,
            first_polygon.model_dump(),
            asset_repo
        )

    if not statistics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid statistics computed for provided assets"
        )

    # Compute centroid from first polygon (for location pin)
    centroid = _compute_centroid(first_polygon.model_dump())

    # Build SiteData record
    site_id = str(uuid.uuid4())
    site = SiteData(
        site_id=site_id,
        locale_id=locale_id,
        user_id=user_id,
        project_id=project_id,
        title=title,
        desc=description,
        location=SiteLocation(
            coordinates=[centroid["lon"], centroid["lat"], 100],
            polygon=polygon,
            centroid=centroid,
            statistics=statistics
        ),
        media_id=[],
        category=category_list,
        tags=tag_list
    )

    # Save to siteData
    locale_site_repo = LocaleSiteRepository()
    saved_site_id, was_replaced = locale_site_repo.save_site(site)

    # Ensure localeData exists
    locale_site_repo.get_or_create_locale(
        locale_id=locale_id,
        title="Segama River",
        description="Humid Heat Stress and PPET selection"
    )
    
    # Add site reference to locale (uses $addToSet to avoid duplicates)
    locale_site_repo.add_site_to_locale(locale_id, saved_site_id)

    # Also save to original polygon_selections for backward compatibility
    record = PolygonSelectionRecord(
        name=title,
        description=description,
        tags=tag_list,
        polygon=polygon,
        centroid=centroid,
        statistics=statistics
    )
    selection_repo = SelectionRepository()
    selection_id, _ = selection_repo.save_selection(record)

    # Fetch the complete saved site record from database
    saved_site = locale_site_repo.get_site_by_title(title)
    if not saved_site:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved site record"
        )

    # Return complete site data with metadata (exclude non-serializable fields)
    site_dict = saved_site.model_dump(by_alias=True, mode='json')
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if was_replaced else status.HTTP_201_CREATED,
        content={
            **site_dict,
            "selection_id": selection_id,  # Backward compatibility
            "replaced": was_replaced,
            "message": "Site updated" if was_replaced else "Site created"
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
            "name": sel.name,
            "description": sel.description,
            "tags": sel.tags,
            "statistics_count": len(sel.statistics),
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
    summary="Retrieve selection by name",
    description="Fetch full selection details including geometry and statistics."
)
async def get_selection_by_name(name: str) -> JSONResponse:
    """Retrieve selection by case-insensitive name."""
    repo = SelectionRepository()
    selection = repo.get_selection_by_name(name)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {name}"
        )

    return JSONResponse(content=selection.model_dump(by_alias=True))


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

    return JSONResponse(content=selection.model_dump(by_alias=True))


@router.post(
    "/selections/{selection_id}/export-czml",
    summary="Export selection as CZML",
    description="Generate CZML visualisation with configurable rendering options."
)
async def export_selection_czml(
    selection_id: str,
    visualisation_type: str = Form("point", description="point, bar, or billboard"),
    colourmap_name: str = Form("viridis", description="Matplotlib colourmap name"),
    scale_min: Optional[float] = Form(None),
    scale_max: Optional[float] = Form(None),
    value_field: str = Form("mean", description="mean, min, max, or std"),
    point_size: int = Form(10, ge=1, le=100),
    bar_height_multiplier: float = Form(10000.0, gt=0),
    show_labels: bool = Form(True)
) -> Response:
    """
    Export selection as CZML for Cesium visualisation.

    Uses `commons/colours.py` for colourmap rendering.
    """
    # Fetch selection
    repo = SelectionRepository()
    selection = repo.get_selection(selection_id)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {selection_id}"
        )

    # Build export options
    try:
        options = CZMLExportOptions(
            visualisation_type=visualisation_type,  # type: ignore
            colourmap_name=colourmap_name,
            scale_min=scale_min,
            scale_max=scale_max,
            value_field=value_field,  # type: ignore
            point_size=point_size,
            bar_height_multiplier=bar_height_multiplier,
            show_labels=show_labels
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export options: {exc}"
        ) from exc

    # Generate CZML
    service = CZMLExportService()
    czml_json = service.export(selection, options)

    return Response(
        content=czml_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={selection.name}_viz.czml"
        }
    )


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


@router.get(
    "/sites",
    summary="List all sites",
    description="Retrieve all sites from siteData collection."
)
async def list_sites(
    locale_id: Optional[str] = Query(None, description="Filter by locale UUID")
) -> JSONResponse:
    """List sites with optional locale filtering."""
    repo = LocaleSiteRepository()
    sites = repo.list_sites(locale_id=locale_id)

    summaries = [
        {
            "site_id": site.site_id,
            "locale_id": site.locale_id,
            "title": site.title,
            "desc": site.desc,
            "location": site.location.coordinates,
            "centroid": site.location.centroid,
            "statistics_count": len(site.location.statistics) if site.location.statistics else 0,
            "tags": site.tags,
            "category": site.category,
            "created": site.creation_date_time.isoformat()
        }
        for site in sites
    ]

    return JSONResponse(content={
        "total": len(summaries),
        "sites": summaries
    })


@router.get(
    "/sites/by-title/{title}",
    summary="Get site by title",
    description="Fetch site details by case-insensitive title."
)
async def get_site_by_title(title: str) -> JSONResponse:
    """Retrieve site by title."""
    repo = LocaleSiteRepository()
    site = repo.get_site_by_title(title)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site not found: {title}"
        )

    return JSONResponse(content=site.model_dump(by_alias=True, mode='json'))


@router.get(
    "/sites/{site_id}",
    summary="Get site by ID",
    description="Fetch site details by siteID UUID."
)
async def get_site_by_id(site_id: str) -> JSONResponse:
    """Retrieve site by siteID."""
    repo = LocaleSiteRepository()
    
    # Query by siteID field
    from app.db.mongo import get_sync_client
    import os
    
    client = get_sync_client()
    db_name = os.getenv("MONGO_DB", "climate_indices")
    site_collection = client[db_name]["siteData"]
    
    site_doc = site_collection.find_one({"siteID": site_id})
    
    if not site_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site not found: {site_id}"
        )
    
    # Convert to SiteData model
    from app.climate_indices.models import SiteData
    site = SiteData.model_validate(site_doc)
    
    return JSONResponse(content=site.model_dump(by_alias=True, mode='json'))


@router.get(
    "/locale/{locale_id}",
    summary="Get locale data",
    description="Retrieve locale data with all associated sites."
)
async def get_locale(locale_id: str) -> JSONResponse:
    """Retrieve locale by ID."""
    from app.db.mongo import get_sync_client
    import os
    
    client = get_sync_client()
    db_name = os.getenv("MONGO_DB", "climate_indices")
    locale_collection = client[db_name]["localeData"]
    
    locale_doc = locale_collection.find_one({"localeID": locale_id})
    
    if not locale_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Locale not found: {locale_id}"
        )
    
    # Convert ObjectId to string
    if "_id" in locale_doc:
        locale_doc["_id"] = str(locale_doc["_id"])
    
    return JSONResponse(content=locale_doc)

@router.post(
    "/sites/{site_id}/export-czml",
    summary="Export site as CZML",
    description="Generate CZML visualisation for a site from the siteData collection."
)
async def export_site_czml(
    site_id: str,
    visualisation_type: str = Form("point", description="point, bar, or billboard"),
    colourmap_name: str = Form("viridis", description="Matplotlib colourmap name"),
    scale_min: Optional[float] = Form(None),
    scale_max: Optional[float] = Form(None),
    value_field: str = Form("mean", description="mean, min, max, or std"),
    point_size: int = Form(10, ge=1, le=100),
    bar_height_multiplier: float = Form(10000.0, gt=0),
    show_labels: bool = Form(True)
) -> Response:
    """
    Export site as CZML for Cesium visualisation.
    
    Converts SiteData to PolygonSelectionRecord format for CZML export.
    """
    # Fetch site from siteData collection
    from app.db.mongo import get_sync_client
    import os
    
    client = get_sync_client()
    db_name = os.getenv("MONGO_DB", "climate_indices")
    site_collection = client[db_name]["siteData"]
    
    site_doc = site_collection.find_one({"siteID": site_id})
    
    if not site_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site not found: {site_id}"
        )
    
    # Convert to SiteData model
    from app.climate_indices.models import SiteData, PolygonSelectionRecord, SelectionStatistics, TimeRange
    from bson import ObjectId
    site = SiteData.model_validate(site_doc)
    
    # Enrich statistics with time_range from assets collection
    assets_collection = client[db_name]["assets"]
    enriched_statistics = []
    
    if site.location.statistics:
        # Fetch all assets in one query for efficiency
        # Convert string asset_ids to ObjectId for MongoDB query
        asset_ids = []
        for stat in site.location.statistics:
            try:
                asset_ids.append(ObjectId(stat.asset_id))
            except Exception:
                # If conversion fails, try as string
                asset_ids.append(stat.asset_id)
        
        assets_cursor = assets_collection.find({"_id": {"$in": asset_ids}})
        assets_map = {str(asset["_id"]): asset for asset in assets_cursor}
        
        # Enrich each statistic with time_range from asset
        for stat in site.location.statistics:
            asset = assets_map.get(stat.asset_id)
            
            # Create enriched statistic with time_range
            enriched_stat = SelectionStatistics(
                asset_id=stat.asset_id,
                index_type=stat.index_type,
                units=stat.units,
                count=stat.count,
                min=stat.min,
                max=stat.max,
                mean=stat.mean,
                std=stat.std,
                asset_filename=stat.asset_filename or (asset.get("filename") if asset else None),
                time_range=TimeRange(
                    start=asset["time_range"]["start"] if asset and asset.get("time_range") and asset["time_range"].get("start") else None,
                    end=asset["time_range"]["end"] if asset and asset.get("time_range") and asset["time_range"].get("end") else None
                ) if asset and asset.get("time_range") else None
            )
            enriched_statistics.append(enriched_stat)
    
    # Convert SiteData to PolygonSelectionRecord for CZML export
    # Handle both single polygon and multi-polygon cases
    polygon_geometry = site.location.polygon
    
    # For CZML export with multiple polygons, generate one entity per polygon
    # Each polygon gets the same statistics (centroid-based visualization)
    if isinstance(polygon_geometry, list) and len(polygon_geometry) > 1:
        # Multiple polygons: create multiple entities with temporal animation
        czml_packets = []
        
        # Add document packet first
        doc_packet = {
            "id": "document",
            "name": f"{site.title} - Multi-Polygon",
            "version": "1.0",
            "description": site.desc or ""
        }
        
        # Add clock for animation if we have time ranges
        has_time_data = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in enriched_statistics
        )
        
        if has_time_data:
            all_starts = [
                s.time_range.start for s in enriched_statistics 
                if s.time_range and s.time_range.start
            ]
            all_ends = [
                s.time_range.end for s in enriched_statistics 
                if s.time_range and s.time_range.end
            ]
            
            if all_starts and all_ends:
                doc_packet["clock"] = {
                    "interval": f"{min(all_starts).isoformat()}/{max(all_ends).isoformat()}",
                    "currentTime": min(all_starts).isoformat(),
                    "multiplier": 31536000,  # 1 year per second (adjust as needed)
                    "range": "LOOP_STOP",
                    "step": "SYSTEM_CLOCK_MULTIPLIER"
                }
        
        czml_packets.append(doc_packet)
        
        # Create entity for each polygon
        for poly_idx, polygon_data in enumerate(polygon_geometry):
            # Compute centroid for this polygon
            from shapely.geometry import shape
            geom = shape(polygon_data.model_dump() if hasattr(polygon_data, 'model_dump') else polygon_data)
            poly_centroid = {"lon": geom.centroid.x, "lat": geom.centroid.y}
            
            # Create selection for this polygon
            selection = PolygonSelectionRecord(
                name=f"{site.title} - Polygon {poly_idx + 1}",
                description=site.desc or "",
                tags=site.tags or [],
                polygon=polygon_data,
                centroid=poly_centroid,
                statistics=enriched_statistics,
                created_at=site.creation_date_time
            )
            
            # Build export options
            options = CZMLExportOptions(
                visualisation_type=visualisation_type,  # type: ignore
                colourmap_name=colourmap_name,
                scale_min=scale_min,
                scale_max=scale_max,
                value_field=value_field,  # type: ignore
                point_size=point_size,
                bar_height_multiplier=bar_height_multiplier,
                show_labels=show_labels
            )
            
            # Generate CZML for this polygon (returns JSON string)
            service = CZMLExportService()
            polygon_czml_str = service.export(selection, options)
            polygon_czml = json.loads(polygon_czml_str)
            
            # Skip document packet, append entity packets only
            czml_packets.extend(polygon_czml[1:])
        
        # Return combined CZML
        czml_json = json.dumps(czml_packets, indent=2)
        
    else:
        # Single polygon: use original flow
        polygon_data = polygon_geometry[0] if isinstance(polygon_geometry, list) else polygon_geometry
        
        # Create PolygonSelectionRecord compatible object with enriched statistics
        selection = PolygonSelectionRecord(
            name=site.title,
            description=site.desc or "",
            tags=site.tags or [],
            polygon=polygon_data,
            centroid=site.location.centroid,
            statistics=enriched_statistics,
            created_at=site.creation_date_time
        )
        
        # Build export options
        options = CZMLExportOptions(
            visualisation_type=visualisation_type,  # type: ignore
            colourmap_name=colourmap_name,
            scale_min=scale_min,
            scale_max=scale_max,
            value_field=value_field,  # type: ignore
            point_size=point_size,
            bar_height_multiplier=bar_height_multiplier,
            show_labels=show_labels
        )
        
        # Generate CZML
        service = CZMLExportService()
        czml_json = service.export(selection, options)
    
    return Response(
        content=czml_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="site_{site_id}.czml"'
        }
    )