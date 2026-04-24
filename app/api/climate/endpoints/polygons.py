"""Polygon query endpoints: compute statistics and extract pixel values within polygons."""

from __future__ import annotations

import io
import csv
import json
from typing import Optional

import numpy as np
import rasterio
from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import Response

from app.climate_indices import AssetRepository
from app.api.climate.query import zonal_stats_from_cog, extract_pixels_from_cog
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================


def _validate_cog_uri(uri: str) -> str:
    """Validate that COG URI is a valid GCS path."""
    if not uri.startswith("gs://"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid COG URI: expected gs:// path, got {uri}"
        )
    return uri


def _resolve_asset(asset_id: str, repo: AssetRepository):
    """
    Resolve asset by ID, supporting both MongoDB ObjectId and frontend raster_id.
    
    Tries MongoDB ObjectId first. If that fails (invalid format or not found),
    falls back to raster_id lookup.
    
    Returns:
        tuple[AssetRecord | None, str]: (asset, resolved_id)
            - resolved_id is the MongoDB ObjectId string for consistency
    """
    # Try MongoDB ObjectId first
    asset = repo.get_asset(asset_id)
    if asset:
        return asset, asset.id
    
    # Fall back to raster_id lookup
    asset = repo.get_asset_by_raster_id(asset_id)
    if asset:
        logger.info("Resolved raster_id %s to MongoDB id %s", asset_id, asset.id)
        return asset, asset.id
    
    return None, asset_id


def _parse_query_inputs(asset_ids: str, polygons_geojson: str) -> tuple[list[str], list[dict]]:
    """Parse and validate asset IDs and polygons for query endpoints."""
    # Parse asset IDs
    asset_id_list = [aid.strip() for aid in asset_ids.split(",") if aid.strip()]
    if not asset_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one assetId is required."
        )
    
    # Parse polygons array
    try:
        polygons = json.loads(polygons_geojson)
        if not isinstance(polygons, list):
            raise ValueError("Expected a JSON array of polygons")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid polygons JSON array: {exc}"
        ) from exc
    
    if not polygons:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one polygon is required."
        )
    
    return asset_id_list, polygons


def _fetch_assets(asset_id_list: list[str], repo: AssetRepository) -> dict:
    """
    Fetch assets from repository and validate all exist.
    
    Supports both MongoDB ObjectIds and frontend raster_id UUIDs.
    Returns dict keyed by resolved MongoDB ObjectId.
    """
    assets = {}
    missing_ids = []
    
    for asset_id in asset_id_list:
        asset, resolved_id = _resolve_asset(asset_id, repo)
        if not asset:
            missing_ids.append(asset_id)
        else:
            assets[resolved_id] = asset
    
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assets not found: {', '.join(missing_ids)}"
        )
    
    return assets


def _generate_pixels_csv(assets: dict, polygons: list) -> Response:
    """Generate CSV response with pixel data."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write CSV header
    writer.writerow(["assetID", "filename", "polygonIndex", "lon", "lat", "value", "row", "col"])
    
    # Extract pixels for each asset and polygon
    for asset_id, asset in assets.items():
        cog_uri = _validate_cog_uri(asset.storage.cog.uri)
        
        for poly_idx, polygon in enumerate(polygons):
            try:
                clipped_data, transform, nodata = extract_pixels_from_cog(cog_uri, polygon)
                
                # Get valid pixel coordinates and values
                rows, cols = np.where(np.isfinite(clipped_data))
                if nodata is not None:
                    valid_mask = clipped_data[rows, cols] != nodata
                    rows = rows[valid_mask]
                    cols = cols[valid_mask]
                
                # Write each pixel as a CSV row
                for row, col in zip(rows, cols):
                    value = clipped_data[row, col]
                    lon, lat = rasterio.transform.xy(transform, row, col, offset='center')
                    
                    writer.writerow([
                        asset_id,
                        asset.filename or "",
                        poly_idx,
                        f"{lon:.6f}",
                        f"{lat:.6f}",
                        f"{value:.6f}",
                        int(row),
                        int(col)
                    ])
            
            except Exception as exc:
                logger.warning(
                    "Failed to extract pixels for asset %s, polygon %d: %s",
                    asset_id, poly_idx, exc
                )
                continue
    
    # Return CSV as downloadable file
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=pixels_{len(assets)}assets_{len(polygons)}polygons.csv"
        }
    )


def _generate_pixels_json(assets: dict, polygons: list) -> Response:
    """Generate JSON response with pixel data."""
    results = {}
    
    for asset_id, asset in assets.items():
        cog_uri = _validate_cog_uri(asset.storage.cog.uri)
        polygon_results = []
        
        for poly_idx, polygon in enumerate(polygons):
            try:
                clipped_data, transform, nodata = extract_pixels_from_cog(cog_uri, polygon)
                
                # Get valid pixel coordinates and values
                rows, cols = np.where(np.isfinite(clipped_data))
                if nodata is not None:
                    valid_mask = clipped_data[rows, cols] != nodata
                    rows = rows[valid_mask]
                    cols = cols[valid_mask]
                
                # Build pixel array
                pixels = []
                for row, col in zip(rows, cols):
                    value = clipped_data[row, col]
                    lon, lat = rasterio.transform.xy(transform, row, col, offset='center')
                    
                    pixels.append({
                        "lon": round(lon, 6),
                        "lat": round(lat, 6),
                        "value": round(float(value), 6),
                        "row": int(row),
                        "col": int(col)
                    })
                
                polygon_results.append({
                    "polygonIndex": poly_idx,
                    "pixelCount": len(pixels),
                    "pixels": pixels
                })

            except Exception as exc:
                logger.warning(
                    "Failed to extract pixels for asset %s, polygon %d: %s",
                    asset_id, poly_idx, exc
                )
                polygon_results.append({
                    "polygonIndex": poly_idx,
                    "error": str(exc),
                    "pixels": []
                })

        results[asset_id] = {
            "indexType": asset.index_type,
            "units": asset.units,
            "filename": asset.filename,
            "metadata": {
                "timeRange": asset.time_range.model_dump(by_alias=True) if asset.time_range else None,
            },
            "polygons": polygon_results
        }

    return Response(
        content=json.dumps({
            "assetCount": len(assets),
            "polygonCount": len(polygons),
            "results": results
        }, indent=2),
        media_type="application/json"
    )


# ============================================================================
# Polygon Query Endpoints
# ============================================================================


@router.post(
    "/query/polygons/stats",
    summary="Compute zonal stats for assets within polygons.",
    description="Compute zonal statistics from GCS-stored COGs within polygon geometries. Supports multiple assets and multiple polygons.",
)
async def query_polygons_stats(
    asset_ids: str = Form(..., alias="assetIds", description="Comma-separated asset IDs (MongoDB ObjectId or rasterID UUID)."),
    polygons_geojson: str = Form(..., alias="polygonsGeojson", description='JSON array of Polygon GeoJSON objects as string (e.g., \'[{"type":"Polygon","coordinates":[[[117.5,4.8],[117.6,4.8],[117.6,4.9],[117.5,4.9],[117.5,4.8]]]}]\').'),
) -> dict:
    """
    Compute zonal statistics for multiple assets across multiple polygons.
    
    Returns a nested structure: results[asset_id][polygon_index] = stats
    """
    # Parse and validate inputs
    asset_id_list, polygons = _parse_query_inputs(asset_ids, polygons_geojson)
    
    # Fetch all assets
    repo = AssetRepository()
    assets = _fetch_assets(asset_id_list, repo)
    
    # Compute statistics for each asset across all polygons
    results = {}
    
    for asset_id, asset in assets.items():
        cog_uri = _validate_cog_uri(asset.storage.cog.uri)
        polygon_results = []
        
        for idx, polygon in enumerate(polygons):
            try:
                stats = zonal_stats_from_cog(cog_uri, polygon)
                polygon_results.append({
                    "polygonIndex": idx,
                    "stats": {
                        **stats,
                        "countDescription": "Number of valid raster pixels within the polygon"
                    }
                })
            except Exception as exc:
                logger.warning(
                    "Failed to compute stats for asset %s, polygon %d: %s",
                    asset_id, idx, exc
                )
                polygon_results.append({
                    "polygonIndex": idx,
                    "error": str(exc),
                    "stats": None
                })

        results[asset_id] = {
            "indexType": asset.index_type,
            "units": asset.units,
            "metadata": {
                "filename": asset.filename,
                "timeRange": asset.time_range.model_dump(by_alias=True) if asset.time_range else None,
            },
            "polygons": polygon_results
        }

    return {
        "assetCount": len(assets),
        "polygonCount": len(polygons),
        "results": results
    }


@router.post(
    "/query/polygons/pixels",
    summary="Extract raw pixel values for assets within polygons.",
    description="Extract all raw pixel values from GCS-stored COGs within polygon geometries. Returns CSV by default or JSON if format=json.",
)
async def query_polygons_pixels(
    asset_ids: str = Form(..., alias="assetIds", description="Comma-separated asset IDs (MongoDB ObjectId or rasterID UUID)."),
    polygons_geojson: str = Form(..., alias="polygonsGeojson", description='JSON array of Polygon GeoJSON objects as string (e.g., \'[{"type":"Polygon","coordinates":[[[117.5,4.8],[117.6,4.8],[117.6,4.9],[117.5,4.9],[117.5,4.8]]]}]\').'),
    format: str = Form("csv", description="Output format: 'csv' or 'json'. Default is 'csv'."),
) -> Response:
    """
    Extract raw pixel values for multiple assets across multiple polygons.
    
    Returns CSV by default with columns: asset_id, filename, polygon_index, lon, lat, value, row, col
    Or JSON if format='json' with structure: results[asset_id][polygon_index] = [{lon, lat, value, row, col}, ...]
    """
    # Validate format parameter
    if format.lower() not in ["csv", "json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be either 'csv' or 'json'."
        )
    
    # Parse and validate inputs
    asset_id_list, polygons = _parse_query_inputs(asset_ids, polygons_geojson)
    
    # Fetch all assets
    repo = AssetRepository()
    assets = _fetch_assets(asset_id_list, repo)
    
    # Format-specific processing
    if format.lower() == "csv":
        return _generate_pixels_csv(assets, polygons)
    else:
        return _generate_pixels_json(assets, polygons)
