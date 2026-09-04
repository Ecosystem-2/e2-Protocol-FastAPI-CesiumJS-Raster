"""CZML bar chart visualisation generator."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_description import (
    build_description_html,
    build_entity_name,
    build_period_stats,
    build_polygon_title,
)
from app.climate_indices.czml_time import period_midpoint_iso, period_midpoint_isos
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sampled_bar_height(stats_group: list, options: CZMLExportOptions) -> dict:
    """
    Build a sampled cylinder length property for interpolation mode.
    
    Adds one sample at each period midpoint, so values represent the centre of
    each climatological period and interpolate smoothly between representative
    periods.
    """
    samples = []
    for stat in stats_group:
        sample_time = period_midpoint_iso(stat)
        if not sample_time:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        height = value * options.bar_height_multiplier
        samples.extend([sample_time, height])
    
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
    """
    Build a sampled colour property for bar interpolation mode.

    Adds one sample at each period midpoint, matching sampled height.
    """
    samples = []
    alpha = int(options.polygon_fill_opacity * 255)
    for stat in stats_group:
        sample_time = period_midpoint_iso(stat)
        if not sample_time:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue

        r, g, b, _ = colourmap_interpret(
            vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
        )
        samples.extend([sample_time, r, g, b, alpha])

    if not samples:
        return {"rgba": [128, 128, 128, alpha]}
    
    return {
        "rgba": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


def _build_sampled_bar_position(
    stats_group: list,
    options: CZMLExportOptions,
    lon: float,
    lat: float
) -> dict:
    """
    Build a sampled cartographicDegrees position so the cylinder centre
    stays at height/2 as the animated length changes.

    Format: [iso, lon, lat, z, iso, lon, lat, z, ...]
    """
    samples = []
    for stat in stats_group:
        sample_time = period_midpoint_iso(stat)
        if not sample_time:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue

        z = value * options.bar_height_multiplier / 2
        samples.extend([sample_time, lon, lat, z])

    if not samples:
        return {"cartographicDegrees": [lon, lat, 0]}

    return {
        "cartographicDegrees": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


def export_bar_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    index_type_filter: str | None = None
) -> list[dict[str, Any]]:
    """
    Export as 3D bar chart using cylinders - ONE BAR PER POLYGON.
    
    Each polygon gets its own bar positioned at its centroid.
    Height and colour represent the index value for that polygon.
    """
    packets = []
    
    num_polygons = len(selection.polygons)
    logger.info(f"Creating bar chart with {num_polygons} bars (one per polygon)")

    for poly_idx, poly in enumerate(selection.polygons):
        # Use polygon's own centroid for positioning
        centroid = poly.centroid
        lon = centroid["lon"]
        lat = centroid["lat"]
        
        # Filter statistics by index_type if specified
        stats_list = [
            s for s in poly.statistics
            if not index_type_filter or s.index_type == index_type_filter
        ]
        
        if not stats_list:
            logger.warning(f"  Polygon {poly_idx}: No statistics found")
            continue
        
        # Group by time for temporal animation
        stats_list.sort(
            key=lambda s: s.time_range.start if s.time_range and s.time_range.start else ""
        )
        
        # Determine index_type label and polygon name (use user-defined title if set)
        index_type = stats_list[0].index_type or "unknown"
        poly_name = build_polygon_title(poly.title, poly_idx)
        
        # Calculate dynamic radius with minimum threshold for visibility
        pixel_count = stats_list[0].count if stats_list else 100
        calculated_radius = pixel_count * options.bar_radius_multiplier
        bar_radius = max(calculated_radius, options.bar_minimum_radius)
        logger.info(
            f"  {poly_name}: radius={bar_radius:.0f}m "
            f"(pixels={pixel_count}, calculated={calculated_radius:.0f}, min={options.bar_minimum_radius})"
        )
        
        # Check if we have temporal data
        has_temporal = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in stats_list
        )
        
        if has_temporal:
            all_periods = build_period_stats(stats_list)
            
            if options.interpolation_mode == "interpolation":
                # Create single entity with sampled (interpolated) properties
                entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_bar"
                
                sampled_height = _build_sampled_bar_height(stats_list, options)
                sampled_colour = _build_sampled_bar_colour(stats_list, options, vmin, vmax)
                sampled_position = _build_sampled_bar_position(stats_list, options, lon, lat)
                
                midpoint_times = period_midpoint_isos(stats_list)
                availability = f"{midpoint_times[0]}/{midpoint_times[-1]}" if midpoint_times else None
                
                first_stat = stats_list[0]
                first_height = getattr(first_stat, options.value_field, 0) * options.bar_height_multiplier
                
                packet = {
                    "id": entity_id,
                    "name": build_entity_name(poly_name),
                    "position": sampled_position,
                    "cylinder": {
                        "length": sampled_height,
                        "topRadius": bar_radius,
                        "bottomRadius": bar_radius * 1.2,  # Slightly wider base for stability
                        "material": {"solidColor": {"color": sampled_colour}},
                        "outline": options.polygon_outline,
                        "outlineColor": {"rgba": [40, 40, 40, 255]},
                        "outlineWidth": 2,
                        "shadows": "ENABLED"
                    },
                    "description": build_description_html(
                        index_type=index_type,
                        stat=first_stat,
                        height=first_height,
                        entity_title=poly_name,
                        all_periods=all_periods,
                        is_interpolated=True
                    )
                }
                if availability:
                    packet["availability"] = availability
                
                packets.append(packet)
                logger.info(f"    Created interpolated bar: {entity_id}")
            else:
                # Step mode: Create SEPARATE entity for EACH time period
                for period_idx, stat in enumerate(stats_list):
                    value = getattr(stat, options.value_field)
                    if value is None or not stat.time_range or not stat.time_range.start or not stat.time_range.end:
                        continue
                    
                    height = value * options.bar_height_multiplier
                    r, g, b, _ = colourmap_interpret(
                        vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                    )
                    alpha = int(options.polygon_fill_opacity * 255)

                    entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_bar_{period_idx}"
                    availability = f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                    time_start = stat.time_range.start.strftime('%Y-%m-%d')
                    time_end = stat.time_range.end.strftime('%Y-%m-%d')

                    packet = {
                        "id": entity_id,
                        "name": build_entity_name(poly_name, time_start=time_start, time_end=time_end),
                        "availability": availability,
                        "position": {"cartographicDegrees": [lon, lat, height / 2]},
                        "cylinder": {
                            "length": height,
                            "topRadius": bar_radius,
                            "bottomRadius": bar_radius * 1.2,
                            "material": {"solidColor": {"color": {"rgba": [r, g, b, alpha]}}},
                            "outline": options.polygon_outline,
                            "outlineColor": {"rgba": [40, 40, 40, 255]},
                            "outlineWidth": 2,
                            "shadows": "ENABLED"
                        },
                        "description": build_description_html(
                            index_type=index_type,
                            stat=stat,
                            height=height,
                            entity_title=poly_name,
                            time_start=time_start,
                            time_end=time_end,
                            all_periods=all_periods
                        )
                    }
                    packets.append(packet)
                    logger.info(f"    Created step bar: {entity_id}")
        else:
            # No temporal data - create single static entity
            entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_bar"
            first_stat = stats_list[0]
            value = getattr(first_stat, options.value_field)
            
            if value is not None:
                height = value * options.bar_height_multiplier
                r, g, b, _ = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                alpha = int(options.polygon_fill_opacity * 255)

                packet = {
                    "id": entity_id,
                    "name": build_entity_name(poly_name),
                    "position": {"cartographicDegrees": [lon, lat, height / 2]},
                    "cylinder": {
                        "length": height,
                        "topRadius": bar_radius,
                        "bottomRadius": bar_radius * 1.2,
                        "material": {"solidColor": {"color": {"rgba": [r, g, b, alpha]}}},
                        "outline": options.polygon_outline,
                        "outlineColor": {"rgba": [40, 40, 40, 255]},
                        "outlineWidth": 2,
                        "shadows": "ENABLED"
                    },
                    "description": build_description_html(
                        index_type=index_type,
                        stat=first_stat,
                        height=height,
                        entity_title=poly_name
                    )
                }
                packets.append(packet)
                logger.info(f"    Created static bar: {entity_id}")

    return packets
