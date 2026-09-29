# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tile serving endpoints: render PNG tiles from COG-backed climate index assets."""

from __future__ import annotations

import os
from typing import Optional, Tuple
from urllib.parse import urlparse

import numpy as np
from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import Response
from rio_tiler.io import COGReader  # type: ignore[attr-defined]
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.models import ImageData

from app.climate_indices import AssetRepository
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _env_flag_enabled(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _log_gcs_visibility(uri: str) -> None:
    """Log whether the Python GCS client can see the COG URI before GDAL opens it."""
    if not _env_flag_enabled("GDAL_TILE_DIAGNOSTICS"):
        return

    if not uri.startswith("gs://"):
        logger.info("Skipping GCS visibility probe for non-GCS URI: %s", uri)
        return

    try:
        from google.cloud import storage  # type: ignore

        parsed = urlparse(uri)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")
        blob = storage.Client().bucket(bucket_name).blob(blob_name)
        exists = blob.exists()
        if exists:
            blob.reload()
        logger.info(
            "Tile GCS visibility probe: uri=%s exists=%s size=%s generation=%s updated=%s",
            uri,
            exists,
            blob.size if exists else None,
            blob.generation if exists else None,
            blob.updated if exists else None,
        )
    except Exception as exc:
        logger.warning("Tile GCS visibility probe failed for %s: %s", uri, exc)


def _log_rasterio_runtime(uri: str) -> None:
    """Log the GDAL/rasterio runtime that rio-tiler will use for tile rendering."""
    if not _env_flag_enabled("GDAL_TILE_DIAGNOSTICS"):
        return

    try:
        import rasterio  # type: ignore

        logger.info(
            "Tile rasterio runtime: uri=%s rasterio=%s gdal_version=%s "
            "GDAL_DISABLE_READDIR_ON_OPEN=%s VSI_CACHE=%s",
            uri,
            getattr(rasterio, "__file__", "unknown"),
            getattr(rasterio, "__gdal_version__", "unknown"),
            os.getenv("GDAL_DISABLE_READDIR_ON_OPEN"),
            os.getenv("VSI_CACHE"),
        )
    except Exception as exc:
        logger.warning("Tile rasterio runtime probe failed for %s: %s", uri, exc)


# ============================================================================
# Helper Functions
# ============================================================================


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
# Tile Serving Endpoint
# ============================================================================


@router.get(
    "/tiles/{raster_id}/{z}/{x}/{y}.png",
    summary="Serve a tile for an asset (COG-backed).",
    description="Lightweight tile endpoint using rio-tiler; resolves COG URI from Mongo by rasterID.",
)
async def tile_png(
    raster_id: str = Path(..., description="UUID rasterID of the asset"),
    z: int = Path(..., description="Tile zoom level"),
    x: int = Path(..., description="Tile x coordinate"),
    y: int = Path(..., description="Tile y coordinate"),
    # Accept both snake_case and camelCase query params
    colormap_name: Optional[str] = Query(None, description="Colormap name (snake_case)"),
    colormapName: Optional[str] = Query(None, description="Colormap name (camelCase)"),
    colourMap: Optional[str] = Query(None, description="Colormap name (alternative)"),
    scale_min: Optional[float] = Query(None, description="Scale minimum (snake_case)"),
    scaleMin: Optional[float] = Query(None, description="Scale minimum (camelCase)"),
    min: Optional[float] = Query(None, alias="min", description="Scale minimum (short)"),
    scale_max: Optional[float] = Query(None, description="Scale maximum (snake_case)"),
    scaleMax: Optional[float] = Query(None, description="Scale maximum (camelCase)"),
    max: Optional[float] = Query(None, alias="max", description="Scale maximum (short)"),
) -> Response:
    """Serve a PNG tile for a raster asset with proper transparency and colour mapping."""
    # Resolve query params (accept multiple naming conventions)
    resolved_colormap = colormap_name or colormapName or colourMap or "viridis"
    resolved_scale_min = scale_min if scale_min is not None else (scaleMin if scaleMin is not None else min)
    resolved_scale_max = scale_max if scale_max is not None else (scaleMax if scaleMax is not None else max)

    # Fetch asset by rasterID and validate colourmap
    repo = AssetRepository()
    asset = repo.get_asset_by_raster_id(raster_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    cmap_def = cmap.get(resolved_colormap)
    if cmap_def is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown colourmap: {resolved_colormap}"
        )

    try:
        _log_gcs_visibility(asset.storage.cog.uri)
        _log_rasterio_runtime(asset.storage.cog.uri)
        with COGReader(input=asset.storage.cog.uri) as src:  # type: ignore[call-arg]
            tile = src.tile(x, y, z, tilesize=256)
            arr = tile.data[0]
            
            # Build mask for valid data
            valid_mask = _build_valid_mask(arr, tile.mask[0], asset.raster.nodata)
            if not valid_mask.any():
                raise TileOutsideBounds()
            
            # Determine rescale range and apply to data
            vmin, vmax = _determine_rescale_range(
                arr, valid_mask, resolved_scale_min, resolved_scale_max,
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
        logger.warning("Tile outside bounds for raster_id=%s, z=%d, x=%d, y=%d", raster_id, z, x, y)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tile outside bounds")
    except Exception as exc:
        logger.error("Tile render failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tile render failed: {exc}"
        ) from exc

    return Response(content, media_type="image/png")
