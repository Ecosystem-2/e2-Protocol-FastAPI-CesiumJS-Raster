"""CZML bar chart visualisation generator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_description import build_description_html, PeriodStats
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sampled_bar_height(stats_group: list, options: CZMLExportOptions) -> dict:
    """
    Build a sampled cylinder length property for interpolation mode.
    
    Adds samples at both period start AND end to hold value constant within each period,
    plus a far-future sample to keep the last value visible.
    """
    samples = []
    last_height = 0
    
    for stat in stats_group:
        if not stat.time_range or not stat.time_range.start:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        height = value * options.bar_height_multiplier
        last_height = height
        
        # Add sample at period START
        iso_start = stat.time_range.start.isoformat()
        samples.extend([iso_start, height])
        
        # Add sample at period END (minus 1 day) with same value
        if stat.time_range.end:
            end_time = stat.time_range.end - timedelta(days=1)
            iso_end = end_time.isoformat()
            samples.extend([iso_end, height])
    
    if not samples:
        return {"number": 0}
    
    # Add far-future sample to keep last value visible
    samples.extend(["2200-01-01T00:00:00Z", last_height])
    
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
    
    Adds samples at both period start AND end to hold colour constant within each period,
    plus a far-future sample to keep the last colour visible.
    """
    samples = []
    last_rgba = (128, 128, 128, 255)
    
    for stat in stats_group:
        if not stat.time_range or not stat.time_range.start:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        r, g, b, a = colourmap_interpret(
            vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
        )
        last_rgba = (r, g, b, a)
        
        # Add sample at period START
        iso_start = stat.time_range.start.isoformat()
        samples.extend([iso_start, r, g, b, a])
        
        # Add sample at period END (minus 1 day) with same colour
        if stat.time_range.end:
            end_time = stat.time_range.end - timedelta(days=1)
            iso_end = end_time.isoformat()
            samples.extend([iso_end, r, g, b, a])
    
    if not samples:
        return {"rgba": [128, 128, 128, 255]}
    
    # Add far-future sample to keep last colour visible
    samples.extend(["2200-01-01T00:00:00Z", last_rgba[0], last_rgba[1], last_rgba[2], last_rgba[3]])
    
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
        
        # Determine index_type label and polygon name
        index_type = stats_list[0].index_type or "unknown"
        poly_name = f"Poly{poly_idx + 1}"
        
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
            # Build list of PeriodStats for all periods
            all_periods = [
                PeriodStats(
                    start=s.time_range.start.strftime('%Y-%m-%d'),
                    end=s.time_range.end.strftime('%Y-%m-%d'),
                    mean=s.mean,
                    std=s.std,
                    min=s.min,
                    max=s.max,
                    count=s.count,
                    units=s.units or ''
                )
                for s in stats_list
                if s.time_range and s.time_range.start and s.time_range.end
            ]
            
            if options.interpolation_mode == "interpolation":
                # Create single entity with sampled (interpolated) properties
                entity_id = f"{selection.title}_{poly_name.replace(' ', '_')}_bar"
                
                sampled_height = _build_sampled_bar_height(stats_list, options)
                sampled_colour = _build_sampled_bar_colour(stats_list, options, vmin, vmax)
                
                starts = [s.time_range.start for s in stats_list if s.time_range and s.time_range.start]
                availability = f"{min(starts).isoformat()}/2200-01-01T00:00:00Z" if starts else None
                
                first_stat = stats_list[0]
                first_height = getattr(first_stat, options.value_field, 0) * options.bar_height_multiplier
                
                packet = {
                    "id": entity_id,
                    "name": f"{poly_name}",
                    "position": {"cartographicDegrees": [lon, lat, 0]},
                    "cylinder": {
                        "length": sampled_height,
                        "topRadius": bar_radius,
                        "bottomRadius": bar_radius * 1.2,  # Slightly wider base for stability
                        "material": {"solidColor": {"color": sampled_colour}},
                        "outline": True,
                        "outlineColor": {"rgba": [40, 40, 40, 255]},
                        "outlineWidth": 2,
                        "shadows": "ENABLED"
                    },
                    "description": build_description_html(
                        index_type=f"{poly_name} - {index_type}",
                        stat=first_stat,
                        height=first_height,
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
                    r, g, b, a = colourmap_interpret(
                        vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                    )
                    
                    entity_id = f"{selection.title}_{poly_name.replace(' ', '_')}_bar_{period_idx}"
                    availability = f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                    time_start = stat.time_range.start.strftime('%Y-%m-%d')
                    time_end = stat.time_range.end.strftime('%Y-%m-%d')
                    
                    packet = {
                        "id": entity_id,
                        "name": f"{poly_name} ({time_start})",
                        "availability": availability,
                        "position": {"cartographicDegrees": [lon, lat, 0]},
                        "cylinder": {
                            "length": height,
                            "topRadius": bar_radius,
                            "bottomRadius": bar_radius * 1.2,
                            "material": {"solidColor": {"color": {"rgba": [r, g, b, a]}}},
                            "outline": True,
                            "outlineColor": {"rgba": [40, 40, 40, 255]},
                            "outlineWidth": 2,
                            "shadows": "ENABLED"
                        },
                        "description": build_description_html(
                            index_type=f"{poly_name} - {index_type}",
                            stat=stat,
                            height=height,
                            time_start=time_start,
                            time_end=time_end,
                            all_periods=all_periods
                        )
                    }
                    packets.append(packet)
                    logger.info(f"    Created step bar: {entity_id}")
        else:
            # No temporal data - create single static entity
            entity_id = f"{selection.title}_{poly_name.replace(' ', '_')}_bar"
            first_stat = stats_list[0]
            value = getattr(first_stat, options.value_field)
            
            if value is not None:
                height = value * options.bar_height_multiplier
                r, g, b, a = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                
                packet = {
                    "id": entity_id,
                    "name": poly_name,
                    "position": {"cartographicDegrees": [lon, lat, 0]},
                    "cylinder": {
                        "length": height,
                        "topRadius": bar_radius,
                        "bottomRadius": bar_radius * 1.2,
                        "material": {"solidColor": {"color": {"rgba": [r, g, b, a]}}},
                        "outline": True,
                        "outlineColor": {"rgba": [40, 40, 40, 255]},
                        "outlineWidth": 2,
                        "shadows": "ENABLED"
                    },
                    "description": build_description_html(
                        index_type=f"{poly_name} - {index_type}",
                        stat=first_stat,
                        height=height
                    )
                }
                packets.append(packet)
                logger.info(f"    Created static bar: {entity_id}")

    return packets
