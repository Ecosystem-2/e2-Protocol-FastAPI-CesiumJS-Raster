"""CZML billboard visualisation generator."""

from __future__ import annotations

from typing import Any

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_point import export_point_czml


def export_billboard_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    centroid: dict[str, float],
    grouped_stats: dict[str, list]
) -> list[dict[str, Any]]:
    """
    Export as billboard markers.
    
    Currently delegates to point export.
    Future: Could use custom billboard images.
    """
    return export_point_czml(selection, options, vmin, vmax, centroid, grouped_stats)
