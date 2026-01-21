"""Tile serving endpoints: render PNG tiles from COG-backed climate index assets."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from rio_tiler.io import COGReader  # type: ignore[attr-defined]
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.models import ImageData

from app.climate_indices.repository import AssetRepository
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


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

