from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import rasterio
from PIL import Image


@lru_cache(maxsize=32)
def render_png(path: str, colormap: str, palette: tuple[str, ...] | None = None) -> bytes:
    raster_path = Path(path)
    if not raster_path.is_file():
        raise FileNotFoundError(f"Raster not found: {raster_path}")

    with rasterio.open(raster_path) as src:
        data = src.read(1, masked=True)

    array = np.array(data, dtype=float)
    mask = np.ma.getmaskarray(data)
    if palette:
        num_classes = len(palette)
        boundaries = np.arange(0.5, num_classes + 1.5, 1.0)
        cmap = mcolors.ListedColormap(palette)
        norm = mcolors.BoundaryNorm(boundaries, cmap.N)
        rgba = (cmap(norm(array)) * 255).astype(np.uint8)
        valid_mask = (~mask) & (array >= 1) & (array <= num_classes)
        rgba[..., 3] = np.where(valid_mask, rgba[..., 3], 0)
    else:
        valid = array[~mask]
        if valid.size:
            vmin = float(np.nanpercentile(valid, 2))
            vmax = float(np.nanpercentile(valid, 98))
        else:
            vmin, vmax = 0.0, 1.0
        if vmax == vmin:
            vmax = vmin + 1.0
        normalised = np.clip((array - vmin) / (vmax - vmin), 0.0, 1.0)
        cmap = plt.get_cmap(colormap)
        rgba = (cmap(normalised) * 255).astype(np.uint8)
        rgba[..., 3] = np.where(mask, 0, rgba[..., 3])

    image = Image.fromarray(rgba)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
