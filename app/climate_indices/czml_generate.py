"""CZML generation service for Cesium visualisation."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_bar import export_bar_czml
from app.climate_indices.czml_polygon import export_polygon_czml
from app.climate_indices.czml_time import period_midpoint_isos
from app.core.logging import get_logger

logger = get_logger(__name__)


def _visualisation_name_suffix(visualisation_type: str) -> str:
    """Return a display suffix for non-default CZML visualisation modes."""
    if visualisation_type == "bar":
        return " (Bar Chart)"
    if visualisation_type == "polygon2d":
        return " (2D Polygon)"
    return ""


class CZMLExportService:
    """Generate CZML documents from polygon selections."""

    @staticmethod
    def _determine_scale_range(
        values: list[float],
        scale_min: float | None,
        scale_max: float | None
    ) -> tuple[float, float]:
        """Determine min/max for colour scaling."""
        if scale_min is not None and scale_max is not None:
            return scale_min, scale_max

        if not values:
            return 0.0, 1.0

        vmin = float(np.min(values))
        vmax = float(np.max(values))

        # Guard against uniform data: colourmap_interpret requires vmin < vmax
        if vmin == vmax:
            vmax = vmin + max(abs(vmin) * 0.1, 0.5)

        return vmin, vmax

    @staticmethod
    def _group_statistics_by_time(polygons_with_stats: list) -> dict[str, list]:
        """Group all statistics from all polygons by index_type for temporal visualisation."""
        grouped = {}
        
        # Flatten all statistics from all polygons
        for poly_stats in polygons_with_stats:
            for stat in poly_stats.statistics:
                index_type = stat.index_type or "unknown"
                if index_type not in grouped:
                    grouped[index_type] = []
                grouped[index_type].append(stat)
        
        # Sort each group by time_range start if available
        for index_type in grouped:
            grouped[index_type].sort(
                key=lambda s: s.time_range.start if s.time_range and s.time_range.start else s.asset_ref
            )
        
        logger.info(f"Grouped statistics from {len(polygons_with_stats)} polygons into {len(grouped)} index types")
        for idx_type, stats in grouped.items():
            has_time = any(s.time_range and s.time_range.start for s in stats)
            logger.info(f"  {idx_type}: {len(stats)} periods, has_time_data={has_time}")
        
        return grouped

    @staticmethod
    def _create_document_packet(
        selection: PolygonSelectionRecord,
        options: CZMLExportOptions
    ) -> dict[str, Any]:
        """Create CZML document packet with clock settings if temporal data exists."""
        doc_packet = {
            "id": "document",
            "name": f"{selection.title}{_visualisation_name_suffix(options.visualisation_type)}",
            "version": "1.0",
            "description": selection.description or ""
        }
        
        # Add clock configuration if we have time ranges
        # Flatten all statistics from all polygons
        all_stats = []
        for poly in selection.polygons:
            all_stats.extend(poly.statistics)
        
        has_time_data = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in all_stats
        )
        
        if has_time_data:
            # Find overall time bounds
            all_starts = [
                s.time_range.start 
                for s in all_stats 
                if s.time_range and s.time_range.start
            ]
            all_ends = [
                s.time_range.end 
                for s in all_stats 
                if s.time_range and s.time_range.end
            ]
            
            midpoint_times = period_midpoint_isos(all_stats)

            if options.interpolation_mode == "interpolation" and midpoint_times:
                doc_packet["clock"] = {
                    "interval": f"{midpoint_times[0]}/{midpoint_times[-1]}",
                    "currentTime": midpoint_times[0],
                    "multiplier": 31536000,  # 1 year per second
                    "range": "LOOP_STOP",
                    "step": "SYSTEM_CLOCK_MULTIPLIER"
                }
            elif all_starts and all_ends:
                doc_packet["clock"] = {
                    "interval": f"{min(all_starts).isoformat()}/{max(all_ends).isoformat()}",
                    "currentTime": min(all_starts).isoformat(),
                    "multiplier": 31536000,  # 1 year per second
                    "range": "LOOP_STOP",
                    "step": "SYSTEM_CLOCK_MULTIPLIER"
                }
        
        return doc_packet

    def export(
        self,
        selection: PolygonSelectionRecord,
        options: CZMLExportOptions,
        index_type: str | None = None
    ) -> str:
        """
        Export selection as CZML JSON string.

        Delegates to type-specific exporters based on visualisation_type.
        
        Args:
            selection: The polygon selection with statistics
            options: Export configuration (colourmap, scale, etc.)
            index_type: Optional filter to export only one index type (ppet, wbgt, etc.)
                       If None, exports all index types together.
        """
        # Extract values for colour scaling from all polygons
        values = []
        for poly in selection.polygons:
            for stat in poly.statistics:
                # Filter by index_type if specified
                if index_type and stat.index_type != index_type:
                    continue
                val = getattr(stat, options.value_field)
                if val is not None:
                    values.append(val)

        vmin, vmax = self._determine_scale_range(
            values, options.scale_min, options.scale_max
        )

        # Group statistics by index type for temporal visualisation
        grouped_stats = self._group_statistics_by_time(selection.polygons)
        
        # Filter to single index_type if specified
        if index_type:
            if index_type not in grouped_stats:
                raise ValueError(f"No statistics found for index_type: {index_type}")
            grouped_stats = {index_type: grouped_stats[index_type]}
            logger.info(f"Filtered to single index_type: {index_type}")

        # Create document packet with clock settings
        doc_packet = self._create_document_packet(selection, options)
        
        # Update document name if filtering by index_type
        if index_type:
            type_suffix = _visualisation_name_suffix(options.visualisation_type)
            doc_packet["name"] = f"{selection.title} - {index_type.upper()}{type_suffix}"

        # Use first polygon's centroid for polygon visualisation positioning
        if not selection.polygons:
            raise ValueError("Selection has no polygons")
        
        centroid = selection.polygons[0].centroid

        # Delegate to type-specific exporter
        if options.visualisation_type == "bar":
            # Bar mode creates one bar PER POLYGON, each at its own centroid
            entity_packets = export_bar_czml(
                selection, options, vmin, vmax, index_type_filter=index_type
            )
        elif options.visualisation_type in {"polygon", "polygon2d"}:
            entity_packets = export_polygon_czml(
                selection, options, vmin, vmax, centroid, grouped_stats
            )
        else:
            raise ValueError(f"Unknown visualisation type: {options.visualisation_type}")

        # Combine document packet with entity packets
        packets = [doc_packet] + entity_packets

        return json.dumps(packets, indent=2)
