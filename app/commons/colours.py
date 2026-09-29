# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import List, Sequence, Tuple

import matplotlib

__all__ = [
    "colourmap_interpret",
    "colormap_interpret",
    "list_available_colourmaps",
    "get_colourmap_categories",
]


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


def list_available_colourmaps(category: str | None = None) -> List[str]:
    """
    List all available Matplotlib colourmap names.

    Args:
        category: Optional filter by category. One of:
            - "perceptually_uniform" (viridis, plasma, inferno, magma, cividis)
            - "sequential" (Blues, Greens, Oranges, Reds, etc.)
            - "diverging" (RdYlGn, coolwarm, RdBu, etc.)
            - "cyclic" (twilight, twilight_shifted, hsv)
            - "qualitative" (Pastel1, Set1, tab10, etc.)
            - "miscellaneous" (terrain, ocean, gist_earth, etc.)
            - None (returns all colourmaps)

    Returns:
        Sorted list of colourmap names.
    """
    categories = get_colourmap_categories()
    
    if category is not None:
        if category not in categories:
            raise ValueError(
                f"Unknown category '{category}'. "
                f"Valid categories: {list(categories.keys())}"
            )
        return sorted(categories[category])
    
    # Return all unique colourmap names
    all_cmaps = set()
    for cmaps in categories.values():
        all_cmaps.update(cmaps)
    return sorted(all_cmaps)


def get_colourmap_categories() -> dict[str, List[str]]:
    """
    Return colourmaps organised by category.

    Categories follow Matplotlib's official classification:
    https://matplotlib.org/stable/tutorials/colors/colormaps.html

    Returns:
        Dictionary mapping category names to lists of colourmap names.
    """
    return {
        "perceptually_uniform": [
            "viridis", "plasma", "inferno", "magma", "cividis"
        ],
        "sequential": [
            "Greys", "Purples", "Blues", "Greens", "Oranges", "Reds",
            "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu",
            "GnBu", "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn"
        ],
        "sequential_multi": [
            "binary", "gist_yarg", "gist_gray", "gray", "bone",
            "pink", "spring", "summer", "autumn", "winter", "cool",
            "Wistia", "hot", "afmhot", "gist_heat", "copper"
        ],
        "diverging": [
            "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu", "RdYlBu",
            "RdYlGn", "Spectral", "coolwarm", "bwr", "seismic"
        ],
        "cyclic": [
            "twilight", "twilight_shifted", "hsv"
        ],
        "qualitative": [
            "Pastel1", "Pastel2", "Paired", "Accent", "Dark2",
            "Set1", "Set2", "Set3", "tab10", "tab20", "tab20b", "tab20c"
        ],
        "miscellaneous": [
            "flag", "prism", "ocean", "gist_earth", "terrain",
            "gist_stern", "gnuplot", "gnuplot2", "CMRmap",
            "cubehelix", "brg", "gist_rainbow", "rainbow", "jet",
            "turbo", "nipy_spectral", "gist_ncar"
        ]
    }
