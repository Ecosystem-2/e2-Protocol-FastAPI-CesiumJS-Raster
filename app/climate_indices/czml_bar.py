"""CZML bar chart visualisation generator."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_description import build_description_html
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sampled_bar_height(stats_group: list, options: CZMLExportOptions) -> dict:
    """Build a sampled cylinder length property for interpolation mode."""
    samples = []
    for stat in stats_group:
        if not stat.time_range or not stat.time_range.start:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        height = value * options.bar_height_multiplier
        iso_time = stat.time_range.start.isoformat()
        samples.extend([iso_time, height])
    
    if not samples:
        return {"number": 0}
    
    return {
        "number": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


def _build_sampled_bar_colour(
    stats_group: list,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float
) -> dict:
    """Build a sampled colour property for bar interpolation mode."""
    samples = []
    
    for stat in stats_group:
        if not stat.time_range or not stat.time_range.start:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        r, g, b, a = colourmap_interpret(
            vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
        )
        iso_time = stat.time_range.start.isoformat()
        samples.extend([iso_time, r, g, b, a])
    
    if not samples:
        return {"rgba": [128, 128, 128, 255]}
    
    return {
        "rgba": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


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
            # Branch based on interpolation mode
            if options.interpolation_mode == "interpolation":
                # Create single entity with sampled (interpolated) properties
                entity_id = f"{selection.title}_{index_type.replace(' ', '_')}_bar"
                
                # Build sampled properties
                sampled_height = _build_sampled_bar_height(stats_group, options)
                sampled_colour = _build_sampled_bar_colour(stats_group, options, vmin, vmax)
                
                # Determine availability from first to last period
                starts = [s.time_range.start for s in stats_group if s.time_range and s.time_range.start]
                ends = [s.time_range.end for s in stats_group if s.time_range and s.time_range.end]
                
                availability = None
                if starts and ends:
                    availability = f"{min(starts).isoformat()}/{max(ends).isoformat()}"
                
                first_stat = stats_group[0] if stats_group else None
                first_height = getattr(first_stat, options.value_field, 0) * options.bar_height_multiplier if first_stat else 0
                time_label = first_stat.time_range.start.strftime('%Y-%m-%d') if first_stat and first_stat.time_range and first_stat.time_range.start else None
                
                packet = {
                    "id": entity_id,
                    "name": f"{index_type} (Interpolated)",
                    "position": {"cartographicDegrees": [lon, lat, 0]},
                    "cylinder": {
                        "length": sampled_height,
                        "topRadius": 500,
                        "bottomRadius": 500,
                        "material": {
                            "solidColor": {"color": sampled_colour}
                        },
                        "outline": True,
                        "outlineColor": {"rgba": [255, 255, 255, 200]}
                    },
                    "description": build_description_html(
                        index_type=index_type,
                        stat=first_stat,
                        height=first_height,
                        time_label=f"{time_label} (interpolated)" if time_label else "(interpolated)"
                    )
                }
                
                if availability:
                    packet["availability"] = availability
                
                packets.append(packet)
                logger.info(f"  Created interpolated bar entity {entity_id} with {len(stats_group)} samples")
            else:
                # Step mode: Create SEPARATE entity for EACH time period
                for period_idx, stat in enumerate(stats_group):
                    value = getattr(stat, options.value_field)
                    if value is None or not stat.time_range or not stat.time_range.start or not stat.time_range.end:
                        continue
                    
                    height = value * options.bar_height_multiplier
                    r, g, b, a = colourmap_interpret(
                        vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                    )
                    
                    entity_id = f"{selection.title}_{index_type.replace(' ', '_')}_bar_{period_idx}"
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
                        "description": build_description_html(
                            index_type=index_type,
                            stat=stat,
                            height=height,
                            time_label=time_label
                        )
                    }
                    
                    packets.append(packet)
                    logger.info(f"  Created step bar entity {entity_id} for {availability}: height={height:.0f}m")
        else:
            # No temporal data - create single static entity
            entity_id = f"{selection.title}_{index_type.replace(' ', '_')}_bar"
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
                    "description": build_description_html(
                        index_type=index_type,
                        stat=first_stat,
                        height=height
                    )
                }
                
                packets.append(packet)
                logger.info(f"  Created static entity {entity_id}: height={height:.0f}m")

    return packets
