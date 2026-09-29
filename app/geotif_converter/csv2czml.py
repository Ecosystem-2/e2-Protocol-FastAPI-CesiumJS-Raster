# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd
from czml3 import Packet
from czml3.properties import Clock


# Minimal CZML writer using plain dicts to keep dependencies light while
# following the CZML structure described by the Cesium CZML Guide.
# Columns expected in the CSV (header inspected):
#   '', 'index', 'y', 'x',
#   'ssp245_wbgt_sun_2071_2100',
#   'ssp245_wbgt_sun_2041_2070',
#   'ssp245_wbgt_sun_historical_1981_2010'


ISO8601_Z_FMT = "%Y-%m-%dT%H:%M:%SZ"
INFOBOX_STYLE = (
    "<style>"
    ".czml-info{color:#0c1b2b;font-family:'Inter',sans-serif;font-size:14px;"
    "line-height:1.45;margin:0;padding:0;}"
    ".czml-info strong{color:#0f4070;}"
    "</style>"
)


@dataclass(frozen=True)
class Interval:
    label: str
    start: str  # ISO8601 UTC
    end: str    # ISO8601 UTC
    column: str
    timestamp: Optional[str] = None  # Optional representative instant


INTERVALS: Tuple[Interval, ...] = (
    Interval(
        label="1981–2010 (historical)",
        start="1981-01-01T00:00:00Z",
        end="2010-12-31T23:59:59Z",
        column="segama_historic_1981_2010",
    ),
    Interval(
        label="2041–2070",
        start="2041-01-01T00:00:00Z",
        end="2070-12-31T23:59:59Z",
        column="segama_all245_2041",
    ),
    Interval(
        label="2071–2100",
        start="2071-01-01T00:00:00Z",
        end="2100-12-31T23:59:59Z",
        column="segama_all245_2071",
    ),
)

CZMLPacket = Union[Packet, Dict[str, Any]]


def value_to_rgba(value: Optional[float]) -> Optional[List[int]]:
    """Map WBGT category/value to RGBA colour.

    Heuristic palette (categorical):
    - 1 -> green; 2 -> orange; 3 -> red; 4 -> purple; 5+ -> brown
    - NaN/None -> None (used to hide point for that interval)
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None

    try:
        v_int = int(round(value))
    except Exception:
        return None

    palette: Dict[int, Tuple[int, int, int]] = {
        1: (50, 205, 50, 80),     # forest green
        2: (255, 255, 0, 80),     # dark orange
        3: (255, 165, 0, 80),     # crimson
        4: (255, 0, 0, 80),     # purple
        5: (0, 0, 0, 80),     # saddle brown
    }
    r, g, b, a = palette.get(v_int, (70, 70, 70, 80))
    return [r, g, b, a]


def make_document_packet(name: str, start: str, end: str) -> Packet:
    return Packet(
        id="document",
        name=name,
        version="1.0",
        clock=Clock(
            interval={"start": start, "end": end},
            currentTime=start,
            multiplier=31536000,
            range="LOOP_STOP",
        ),
    )


def packet_to_dict(packet: CZMLPacket) -> Dict[str, Any]:
    """Convert czml3 Packet objects or raw dicts into a CZML dictionary representation."""
    if isinstance(packet, Packet):
        return json.loads(packet.to_json())
    return dict(packet)


def parse_iso8601_z(value: str) -> datetime:
    return datetime.strptime(value, ISO8601_Z_FMT)


def format_iso8601_z(value: datetime) -> str:
    return value.strftime(ISO8601_Z_FMT)


def resolve_timeline_bounds(
    intervals: Sequence[Interval],
) -> Tuple[str, str]:
    if not intervals:
        raise ValueError("At least one interval definition is required")
    start_times: List[datetime] = []
    end_times: List[datetime] = []
    for interval in intervals:
        start_times.append(parse_iso8601_z(interval.start))
        end_times.append(parse_iso8601_z(interval.end))
    return (
        format_iso8601_z(min(start_times)),
        format_iso8601_z(max(end_times)),
    )


def build_entity_packet(
    entity_id: str,
    lon: float,
    lat: float,
    values_by_interval: Dict[str, Optional[float]],
    intervals: Sequence[Interval],
    timeline_start: str,
    timeline_end: str,
) -> Dict[str, Any]:
    show_values: List[Dict[str, Any]] = []
    for interval in intervals:
        v = values_by_interval.get(interval.column)
        interval_str = f"{interval.start}/{interval.end}"
        visible = not (v is None or (isinstance(v, float) and math.isnan(v)))
        show_values.append({"interval": interval_str, "boolean": visible})

    desc_lines = [
        f"<strong>Lon:</strong> {lon:.6f}, <strong>Lat:</strong> {lat:.6f}",
    ]
    for it in intervals:
        val = values_by_interval.get(it.column)
        val_str = "N/A" if val is None or (isinstance(val, float) and math.isnan(val)) else str(val)
        desc_lines.append(f"<strong>{it.label}:</strong> {val_str}")
    description_html = INFOBOX_STYLE + "<div class='czml-info'>" + "<br/>".join(desc_lines) + "</div>"

    color_values: List[Dict[str, Any]] = []
    for interval in intervals:
        v = values_by_interval.get(interval.column)
        rgba = value_to_rgba(v)
        if rgba is None:
            continue
        color_values.append({"interval": f"{interval.start}/{interval.end}", "rgba": rgba})

    show_prop = (show_values if show_values else True)
    color_prop: Union[Dict[str, Any], List[int]] = (color_values if color_values else {"rgba": [200, 200, 200, 80]})

    availability_interval = f"{timeline_start}/{timeline_end}"

    return {
        "id": entity_id,
        "availability": availability_interval,
        "position": {"cartographicDegrees": [float(lon), float(lat), 0.0]},
        "point": {
            "pixelSize": 7.0,
            "outlineWidth": 0,
            "show": show_prop,
            "color": color_prop,
        },
        "description": {"string": description_html},
    }


def csv_to_czml(
    csv_path: str,
    out_path: str,
    *,
    limit_points: Optional[int] = None,
    intervals: Optional[Sequence[Interval]] = None,
) -> Tuple[int, str]:
    """Convert a CSV with WBGT columns to a CZML document."""
    df = pd.read_csv(csv_path)

    # Normalise column names (strip spaces)
    df.columns = [c.strip() for c in df.columns]

    intervals = tuple(intervals or INTERVALS)
    required_cols = {"x", "y"} | {it.column for it in intervals}
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # Keep rows with at least one non-null value across intervals
    df_values = df[list({it.column for it in intervals})]
    mask_has_value = df_values.notnull().any(axis=1)
    df = df.loc[mask_has_value].copy()

    if limit_points is not None and limit_points > 0:
        df = df.head(limit_points)

    timeline_start, timeline_end = resolve_timeline_bounds(intervals)
    name = os.path.splitext(os.path.basename(out_path))[0]
    preamble = make_document_packet(name=name, start=timeline_start, end=timeline_end)

    packets: List[CZMLPacket] = []
    for idx, row in df.iterrows():
        lon = float(row["x"])
        lat = float(row["y"])
        values = {it.column: row.get(it.column) for it in intervals}
        entity_id = f"pt-{idx}"
        packets.append(
            build_entity_packet(
                entity_id,
                lon,
                lat,
                values,
                intervals,
                timeline_start,
                timeline_end,
            )
        )

    # Convert packets to raw CZML dictionaries. This allows us to mix czml3 Packet
    # objects with handwritten dicts for components not provided by czml3.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    czml_list = [packet_to_dict(preamble)] + [packet_to_dict(pkt) for pkt in packets]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(czml_list, f, ensure_ascii=False, separators=(",", ":"), indent=2)

    return len(packets), out_path


def main() -> None:
    # This file lives under src/geotif_converter/, so project root is two levels up
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    csv_path = os.path.join(
        project_root,
        "data",
        "humid-heat-stress",
        "ssp245_WBGT_Sun_Segama_River_combined.csv",
    )
    out_czml_path = os.path.join(
        project_root,
        "data",
        "humid-heat-stress",
        "ssp245_WBGT_Sun_Segama_River_interval.czml",
    )

    count, path = csv_to_czml(csv_path=csv_path, out_path=out_czml_path)
    print(f"Wrote CZML with {count} entities -> {path}")


if __name__ == "__main__":
    main()
