"""CZML generation service for Cesium visualisation."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from shapely.geometry import shape

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_point import export_point_czml
from app.climate_indices.czml_bar import export_bar_czml
from app.climate_indices.czml_billboard import export_billboard_czml
from app.core.logging import get_logger

logger = get_logger(__name__)


class CZMLExportService:
    """Generate CZML documents from polygon selections."""

    @staticmethod
    def _compute_centroid(polygon_geojson: dict) -> dict[str, float]:
        """Compute polygon centroid using Shapely."""
        geom = shape(polygon_geojson)
        centroid = geom.centroid
        return {"lon": centroid.x, "lat": centroid.y}

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

        return float(np.min(values)), float(np.max(values))

    @staticmethod
    def _group_statistics_by_time(statistics: list) -> dict[str, list]:
        """Group statistics by index_type for temporal visualisation."""
        grouped = {}
        for stat in statistics:
            index_type = stat.index_type or "unknown"
            if index_type not in grouped:
                grouped[index_type] = []
            grouped[index_type].append(stat)
        
        # Sort each group by time_range start if available
        for index_type in grouped:
            grouped[index_type].sort(
                key=lambda s: s.time_range.start if s.time_range and s.time_range.start else s.asset_id
            )
        
        logger.info(f"Grouped {len(statistics)} statistics into {len(grouped)} index types")
        for idx_type, stats in grouped.items():
            has_time = any(s.time_range and s.time_range.start for s in stats)
            logger.info(f"  {idx_type}: {len(stats)} periods, has_time_data={has_time}")
        
        return grouped

    @staticmethod
    def _create_document_packet(
        selection: PolygonSelectionRecord,
        visualisation_type: str
    ) -> dict[str, Any]:
        """Create CZML document packet with clock settings if temporal data exists."""
        doc_packet = {
            "id": "document",
            "name": f"{selection.name}{' (Bar Chart)' if visualisation_type == 'bar' else ''}",
            "version": "1.0",
            "description": selection.description or ""
        }
        
        # Add clock configuration if we have time ranges
        has_time_data = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in selection.statistics
        )
        
        if has_time_data:
            # Find overall time bounds
            all_starts = [
                s.time_range.start 
                for s in selection.statistics 
                if s.time_range and s.time_range.start
            ]
            all_ends = [
                s.time_range.end 
                for s in selection.statistics 
                if s.time_range and s.time_range.end
            ]
            
            if all_starts and all_ends:
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
        options: CZMLExportOptions
    ) -> str:
        """
        Export selection as CZML JSON string.

        Delegates to type-specific exporters based on visualisation_type.
        """
        # Extract values for colour scaling
        values = [
            getattr(stat, options.value_field)
            for stat in selection.statistics
            if getattr(stat, options.value_field) is not None
        ]

        vmin, vmax = self._determine_scale_range(
            values, options.scale_min, options.scale_max
        )

        # Group statistics by index type for temporal visualisation
        grouped_stats = self._group_statistics_by_time(selection.statistics)

        # Create document packet with clock settings
        doc_packet = self._create_document_packet(selection, options.visualisation_type)

        # Compute centroid once
        centroid = selection.centroid or self._compute_centroid(
            selection.polygon.model_dump()
        )

        # Delegate to type-specific exporter
        if options.visualisation_type == "point":
            entity_packets = export_point_czml(
                selection, options, vmin, vmax, centroid, grouped_stats
            )
        elif options.visualisation_type == "bar":
            entity_packets = export_bar_czml(
                selection, options, vmin, vmax, centroid, grouped_stats
            )
        elif options.visualisation_type == "billboard":
            entity_packets = export_billboard_czml(
                selection, options, vmin, vmax, centroid, grouped_stats
            )
        else:
            raise ValueError(f"Unknown visualisation type: {options.visualisation_type}")

        # Combine document packet with entity packets
        packets = [doc_packet] + entity_packets

        return json.dumps(packets, indent=2)
