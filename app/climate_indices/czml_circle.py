"""CZML flat circle visualisation generator."""

from __future__ import annotations

from typing import Any

from app.climate_indices.models import PolygonSelectionRecord, CZMLExportOptions
from app.climate_indices.czml_description import (
    build_description_html,
    build_entity_name,
    build_period_stats,
    build_polygon_title,
)
from app.climate_indices.czml_time import (
    period_full_range_iso,
    period_midpoint_iso,
    period_midpoint_isos,
)
from app.commons.colours import colourmap_interpret
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_sampled_circle_colour(
    stats_group: list,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float
) -> dict[str, Any]:
    """Build a sampled colour property for circle interpolation mode."""
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
        "interpolationDegree": 1,
        "forwardExtrapolationType": "HOLD",
        "backwardExtrapolationType": "HOLD"
    }


def _circle_packet_base(
    *,
    entity_id: str,
    name: str,
    lon: float,
    lat: float,
    options: CZMLExportOptions,
    colour: dict[str, Any],
) -> dict[str, Any]:
    """Build the shared flat circle packet structure."""
    ellipse: dict[str, Any] = {
        "semiMajorAxis": options.circle_radius,
        "semiMinorAxis": options.circle_radius,
        "height": 0,
        "material": {"solidColor": {"color": colour}},
    }
    if options.polygon_outline:
        ellipse["outline"] = True
        ellipse["outlineColor"] = {"rgba": [255, 255, 255, 220]}
        ellipse["outlineWidth"] = 1

    return {
        "id": entity_id,
        "name": name,
        "position": {"cartographicDegrees": [lon, lat, 0]},
        "ellipse": ellipse,
    }


def _add_circle_label(
    packet: dict[str, Any],
    *,
    stat: Any,
    options: CZMLExportOptions,
    lon: float,
    lat: float,
) -> None:
    """Add an optional value label above the flat circle."""
    if not options.show_labels:
        return
    value = getattr(stat, options.value_field)
    if value is None:
        return

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


def export_circle_czml(
    selection: PolygonSelectionRecord,
    options: CZMLExportOptions,
    vmin: float,
    vmax: float,
    index_type_filter: str | None = None
) -> list[dict[str, Any]]:
    """
    Export one flat 2D colour circle per saved polygon.

    The circle is centred on each polygon centroid. Radius is fixed from
    options.circle_radius; the selected statistic is represented by colour.
    """
    packets: list[dict[str, Any]] = []

    for poly_idx, poly in enumerate(selection.polygons):
        lon = poly.centroid["lon"]
        lat = poly.centroid["lat"]
        poly_name = build_polygon_title(poly.title, poly_idx)
        stats_list = [
            s for s in poly.statistics
            if not index_type_filter or s.index_type == index_type_filter
        ]
        if not stats_list:
            logger.warning("  Polygon %s: No statistics found for circle export", poly_idx)
            continue

        stats_list.sort(
            key=lambda s: s.time_range.start if s.time_range and s.time_range.start else ""
        )
        index_type = stats_list[0].index_type or "unknown"
        has_temporal = any(
            stat.time_range and stat.time_range.start and stat.time_range.end
            for stat in stats_list
        )

        if has_temporal:
            all_periods = build_period_stats(stats_list)

            if options.interpolation_mode == "interpolation":
                entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_circle"
                sampled_colour = _build_sampled_circle_colour(stats_list, options, vmin, vmax)
                first_stat = stats_list[0]
                packet = _circle_packet_base(
                    entity_id=entity_id,
                    name=build_entity_name(poly_name),
                    lon=lon,
                    lat=lat,
                    options=options,
                    colour=sampled_colour,
                )
                full_range = period_full_range_iso(stats_list)
                if full_range:
                    packet["availability"] = f"{full_range[0]}/{full_range[1]}"
                else:
                    midpoint_times = period_midpoint_isos(stats_list)
                    if midpoint_times:
                        packet["availability"] = f"{midpoint_times[0]}/{midpoint_times[-1]}"
                packet["description"] = build_description_html(
                    index_type=index_type,
                    stat=first_stat,
                    entity_title=poly_name,
                    all_periods=all_periods,
                    is_interpolated=True
                )
                _add_circle_label(packet, stat=first_stat, options=options, lon=lon, lat=lat)
                packets.append(packet)
                continue

            for period_idx, stat in enumerate(stats_list):
                value = getattr(stat, options.value_field)
                if value is None or not stat.time_range or not stat.time_range.start or not stat.time_range.end:
                    continue

                r, g, b, _ = colourmap_interpret(
                    vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
                )
                alpha = int(options.polygon_fill_opacity * 255)
                time_start = stat.time_range.start.strftime('%Y-%m-%d')
                time_end = stat.time_range.end.strftime('%Y-%m-%d')
                entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_circle_{period_idx}"
                packet = _circle_packet_base(
                    entity_id=entity_id,
                    name=build_entity_name(poly_name, time_start=time_start, time_end=time_end),
                    lon=lon,
                    lat=lat,
                    options=options,
                    colour={"rgba": [r, g, b, alpha]},
                )
                packet["availability"] = f"{stat.time_range.start.isoformat()}/{stat.time_range.end.isoformat()}"
                packet["description"] = build_description_html(
                    index_type=index_type,
                    stat=stat,
                    entity_title=poly_name,
                    time_start=time_start,
                    time_end=time_end,
                    all_periods=all_periods
                )
                _add_circle_label(packet, stat=stat, options=options, lon=lon, lat=lat)
                packets.append(packet)
        else:
            first_stat = stats_list[0]
            value = getattr(first_stat, options.value_field)
            if value is None:
                continue

            r, g, b, _ = colourmap_interpret(
                vmin=vmin, vmax=vmax, value=value, colourmap=options.colourmap_name
            )
            alpha = int(options.polygon_fill_opacity * 255)
            entity_id = f"{selection.title.replace(' ', '_')}_{poly_name.replace(' ', '_')}_circle"
            packet = _circle_packet_base(
                entity_id=entity_id,
                name=build_entity_name(poly_name),
                lon=lon,
                lat=lat,
                options=options,
                colour={"rgba": [r, g, b, alpha]},
            )
            packet["description"] = build_description_html(
                index_type=index_type,
                stat=first_stat,
                entity_title=poly_name
            )
            _add_circle_label(packet, stat=first_stat, options=options, lon=lon, lat=lat)
            packets.append(packet)

    return packets
