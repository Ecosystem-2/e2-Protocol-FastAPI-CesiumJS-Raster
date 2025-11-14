from __future__ import annotations

from typing import Sequence, Tuple

import matplotlib

__all__ = ["colourmap_interpret", "colormap_interpret"]


def colourmap_interpret(
    vmin: float = 0.0,
    vmax: float = 1.0,
    *,
    value: float = 0.5,
    colourmap: str = "Spectral",
) -> Tuple[int, int, int, int]:
    """
    Convert a numeric value into an RGBA colour taken from a named Matplotlib colourmap.

    Args:
        vmin: Minimum value represented by the colour scale.
        vmax: Maximum value represented by the colour scale.
        value: Concrete value to sample from the colourmap.
        colourmap: Any Matplotlib colourmap name; see
            https://matplotlib.org/stable/tutorials/colors/colormaps.html

    Returns:
        Tuple of (R, G, B, A) integers in the 0-255 range.
    """
    if vmin >= vmax:
        raise ValueError("vmin must be smaller than vmax to form a valid range.")

    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    cmap = matplotlib.cm.get_cmap(colourmap)
    rgba: Sequence[int] = cmap(norm(value), bytes=True)
    return tuple(int(channel) for channel in rgba)


def colormap_interpret(
    vmin: float = 0.0,
    vmax: float = 1.0,
    v: float = 0.5,
    colormap: str = "Spectral",
) -> Tuple[int, int, int, int]:
    """
    American-English alias retained for backwards compatibility.

    Prefer :func:`colourmap_interpret`.
    """
    return colourmap_interpret(vmin=vmin, vmax=vmax, value=v, colourmap=colormap)
