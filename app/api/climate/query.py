from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import numpy as np
import rasterio
from fastapi import HTTPException
from rasterio.mask import mask
from shapely.geometry import shape

from app.core.logging import get_logger

logger = get_logger(__name__)


def zonal_stats_from_cog(cog_path: str, polygon_geojson: Dict[str, Any]) -> Dict[str, Any]:
    """Clip COG to polygon and return simple stats."""
    try:
        geom = shape(polygon_geojson)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid polygon: {exc}") from exc

    try:
        with rasterio.open(cog_path) as src:
            clipped, transform = mask(src, [geom], crop=True, nodata=src.nodata)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="COG not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Raster clip failed: {exc}") from exc

    data = clipped[0]
    data = data.astype(float)
    data[data == src.nodata] = np.nan
    vals = data[~np.isnan(data)]
    if vals.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None, "median": None}

    return {
        "count": int(vals.size),
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals)),
        "median": float(np.median(vals)),
    }


def extract_pixels_from_cog(
    cog_path: str,
    polygon_geojson: Dict[str, Any]
) -> Tuple[np.ndarray, rasterio.Affine, float | None]:
    """Extract raw pixel values from COG within polygon bounds.
    
    Returns:
        Tuple of (clipped_data_array, transform, nodata_value)
    """
    try:
        geom = shape(polygon_geojson)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid polygon: {exc}") from exc

    try:
        with rasterio.open(cog_path) as src:
            clipped, transform = mask(src, [geom], crop=True, nodata=src.nodata, filled=False)
            nodata = src.nodata
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="COG not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Raster clip failed: {exc}") from exc

    return clipped[0], transform, nodata
