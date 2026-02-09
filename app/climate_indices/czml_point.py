"""CZML point visualisation generator."""

from __future__ import annotations

from typing import Any

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def export_point_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    centroid: dict[str, float],
    grouped_stats: dict[str, list]
) -> list[dict[str, Any]]:
    """Export as point entities at polygon centroid with temporal animation support."""
    
    packets = []

    # Create entities - separate entity for each time period
    for index_type, stats_group in grouped_stats.items():
        logger.info(f"Creating point(s) for {index_type} with {len(stats_group)} time periods")
        
        # Check if we have temporal data
        has_temporal = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in stats_group
        )
        
        if has_temporal:
            # Create SEPARATE entity for EACH time period
            for period_idx, stat in enumerate(stats_group):
                value = getattr(stat, options.value_field)
                if value is None or not stat.time_range or not stat.time_range.start or not stat.time_range.end:
                    continue
                
                r, g, b, a = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                
                entity_id = f"{selection.name}_{index_type.replace(' ', '_')}_{period_idx}"
                availability = f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                time_label = stat.time_range.start.strftime('%Y-%m-%d')
                
                packet = {
                    "id": entity_id,
                    "name": f"{index_type} ({time_label})",
                    "availability": availability,
                    "position": {"cartographicDegrees": [centroid["lon"], centroid["lat"], 0]},
                    "point": {
                        "pixelSize": options.point_size,
                        "color": {"rgba": [r, g, b, a]},
                        "outlineColor": {"rgba": [255, 255, 255, 200]},
                        "outlineWidth": 1
                    }
                }
                
                if options.show_labels:
                    packet["label"] = {
                        "text": f"{value:.2f} {stat.units or ''}",
                        "font": "14pt sans-serif",
                        "fillColor": {"rgba": [255, 255, 255, 255]},
                        "outlineColor": {"rgba": [0, 0, 0, 255]},
                        "outlineWidth": 2,
                        "pixelOffset": {"cartesian2": [0, -20]},
                        "style": "FILL_AND_OUTLINE"
                    }
                
                packet["description"] = (
                    f"<div style='color: #1e293b; background: white; padding: 10px;'>"
                    f"<p><strong>{index_type}</strong></p>"
                    f"<p><strong>Period: {time_label}</strong></p>"
                    f"<p>Mean: {stat.mean:.2f} {stat.units or ''}</p>"
                    f"<p>Min: {stat.min:.2f}, Max: {stat.max:.2f}</p>"
                    f"<p>Std Dev: {stat.std:.2f}</p>"
                    f"<p>Pixel Count: {stat.count}</p>"
                    f"</div>"
                )
                
                packets.append(packet)
                logger.info(f"  Created entity {entity_id} for {availability}")
        else:
            # No temporal data - create single static entity
            entity_id = f"{selection.name}_{index_type.replace(' ', '_')}"
            first_stat = stats_group[0]
            value = getattr(first_stat, options.value_field)
            
            if value is not None:
                r, g, b, a = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                
                packet = {
                    "id": entity_id,
                    "name": index_type,
                    "position": {"cartographicDegrees": [centroid["lon"], centroid["lat"], 0]},
                    "point": {
                        "pixelSize": options.point_size,
                        "color": {"rgba": [r, g, b, a]},
                        "outlineColor": {"rgba": [255, 255, 255, 200]},
                        "outlineWidth": 1
                    }
                }
                
                if options.show_labels:
                    packet["label"] = {
                        "text": f"{value:.2f} {first_stat.units or ''}",
                        "font": "14pt sans-serif",
                        "fillColor": {"rgba": [255, 255, 255, 255]},
                        "outlineColor": {"rgba": [0, 0, 0, 255]},
                        "outlineWidth": 2,
                        "pixelOffset": {"cartesian2": [0, -20]},
                        "style": "FILL_AND_OUTLINE"
                    }
                
                packet["description"] = (
                    f"<div style='color: #1e293b; background: white; padding: 10px;'>"
                    f"<p><strong>{index_type}</strong></p>"
                    f"<p>Mean: {first_stat.mean:.2f} {first_stat.units or ''}</p>"
                    f"<p>Min: {first_stat.min:.2f}, Max: {first_stat.max:.2f}</p>"
                    f"<p>Std Dev: {first_stat.std:.2f}</p>"
                    f"<p>Pixel Count: {first_stat.count}</p>"
                    f"</div>"
                )
                
                packets.append(packet)
                logger.info(f"  Created static entity {entity_id}")

    return packets
