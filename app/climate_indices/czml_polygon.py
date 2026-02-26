"""CZML polygon visualisation generator with extruded height."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_description import build_description_html, PeriodStats
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def _flatten_polygon_coordinates(geometry: dict) -> list[float]:
    """
    Flatten GeoJSON polygon coordinates to CZML cartographicDegrees format.
    
    CZML expects: [lon1, lat1, height1, lon2, lat2, height2, ...]
    GeoJSON is: [[[lon1, lat1], [lon2, lat2], ...]]
    
    Only handles the exterior ring (first ring) for simplicity.
    """
    coords = geometry.get("coordinates", [])
    if not coords:
        return []
    
    # Handle Polygon vs MultiPolygon
    geom_type = geometry.get("type", "Polygon")
    if geom_type == "MultiPolygon":
        # For MultiPolygon, use first polygon's exterior ring
        if coords and coords[0]:
            exterior_ring = coords[0][0]
        else:
            return []
    else:
        # For Polygon, use first ring (exterior)
        exterior_ring = coords[0] if coords else []
    
    # Flatten to [lon, lat, height, lon, lat, height, ...]
    flattened = []
    for point in exterior_ring:
        lon = point[0]
        lat = point[1]
        height = point[2] if len(point) > 2 else 0
        flattened.extend([lon, lat, height])
    
    return flattened


def _build_sampled_height(stats_group: list, options: CZMLExportOptions) -> dict:
    """
    Build a sampled extrudedHeight property for interpolation mode.
    
    Format: [ISO_time_1, value_1, ISO_time_2, value_2, ...]
    
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
        
        height = value * options.polygon_height_multiplier
        last_height = height
        
        # Add sample at period START
        iso_start = stat.time_range.start.isoformat()
        samples.extend([iso_start, height])
        
        # Add sample at period END (minus 1 day to avoid overlap) with same value
        if stat.time_range.end:
            end_time = stat.time_range.end - timedelta(days=1)
            iso_end = end_time.isoformat()
            samples.extend([iso_end, height])
    
    if not samples:
        return {"number": 0}
    
    # Add far-future sample to keep last value visible (year 2200)
    samples.extend(["2200-01-01T00:00:00Z", last_height])
    
    return {
        "number": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


def _build_sampled_colour(
    stats_group: list,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float
) -> dict:
    """
    Build a sampled colour property for interpolation mode.
    
    Format: [ISO_time_1, r1, g1, b1, a1, ISO_time_2, r2, g2, b2, a2, ...]
    
    Adds samples at both period start AND end to hold colour constant within each period,
    plus a far-future sample to keep the last colour visible.
    """
    samples = []
    alpha = int(options.polygon_fill_opacity * 255)
    last_rgba = (128, 128, 128, alpha)
    
    for stat in stats_group:
        if not stat.time_range or not stat.time_range.start:
            continue
        value = getattr(stat, options.value_field)
        if value is None:
            continue
        
        r, g, b, _ = colourmap_interpret(
            vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
        )
        last_rgba = (r, g, b, alpha)
        
        # Add sample at period START
        iso_start = stat.time_range.start.isoformat()
        samples.extend([iso_start, r, g, b, alpha])
        
        # Add sample at period END (minus 1 day to avoid overlap) with same colour
        if stat.time_range.end:
            end_time = stat.time_range.end - timedelta(days=1)
            iso_end = end_time.isoformat()
            samples.extend([iso_end, r, g, b, alpha])
    
    if not samples:
        return {"rgba": [128, 128, 128, alpha]}
    
    # Add far-future sample to keep last colour visible (year 2200)
    samples.extend(["2200-01-01T00:00:00Z", last_rgba[0], last_rgba[1], last_rgba[2], last_rgba[3]])
    
    if not samples:
        return {"rgba": [128, 128, 128, alpha]}
    
    return {
        "rgba": samples,
        "interpolationAlgorithm": "LINEAR",
        "interpolationDegree": 1
    }


def _build_interpolated_polygon_packet(
    entity_id: str,
    name: str,
    geometry: dict,
    stats_group: list,
    options: CZMLExportOptions,
    index_type: str,
    vmin: float,
    vmax: float,
    centroid: dict[str, float]
) -> dict[str, Any]:
    """
    Build a single CZML polygon packet with sampled (interpolated) properties.
    
    Height and colour transition smoothly between time period start values.
    """
    positions = _flatten_polygon_coordinates(geometry)
    
    # Build sampled properties
    sampled_height = _build_sampled_height(stats_group, options)
    sampled_colour = _build_sampled_colour(stats_group, options, vmin, vmax)
    
    # Determine availability from first period to far future (so it stays visible)
    starts = [s.time_range.start for s in stats_group if s.time_range and s.time_range.start]
    
    availability = None
    if starts:
        # Extend to year 2200 so polygon stays visible after last data period
        availability = f"{min(starts).isoformat()}/2200-01-01T00:00:00Z"
    
    packet: dict[str, Any] = {
        "id": entity_id,
        "name": name,
        "polygon": {
            "positions": {
                "cartographicDegrees": positions
            },
            "height": 0,
            "extrudedHeight": sampled_height,
            "material": {
                "solidColor": {
                    "color": sampled_colour
                }
            },
            "outline": options.polygon_outline,
            "outlineColor": {"rgba": [255, 255, 255, 200]},
            "outlineWidth": 1,
            "closeTop": True,
            "closeBottom": True
        }
    }
    
    if availability:
        packet["availability"] = availability
    
    # Build PeriodStats for all periods
    first_stat = stats_group[0] if stats_group else None
    if first_stat:
        first_height = getattr(first_stat, options.value_field, 0) * options.polygon_height_multiplier
        
        # Build list of PeriodStats for the table display
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
            for s in stats_group
            if s.time_range and s.time_range.start and s.time_range.end
        ]
        
        packet["description"] = build_description_html(
            index_type=index_type,
            stat=first_stat,
            height=first_height,
            all_periods=all_periods,
            is_interpolated=True
        )
    
    return packet


def export_polygon_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    centroid: dict[str, float],
    grouped_stats: dict[str, list]
) -> list[dict[str, Any]]:
    """
    Export as extruded polygon entities with colour-coded height.
    
    Each polygon from the selection is rendered with:
    - Colour derived from the value via colourmap
    - Extruded height proportional to the value
    - Optional time-based animation matching temporal data
    
    Args:
        selection: The polygon selection record with geometry and statistics
        options: CZML export configuration
        vmin: Minimum value for colour scaling
        vmax: Maximum value for colour scaling
        centroid: Polygon centroid (used for labels)
        grouped_stats: Statistics grouped by index_type
    
    Returns:
        List of CZML entity packets
    """
    packets = []
    
    # Get the set of allowed index types from grouped_stats (already filtered upstream)
    allowed_index_types = set(grouped_stats.keys())
    # logger.info(f"CZML polygon export - allowed_index_types: {allowed_index_types}")
    
    # Process each polygon in the selection
    for poly_idx, poly_with_stats in enumerate(selection.polygons):
        geometry = poly_with_stats.geometry.model_dump()
        polygon_centroid = poly_with_stats.centroid
        
        # Log all index types in this polygon before filtering
        # all_idx_types = set(s.index_type for s in poly_with_stats.statistics)
        # logger.info(f"  Polygon {poly_idx}: has index_types {all_idx_types}, filtering to {allowed_index_types}")
        
        # Group this polygon's statistics by index_type, filtering to allowed types only
        poly_grouped = {}
        for stat in poly_with_stats.statistics:
            idx_type = stat.index_type or "unknown"
            # Only include index types that were requested (filtered upstream)
            if idx_type not in allowed_index_types:
                logger.debug(f"    Skipping stat with index_type={idx_type} (not in allowed)")
                continue
            if idx_type not in poly_grouped:
                poly_grouped[idx_type] = []
            poly_grouped[idx_type].append(stat)
        
        # logger.info(f"  Polygon {poly_idx}: after filtering, poly_grouped keys = {list(poly_grouped.keys())}")
        
        # Sort each group by time_range if available
        for idx_type in poly_grouped:
            poly_grouped[idx_type].sort(
                key=lambda s: s.time_range.start if s.time_range and s.time_range.start else s.asset_id
            )
        
        # Create entities for each index type
        for index_type, stats_group in poly_grouped.items():
            logger.info(
                f"Creating polygon(s) for poly_{poly_idx}/{index_type} "
                f"with {len(stats_group)} time periods"
            )
            
            # Check if we have temporal data
            has_temporal = any(
                stat.time_range and stat.time_range.start and stat.time_range.end
                for stat in stats_group
            )
            
            if has_temporal:
                # Branch based on interpolation mode
                if options.interpolation_mode == "interpolation":
                    # Create single entity with sampled (interpolated) properties
                    entity_id = f"{selection.title}_poly{poly_idx}_{index_type.replace(' ', '_')}"
                    
                    packet = _build_interpolated_polygon_packet(
                        entity_id=entity_id,
                        name=f"{index_type} (Interpolated)",
                        geometry=geometry,
                        stats_group=stats_group,
                        options=options,
                        index_type=index_type,
                        vmin=vmin,
                        vmax=vmax,
                        centroid=polygon_centroid
                    )
                    
                    packets.append(packet)
                    logger.info(
                        f"  Created interpolated entity {entity_id} with {len(stats_group)} samples"
                    )
                else:
                    # Step mode: Create SEPARATE entity for EACH time period
                    for period_idx, stat in enumerate(stats_group):
                        value = getattr(stat, options.value_field)
                        if value is None:
                            continue
                        if not stat.time_range or not stat.time_range.start or not stat.time_range.end:
                            continue
                        
                        # Calculate extruded height and colour
                        extruded_height = value * options.polygon_height_multiplier
                        r, g, b, _ = colourmap_interpret(
                            vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                        )
                        # Apply fill opacity
                        alpha = int(options.polygon_fill_opacity * 255)
                        
                        entity_id = (
                            f"{selection.title}_poly{poly_idx}_{index_type.replace(' ', '_')}_{period_idx}"
                        )
                        availability = (
                            f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                        )
                        time_start = stat.time_range.start.strftime('%Y-%m-%d')
                        time_end = stat.time_range.end.strftime('%Y-%m-%d')
                        
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
                            for s in stats_group
                            if s.time_range and s.time_range.start and s.time_range.end
                        ]
                        
                        packet = _build_polygon_packet(
                            entity_id=entity_id,
                            name=f"{index_type} ({time_start})",
                            geometry=geometry,
                            extruded_height=extruded_height,
                            rgba=(r, g, b, alpha),
                            options=options,
                            stat=stat,
                            index_type=index_type,
                            time_start=time_start,
                            time_end=time_end,
                            availability=availability,
                            centroid=polygon_centroid,
                            all_periods=all_periods
                        )
                        
                        packets.append(packet)
                        logger.info(
                            f"  Created step entity {entity_id} for {availability}: "
                            f"height={extruded_height:.0f}m"
                        )
            else:
                # No temporal data - create single static entity
                if not stats_group:
                    continue
                    
                first_stat = stats_group[0]
                value = getattr(first_stat, options.value_field)
                
                if value is not None:
                    extruded_height = value * options.polygon_height_multiplier
                    r, g, b, _ = colourmap_interpret(
                        vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                    )
                    alpha = int(options.polygon_fill_opacity * 255)
                    
                    entity_id = f"{selection.title}_poly{poly_idx}_{index_type.replace(' ', '_')}"
                    
                    packet = _build_polygon_packet(
                        entity_id=entity_id,
                        name=f"{index_type} (Polygon {poly_idx + 1})",
                        geometry=geometry,
                        extruded_height=extruded_height,
                        rgba=(r, g, b, alpha),
                        options=options,
                        stat=first_stat,
                        index_type=index_type,
                        time_start=None,
                        time_end=None,
                        availability=None,
                        centroid=polygon_centroid,
                        all_periods=None
                    )
                    
                    packets.append(packet)
                    logger.info(
                        f"  Created static entity {entity_id}: height={extruded_height:.0f}m"
                    )
    
    return packets


def _build_polygon_packet(
    entity_id: str,
    name: str,
    geometry: dict,
    extruded_height: float,
    rgba: tuple[int, int, int, int],
    options: CZMLExportOptions,
    stat: Any,
    index_type: str,
    time_start: str | None,
    time_end: str | None,
    availability: str | None,
    centroid: dict[str, float],
    all_periods: list[PeriodStats] | None = None
) -> dict[str, Any]:
    """Build a CZML polygon packet with extrusion."""
    
    # Flatten coordinates for CZML
    positions = _flatten_polygon_coordinates(geometry)
    
    r, g, b, a = rgba
    
    packet: dict[str, Any] = {
        "id": entity_id,
        "name": name,
        "polygon": {
            "positions": {
                "cartographicDegrees": positions
            },
            "height": 0,
            "extrudedHeight": extruded_height,
            "material": {
                "solidColor": {
                    "color": {"rgba": [r, g, b, a]}
                }
            },
            "outline": options.polygon_outline,
            "outlineColor": {"rgba": [255, 255, 255, 200]},
            "outlineWidth": 1,
            "closeTop": True,
            "closeBottom": True
        }
    }
    
    # Add availability if temporal
    if availability:
        packet["availability"] = availability
    
    # Build description HTML using shared builder
    packet["description"] = build_description_html(
        index_type=index_type,
        stat=stat,
        height=extruded_height,
        time_start=time_start,
        time_end=time_end,
        all_periods=all_periods
    )
    
    # Add label at centroid if enabled
    if options.show_labels:
        value = getattr(stat, options.value_field)
        packet["position"] = {
            "cartographicDegrees": [centroid["lon"], centroid["lat"], extruded_height]
        }
        packet["label"] = {
            "text": f"{value:.2f} {stat.units or ''}",
            "font": "14pt sans-serif",
            "fillColor": {"rgba": [255, 255, 255, 255]},
            "outlineColor": {"rgba": [0, 0, 0, 255]},
            "outlineWidth": 2,
            "pixelOffset": {"cartesian2": [0, -20]},
            "style": "FILL_AND_OUTLINE",
            "verticalOrigin": "BOTTOM"
        }
    
    return packet
