# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

from app.geotif_converter.csv2czml import (
    INFOBOX_STYLE,
    INTERVALS,
    Interval,
    make_document_packet,
    packet_to_dict,
    parse_iso8601_z,
    value_to_rgba,
)


CZMLPacket = Union[Dict[str, Any]]
ISO8601_Z_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_TIMESTAMP_DURATION_SECONDS = 24 * 60 * 60 * 365 *5 # 1 year
TIMESTAMP_CLOCK_MULTIPLIER = 24 * 60 * 60 * 365 
CYLINDER_RADIUS_FACTOR = 360.0  # meters


def format_iso8601_z(value: datetime) -> str:
    return value.strftime(ISO8601_Z_FMT)


def value_to_height(value: Optional[float]) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    try:
        return float(value) * 240.0
    except Exception:
        return 0.0


def resolve_timestamp_interval(
    interval: Interval,
    timestamp_duration_seconds: int,
) -> Tuple[str, str]:
    if timestamp_duration_seconds <= 0:
        raise ValueError("timestamp_duration_seconds must be positive")
    ts = interval.timestamp or interval.start
    start_dt = parse_iso8601_z(ts)
    end_dt = start_dt + timedelta(seconds=timestamp_duration_seconds)
    return format_iso8601_z(start_dt), format_iso8601_z(end_dt)


def resolve_timestamp_timeline(
    intervals: Sequence[Interval],
    timestamp_duration_seconds: int,
) -> Tuple[str, str]:
    if not intervals:
        raise ValueError("At least one interval definition is required")
    start_times: List[datetime] = []
    end_times: List[datetime] = []
    for interval in intervals:
        start_i, end_i = resolve_timestamp_interval(interval, timestamp_duration_seconds)
        start_times.append(parse_iso8601_z(start_i))
        end_times.append(parse_iso8601_z(end_i))
    return (
        format_iso8601_z(min(start_times)),
        format_iso8601_z(max(end_times)),
    )


def build_timestamp_packet(
    entity_id: str,
    lon: float,
    lat: float,
    values_by_interval: Dict[str, Optional[float]],
    intervals: Sequence[Interval],
    timeline_start: str,
    timeline_end: str,
    timestamp_duration_seconds: int,
) -> Dict[str, Any]:
    cylinder_colors: List[Dict[str, Any]] = []
    sample_points: List[Tuple[datetime, float, Optional[List[int]]]] = []

    for interval in intervals:
        v = values_by_interval.get(interval.column)
        rgba = value_to_rgba(v)
        start_i, end_i = resolve_timestamp_interval(interval, timestamp_duration_seconds)
        interval_str = f"{start_i}/{end_i}"
        height = value_to_height(v)
        sample_points.append((parse_iso8601_z(start_i), max(height, 0.0), rgba))

    desc_lines = [
        f"<strong>Lon:</strong> {lon:.6f}, <strong>Lat:</strong> {lat:.6f}",
    ]
    for it in intervals:
        val = values_by_interval.get(it.column)
        val_str = "N/A" if val is None or (isinstance(val, float) and math.isnan(val)) else str(val)
        desc_lines.append(f"<strong>{it.label}:</strong> {val_str}")
    description_html = INFOBOX_STYLE + "<div class='czml-info'>" + "<br/>".join(desc_lines) + "</div>"

    sample_points.sort(key=lambda item: item[0])
    timeline_start_dt = parse_iso8601_z(timeline_start)

    def seconds_from_epoch(dt: datetime) -> float:
        return (dt - timeline_start_dt).total_seconds()

    length_numbers: List[float] = []
    position_numbers: List[float] = []
    for dt, height, _ in sample_points:
        length_numbers.extend([seconds_from_epoch(dt), height])
        position_numbers.extend([seconds_from_epoch(dt), float(lon), float(lat), max(height * 0.5, 20.0)])

    # Add final zero sample to smoothly drop bars after last timestamp
    if sample_points:
        end_dt = parse_iso8601_z(timeline_end)
        if end_dt > sample_points[-1][0]:
            last_height = sample_points[-1][1]
            length_numbers.extend([seconds_from_epoch(end_dt), last_height])
            position_numbers.extend([seconds_from_epoch(end_dt), float(lon), float(lat), max(last_height * 0.5, 20.0)])

    position_prop: Dict[str, Any]
    if position_numbers:
        position_prop = {
            "epoch": timeline_start,
            "cartographicDegrees": position_numbers,
            "interpolationAlgorithm": "LAGRANGE",
            "interpolationDegree": 1,
        }
    else:
        position_prop = {"cartographicDegrees": [float(lon), float(lat), 0.0]}

    length_prop: Union[Dict[str, Any], float]
    if length_numbers:
        length_prop = {
            "epoch": timeline_start,
            "number": length_numbers,
            "interpolationAlgorithm": "LINEAR",
            "interpolationDegree": 1,
        }
    else:
        length_prop = 0.0

    show_prop = True
    color_intervals: List[Dict[str, Any]] = []
    if sample_points:
        default_color = [255, 255, 255, 180]
        known_last_color = next((rgba for _, _, rgba in reversed(sample_points) if rgba is not None), default_color)
        extended_points = list(sample_points)
        extended_points.append((parse_iso8601_z(timeline_end), sample_points[-1][1], known_last_color))
        last_color = sample_points[0][2] or default_color
        for (dt, _, rgba), (next_dt, _, _) in zip(extended_points[:-1], extended_points[1:]):
            rgba_use = rgba or last_color
            if rgba is not None:
                last_color = rgba
            color_intervals.append({
                "interval": f"{format_iso8601_z(dt)}/{format_iso8601_z(next_dt)}",
                "rgba": rgba_use,
            })
    cylinder_color_prop = (color_intervals if color_intervals else {"rgba": [255, 255, 255, 180]})

    availability_interval = f"{timeline_start}/{timeline_end}"

    return {
        "id": entity_id,
        "availability": availability_interval,
        "position": position_prop,
        "cylinder": {
            "length": length_prop,
            "topRadius": CYLINDER_RADIUS_FACTOR,
            "bottomRadius": CYLINDER_RADIUS_FACTOR,
            "material": {"solidColor": {"color": cylinder_color_prop}},
            "show": show_prop,
        },
        "description": {"string": description_html},
    }


def csv_to_czml_timestamp(
    csv_path: str,
    out_path: str,
    *,
    limit_points: Optional[int] = None,
    intervals: Optional[Sequence[Interval]] = None,
    timestamp_duration_seconds: int = DEFAULT_TIMESTAMP_DURATION_SECONDS,
) -> Tuple[int, str]:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]

    intervals = tuple(intervals or INTERVALS)
    required_cols = {"x", "y"} | {it.column for it in intervals}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    df_values = df[list({it.column for it in intervals})]
    mask_has_value = df_values.notnull().any(axis=1)
    df = df.loc[mask_has_value].copy()

    if limit_points is not None and limit_points > 0:
        df = df.head(limit_points)

    timeline_start, timeline_end = resolve_timestamp_timeline(intervals, timestamp_duration_seconds)
    name = os.path.splitext(os.path.basename(out_path))[0]
    preamble = make_document_packet(name=name, start=timeline_start, end=timeline_end)

    packets: List[CZMLPacket] = []
    for idx, row in df.iterrows():
        lon = float(row["x"])
        lat = float(row["y"])
        values = {it.column: row.get(it.column) for it in intervals}
        entity_id = f"pt-{idx}"
        packets.append(
            build_timestamp_packet(
                entity_id,
                lon,
                lat,
                values,
                intervals,
                timeline_start,
                timeline_end,
                timestamp_duration_seconds,
            )
        )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    czml_list = [packet_to_dict(preamble)] + [packet_to_dict(pkt) for pkt in packets]
    if czml_list and "clock" in czml_list[0]:
        czml_list[0]["clock"]["multiplier"] = TIMESTAMP_CLOCK_MULTIPLIER
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(czml_list, f, ensure_ascii=False, separators=(",", ":"), indent=2)

    return len(packets), out_path
