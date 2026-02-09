"""CZML bar chart visualisation generator."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def export_bar_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    centroid: dict[str, float],
    grouped_stats: dict[str, list]
) -> list[dict[str, Any]]:
    """Export as 3D bar chart using cylinders with temporal animation support."""
    
    packets = []

    # Create one bar per index type with time-varying height and colour
    num_index_types = len(grouped_stats)
    radius = 0.01  # degrees (~1km)

    for idx, (index_type, stats_group) in enumerate(grouped_stats.items()):
        logger.info(f"Creating bar(s) for {index_type} with {len(stats_group)} time periods")
        
        # Position bars in circle around centroid
        angle = (2 * np.pi * idx) / max(num_index_types, 1)
        lon = centroid["lon"] + radius * np.cos(angle)
        lat = centroid["lat"] + radius * np.sin(angle)

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
                
                height = value * options.bar_height_multiplier
                r, g, b, a = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                
                entity_id = f"{selection.name}_{index_type.replace(' ', '_')}_bar_{period_idx}"
                availability = f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                
                time_label = stat.time_range.start.strftime('%Y-%m-%d')
                
                packet = {
                    "id": entity_id,
                    "name": f"{index_type} ({time_label})",
                    "availability": availability,
                    "position": {"cartographicDegrees": [lon, lat, 0]},
                    "cylinder": {
                        "length": height,
                        "topRadius": 500,
                        "bottomRadius": 500,
                        "material": {
                            "solidColor": {"color": {"rgba": [r, g, b, a]}}
                        },
                        "outline": True,
                        "outlineColor": {"rgba": [255, 255, 255, 200]}
                    },
                    "description": (
                        f"<div style='color: #1e293b; background: white; padding: 10px;'>"
                        f"<p><strong>{index_type}</strong></p>"
                        f"<p><strong>Period: {time_label}</strong></p>"
                        f"<p>Mean: {stat.mean:.2f} {stat.units or ''}</p>"
                        f"<p>Min: {stat.min:.2f}, Max: {stat.max:.2f}</p>"
                        f"<p>Std Dev: {stat.std:.2f}</p>"
                        f"<p>Pixel Count: {stat.count}</p>"
                        f"</div>"
                    )
                }
                
                packets.append(packet)
                logger.info(f"  Created entity {entity_id} for {availability}: height={height:.0f}m")
        else:
            # No temporal data - create single static entity
            entity_id = f"{selection.name}_{index_type.replace(' ', '_')}_bar"
            first_stat = stats_group[0]
            value = getattr(first_stat, options.value_field)
            
            if value is not None:
                height = value * options.bar_height_multiplier
                r, g, b, a = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                
                packet = {
                    "id": entity_id,
                    "name": index_type,
                    "position": {"cartographicDegrees": [lon, lat, 0]},
                    "cylinder": {
                        "length": height,
                        "topRadius": 500,
                        "bottomRadius": 500,
                        "material": {
                            "solidColor": {"color": {"rgba": [r, g, b, a]}}
                        },
                        "outline": True,
                        "outlineColor": {"rgba": [255, 255, 255, 200]}
                    },
                    "description": (
                        f"<div style='color: #1e293b; background: white; padding: 10px;'>"
                        f"<p><strong>{index_type}</strong></p>"
                        f"<p>Mean: {first_stat.mean:.2f} {first_stat.units or ''}</p>"
                        f"<p>Min: {first_stat.min:.2f}, Max: {first_stat.max:.2f}</p>"
                        f"<p>Std Dev: {first_stat.std:.2f}</p>"
                        f"<p>Pixel Count: {first_stat.count}</p>"
                        f"</div>"
                    )
                }
                
                packets.append(packet)
                logger.info(f"  Created static entity {entity_id}: height={height:.0f}m")

    return packets
