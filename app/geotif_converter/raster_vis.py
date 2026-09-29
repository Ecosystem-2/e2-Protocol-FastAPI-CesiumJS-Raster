# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import Any, Tuple
from pathlib import Path
import logging

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from app.geotif_converter.raster_io import read_geotiff
logger = logging.getLogger(__name__)

__all__ = ["suggest_colour_limits", "plot_raster", "plot_raster_discrete"]


def suggest_colour_limits(
    raster: xr.DataArray,
    *,
    lower_percentile: float = 2,
    upper_percentile: float = 98,
) -> Tuple[float, float]:
    try:
        q = raster.quantile([lower_percentile / 100.0, upper_percentile / 100.0], skipna=True)
        vmin = float(q.isel(quantile=0).item())
        vmax = float(q.isel(quantile=1).item())
    except Exception:
        arr = np.asarray(raster.values)
        vmin = float(np.nanpercentile(arr, lower_percentile))
        vmax = float(np.nanpercentile(arr, upper_percentile))

    if not np.isfinite(vmin):
        vmin = float(np.nanmin(raster.values))
    if not np.isfinite(vmax):
        vmax = float(np.nanmax(raster.values))

    return vmin, vmax


def plot_raster(
    raster: xr.DataArray,
    *,
    band: int | None = None,
    cmap: str = "viridis_r",
    robust: bool = False,
    lower_percentile: float = 2.0,
    upper_percentile: float = 98.0,
    figsize: tuple[int, int] = (8, 6),
    add_colorbar: bool = True,
    title: str | None = None,
    save_path: str | Path | None = None,
    dpi: int = 300,
    transparent: bool = False,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot a raster with sensible default colour scaling.

    - If vmin/vmax are not provided and ``robust`` is True, compute them from
      the given percentiles to avoid outlier-driven black/white renders.
    - If the raster has a "band" dimension and no band is specified, the first
      band is shown.
    """
    da = raster
    if "band" in da.dims:
        if band is None:
            da = da.isel(band=0)
        else:
            # GeoTIFF bands are commonly 1-based; accept either
            idx = band if 0 <= band < da.sizes["band"] else band - 1
            da = da.isel(band=idx)

    if robust:
        vmin, vmax = suggest_colour_limits(da, lower_percentile=lower_percentile, upper_percentile=upper_percentile)
    else:
        vmin, vmax = float(da.min(skipna=True)), float(da.max(skipna=True))


    fig, ax = plt.subplots(figsize=figsize)
    im = da.plot.imshow(ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, add_colorbar=False)
    if add_colorbar:
        cbar = fig.colorbar(im, ax=ax, shrink=0.5)
        cbar.ax.set_ylabel(da.attrs.get("units", ""))

    ax.set_xlabel(da.coords.get("x").name if "x" in da.coords else "x")
    ax.set_ylabel(da.coords.get("y").name if "y" in da.coords else "y")
    if title:
        ax.set_title(title)
    else:
        name = da.name or "raster"
        ax.set_title(f"{name} | cmap={cmap} | vmin={vmin:.3g}, vmax={vmax:.3g}")

    ax.set_aspect("equal")
    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight", transparent=transparent)

    return fig, ax


# Discrete categorical plotting (e.g., 1..6 threat levels)
def plot_raster_discrete(
    raster: xr.DataArray,
    *,
    band: int | None = None,
    levels: tuple[int, ...] | list[int] = (1, 2, 3, 4, 5, 6),
    labels: tuple[str, ...] | list[str] | None = (
        "Low Threat",
        "Elevated Threat",
        "Moderate Threat",
        "High Threat",
        "Extreme Threat",
        "Critical Threat",
    ),
    colours: tuple[str, ...] | list[str] | None = (
        "limegreen",  # 1
        "yellow",     # 2
        "orange",     # 3
        "red",        # 4
        "black",      # 5
        "magenta",    # 6
    ),
    alpha: float = 0.85,
    figsize: tuple[int, int] = (8, 6),
    add_colorbar: bool = True,
    title: str | None = None,
    save_path: str | Path | None = None,
    dpi: int = 300,
    transparent: bool = False,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot discrete categories with fixed colours for integer levels.

    Non-matching or missing values are rendered transparent.
    """
    da = raster
    if "band" in da.dims:
        if band is None:
            da = da.isel(band=0)
        else:
            idx = band if 0 <= band < da.sizes["band"] else band - 1
            da = da.isel(band=idx)

    # Round to nearest integer category and mask out-of-range values
    # Keep float dtype so NaNs remain representable (avoid NaN→int cast warnings)
    da_cat = xr.apply_ufunc(np.rint, da, dask="allowed")
    da_cat = da_cat.astype("float")
    levels_arr = np.array(sorted(levels))
    valid_mask = xr.apply_ufunc(np.isin, da_cat, levels_arr, dask="allowed")
    da_cat = da_cat.where(valid_mask)

    # Build a listed colormap with alpha and transparent NaNs
    if colours is None:
        colours = ("limegreen", "yellow", "orange", "red", "black", "magenta")
    rgba_colours = [mcolors.to_rgba(c, alpha=alpha) for c in colours]
    cmap = mcolors.ListedColormap(rgba_colours, name="threat_levels")
    cmap.set_bad((0, 0, 0, 0))  # transparent for NaNs

    # Boundaries centre bins on integer categories (e.g., 0.5..1.5 -> 1)
    bounds = [levels_arr[0] - 0.5] + [int(l) + 0.5 for l in levels_arr]
    norm = mcolors.BoundaryNorm(bounds, ncolors=cmap.N, clip=False)

    fig, ax = plt.subplots(figsize=figsize)
    im = da_cat.plot.imshow(ax=ax, cmap=cmap, norm=norm, add_colorbar=False)

    if add_colorbar:
        cbar = fig.colorbar(im, ax=ax, ticks=levels_arr, shrink=0.5)
        if labels is not None and len(labels) == len(levels_arr):
            cbar.ax.set_yticklabels(list(labels))
        cbar.ax.set_ylabel(da.attrs.get("units", ""))

    ax.set_xlabel(da.coords.get("x").name if "x" in da.coords else "x")
    ax.set_ylabel(da.coords.get("y").name if "y" in da.coords else "y")
    if title:
        ax.set_title(title)
    else:
        name = da.name or "raster"
        ax.set_title(f"{name} | discrete levels {tuple(levels_arr)}")

    ax.set_aspect("equal")
    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight", transparent=transparent)

    return fig, ax

# --- Test code ---
if __name__ == "__main__":
    raster = read_geotiff("data/Humid Heat Stress/geotif/ssp245_WBGT_Sun_2041_2070_Segama_River.tif")
    fig, ax = plot_raster(raster)

    plt.show()
    plt.close(fig)

