from __future__ import annotations

from datetime import datetime
from typing import Final, Optional, Tuple
from pathlib import Path

import os
import json
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from rio_tiler.io import COGReader  # type: ignore[attr-defined]
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.models import ImageData

from app.climate_indices.models import AssetIngestRequest, AssetIngestResult, TimeRange
from app.climate_indices.service import ingest_upload, persist_climate_index
from app.climate_indices.repository import AssetRepository
from app.climate_indices.storage import GCSBlobStore
from app.api.climate.query import zonal_stats_from_cog
from app.core.logging import get_logger

router = APIRouter(prefix="/climate-indices", tags=["climate_indices"])
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


def _validate_cog_uri(uri: str) -> str:
    """Validate that COG URI is a valid GCS path."""
    if not uri.startswith("gs://"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid COG URI: expected gs:// path, got {uri}"
        )
    return uri


def _parse_geojson(geojson_str: str) -> dict:
    """Parse GeoJSON string with error handling."""
    try:
        return json.loads(geojson_str)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid polygon JSON: {exc}"
        ) from exc


def _build_valid_mask(arr: np.ndarray, tile_mask: np.ndarray, nodata: Optional[float]) -> np.ndarray:
    """Build boolean mask for valid data pixels."""
    valid_mask = tile_mask.astype(bool)
    
    if nodata is not None:
        valid_mask = valid_mask & (arr != nodata)
    
    valid_mask = valid_mask & np.isfinite(arr)
    return valid_mask


def _determine_rescale_range(
    arr: np.ndarray,
    valid_mask: np.ndarray,
    scale_min: Optional[float],
    scale_max: Optional[float],
    asset_min: Optional[float],
    asset_max: Optional[float],
) -> Tuple[float, float]:
    """Determine min/max values for rescaling data to 0-255 range.
    
    Priority: explicit params > asset metadata > tile percentiles.
    """
    if scale_min is not None and scale_max is not None:
        return float(scale_min), float(scale_max)
    
    if asset_min is not None and asset_max is not None:
        return float(asset_min), float(asset_max)
    
    valid_data = arr[valid_mask]
    if valid_data.size > 0:
        return tuple(np.percentile(valid_data, [2, 98]))  # type: ignore
    
    return float(arr.min()), float(arr.max())


def _rescale_array(arr: np.ndarray, valid_mask: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    """Rescale array values to 0-255 range, handling NaN/inf safely."""
    arr_rescaled = np.full_like(arr, 0, dtype="float32")
    arr_rescaled[valid_mask] = np.clip(
        (arr[valid_mask] - vmin) / (vmax - vmin) * 255.0, 0, 255
    )
    return arr_rescaled.astype("uint8")


# ============================================================================
# Endpoints
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


@router.post(
    "/query/polygon",
    summary="Compute zonal stats for an asset within a polygon.",
    description="Compute zonal statistics from GCS-stored COG within a polygon geometry.",
)
async def query_polygon(
    asset_id: str = Form(..., description="Asset identifier (must exist in Mongo)."),
    polygon_geojson: str = Form(..., description="Polygon GeoJSON object as string."),
) -> dict:
    """Compute zonal statistics for a polygon within a raster asset."""
    repo = AssetRepository()
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    polygon = _parse_geojson(polygon_geojson)
    cog_uri = _validate_cog_uri(asset.storage.cog.uri)
    stats = zonal_stats_from_cog(cog_uri, polygon)
    
    return {
        "asset_id": asset_id,
        "index_type": asset.index_type,
        "units": asset.units,
        "stats": {
            **stats,
            "count_description": "Number of valid raster pixels within the polygon"
        },
        "metadata": {
            "filename": asset.filename,
            "time_range": asset.time_range.model_dump() if asset.time_range else None,
        }
    }

# %% ----------------------------------------------------------------------------
# Additional Asset Endpoints
# -----------------------------------------------------------------------------

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
    limit: int = 20,
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


@router.get(
    "/tiles/{asset_id}/{z}/{x}/{y}.png",
    summary="Serve a tile for an asset (COG-backed).",
    description="Lightweight tile endpoint using rio-tiler; resolves COG URI from Mongo.",
)
async def tile_png(
    asset_id: str,
    z: int,
    x: int,
    y: int,
    colormap_name: str = "viridis",
    scale_min: Optional[float] = None,
    scale_max: Optional[float] = None,
) -> Response:
    """Serve a PNG tile for a raster asset with proper transparency and colour mapping."""
    # Fetch asset and validate colourmap
    repo = AssetRepository()
    asset = repo.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    cmap_def = cmap.get(colormap_name)
    if cmap_def is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown colourmap: {colormap_name}"
        )

    try:
        with COGReader(input=asset.storage.cog.uri) as src:  # type: ignore[call-arg]
            tile = src.tile(x, y, z, tilesize=256)
            arr = tile.data[0]
            
            # Build mask for valid data
            valid_mask = _build_valid_mask(arr, tile.mask[0], asset.raster.nodata)
            if not valid_mask.any():
                raise TileOutsideBounds()
            
            # Determine rescale range and apply to data
            vmin, vmax = _determine_rescale_range(
                arr, valid_mask, scale_min, scale_max,
                asset.raster.min, asset.raster.max
            )
            arr_rescaled = _rescale_array(arr, valid_mask, vmin, vmax)
            alpha_mask = valid_mask.astype("uint8") * 255
            
            # Create new tile with proper mask and rescaled data
            tile = ImageData(
                array=np.expand_dims(arr_rescaled, axis=0),
                alpha_mask=alpha_mask,
                assets=tile.assets,
                crs=tile.crs,
                bounds=tile.bounds,
            )

            content = tile.render(colormap=cmap_def, img_format="PNG")  # type: ignore[call-arg]
            
    except TileOutsideBounds:
        logger.warning("Tile outside bounds for asset_id=%s, z=%d, x=%d, y=%d", asset_id, z, x, y)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tile outside bounds")
    except Exception as exc:
        logger.error("Tile render failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tile render failed: {exc}"
        ) from exc

    return Response(content, media_type="image/png")

