# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared CZML naming and description HTML builders."""

from __future__ import annotations

from typing import Any, Optional, List
from dataclasses import dataclass
import html


@dataclass
class PeriodStats:
    """Statistics for a single time period."""
    start: str
    end: str
    mean: Optional[float]
    std: Optional[float]
    min: Optional[float]
    max: Optional[float]
    count: int
    units: str


def display_label(value: Any, fallback: str = "Untitled") -> str:
    """Return a human-readable label for CZML names and card headings."""
    if value is None:
        return fallback
    text = str(value).replace("_", " ").replace("-", " ").strip()
    if not text:
        return fallback
    return " ".join(text.split())


def display_index_type(index_type: str) -> str:
    """Format climate index identifiers consistently."""
    label = display_label(index_type, fallback="Unknown index")
    if label.isupper():
        return label
    return label[:1].upper() + label[1:]


def display_period(time_start: Optional[str], time_end: Optional[str]) -> Optional[str]:
    """Return a compact period label for entity titles and descriptions."""
    if not time_start and not time_end:
        return None
    if time_start and time_end:
        start_year = time_start[:4]
        end_year = time_end[:4]
        if start_year and end_year and start_year != end_year:
            return f"{start_year}-{end_year}"
        return time_start if time_start == time_end else f"{time_start} to {time_end}"
    return time_start or time_end


def build_entity_name(
    polygon_title: Optional[str],
    *,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> str:
    """Build the Cesium info-box header title."""
    title = display_label(polygon_title, fallback="Polygon")
    period = display_period(time_start, time_end)
    return f"{title} ({period})" if period else title


def build_polygon_title(raw_title: Optional[str], index: int) -> str:
    """Use the saved per-polygon title, falling back only when it is blank."""
    return display_label(raw_title, fallback=f"Polygon {index + 1}")


def build_period_stats(stats_group: list[Any]) -> list[PeriodStats]:
    """Convert selection statistics into table rows for CZML descriptions."""
    return [
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


def _fmt_number(value: Any, decimals: int = 2, fallback: str = "n/a") -> str:
    """Format optional numeric values without breaking CZML generation."""
    if value is None:
        return fallback
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return fallback


def _escape(value: Any) -> str:
    """HTML-escape display values."""
    return html.escape(str(value), quote=True)


def _mode_label(is_interpolated: bool, has_periods: bool) -> str:
    if is_interpolated:
        return "Interpolated timeline"
    if has_periods:
        return "Step timeline"
    return "Static value"


def _build_header(
    entity_title: Optional[str],
    index_type: str,
    *,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    is_interpolated: bool = False,
    has_periods: bool = False,
) -> str:
    """Build a consistent card header used by all CZML visualisation modes."""
    title = _escape(display_label(entity_title, fallback="Polygon"))
    index_label = _escape(display_index_type(index_type))
    period = display_period(time_start, time_end)
    period_chip = (
        f"<span style='background: #334155; color: #dbeafe; padding: 4px 8px; "
        f"border-radius: 999px; font-size: 11px;'>{_escape(period)}</span>"
        if period
        else ""
    )
    mode = _escape(_mode_label(is_interpolated, has_periods))

    return (
        f"<div style='border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 12px;'>"
        f"<h3 style='margin: 0; color: #f8fafc; font-size: 18px; line-height: 1.25;'>{title}</h3>"
        f"<div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 8px;'>"
        f"<span style='background: #1d4ed8; color: #eff6ff; padding: 4px 8px; "
        f"border-radius: 999px; font-size: 11px; font-weight: 700;'>{index_label}</span>"
        f"{period_chip}"
        f"<span style='color: #93c5fd; font-size: 12px; font-weight: 700;'>{mode}</span>"
        f"</div>"
        f"</div>"
    )


def build_description_html(
    index_type: str,
    stat: Any,
    height: Optional[float] = None,
    entity_title: Optional[str] = None,
    time_label: Optional[str] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    all_periods: Optional[List[PeriodStats]] = None,
    is_interpolated: bool = False
) -> str:
    """
    Build dark-themed HTML description for CZML entity info boxes.
    
    Args:
        index_type: Climate index name (e.g., 'ppet', 'wbgt')
        stat: Statistics object with mean, min, max, std, count, units (for single period display)
        height: Optional rendered height in metres. Omit for flat polygon modes.
        time_label: Optional time period label (e.g., '2024-01-01') - deprecated
        time_start: Period start date string (e.g., '2071-01-01')
        time_end: Period end date string (e.g., '2071-12-31')
        all_periods: List of PeriodStats for all available periods
        is_interpolated: If True, show table of all periods instead of single period stats
    
    Returns:
        HTML string for CZML description property
    """
    # For multiple periods, show table format for both interpolated and step mode
    if all_periods and len(all_periods) > 1:
        return _build_periods_table(
            index_type,
            all_periods,
            height,
            stat.count,
            entity_title=entity_title,
            is_interpolated=is_interpolated,
        )
    
    if time_label and not time_start and not time_end:
        time_start = time_label
    
    return (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        f"color: #e2e8f0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); "
        f"padding: 16px; border-radius: 8px; border: 1px solid #334155; "
        f"box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
        
        f"{_build_header(entity_title, index_type, time_start=time_start, time_end=time_end)}"
        
        f"<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;'>"
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Mean</span><br>"
        f"<strong style='color: #10b981; font-size: 14px;'>{_fmt_number(stat.mean)}</strong> "
        f"<span style='color: #64748b; font-size: 11px;'>{_escape(stat.units or '')}</span></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Std Dev</span><br>"
        f"<strong style='color: #f59e0b; font-size: 14px;'>{_fmt_number(stat.std)}</strong></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Min</span><br>"
        f"<strong style='color: #06b6d4; font-size: 14px;'>{_fmt_number(stat.min)}</strong></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Max</span><br>"
        f"<strong style='color: #ef4444; font-size: 14px;'>{_fmt_number(stat.max)}</strong></div>"
        f"</div>"
        
        f"<div style='margin-top: 12px; padding-top: 12px; border-top: 1px solid #475569; "
        f"display: flex; justify-content: space-between; font-size: 12px;'>"
        f"<span style='color: #94a3b8;'>Pixels: <strong style='color: #e2e8f0;'>{stat.count}</strong></span>"
        f"{_build_height_footer(height)}"
        f"</div>"
        f"</div>"
    )


def _build_height_footer(height: Optional[float]) -> str:
    """Build the optional height footer item for 3D visualisations."""
    if height is None:
        return ""
    return (
        f"<span style='color: #94a3b8;'>Height: "
        f"<strong style='color: #a78bfa;'>{_fmt_number(height, decimals=0)}m</strong></span>"
    )


def _build_periods_table(
    index_type: str,
    all_periods: List[PeriodStats],
    height: Optional[float],
    pixel_count: int,
    *,
    entity_title: Optional[str],
    is_interpolated: bool,
) -> str:
    """Build description with table showing all periods (used for both modes)."""
    
    # Build table rows
    rows = ""
    for p in all_periods:
        year_range = f"{p.start[:4]}–{p.end[:4]}"
        rows += (
            f"<tr style='border-bottom: 1px solid #334155;'>"
            f"<td style='padding: 6px 4px; color: #94a3b8; font-size: 11px;'>{year_range}</td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #10b981;'>{_fmt_number(p.mean)}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #f59e0b;'>{_fmt_number(p.std)}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #06b6d4;'>{_fmt_number(p.min)}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #ef4444;'>{_fmt_number(p.max)}</strong></td>"
            f"</tr>"
        )
    
    units = all_periods[0].units if all_periods else ""
    header = _build_header(
        entity_title,
        index_type,
        is_interpolated=is_interpolated,
        has_periods=True,
    )
    
    return (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        f"color: #e2e8f0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); "
        f"padding: 16px; border-radius: 8px; border: 1px solid #334155; "
        f"box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
        
        f"{header}"
        
        f"<table style='width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0;'>"
        f"<thead><tr style='border-bottom: 2px solid #475569;'>"
        f"<th style='padding: 4px; text-align: left; color: #94a3b8; font-weight: normal;'>Period</th>"
        f"<th style='padding: 4px; text-align: right; color: #10b981;'>Mean</th>"
        f"<th style='padding: 4px; text-align: right; color: #f59e0b;'>Std</th>"
        f"<th style='padding: 4px; text-align: right; color: #06b6d4;'>Min</th>"
        f"<th style='padding: 4px; text-align: right; color: #ef4444;'>Max</th>"
        f"</tr></thead>"
        f"<tbody>{rows}</tbody>"
        f"</table>"
        
        f"<p style='margin: 4px 0; color: #64748b; font-size: 10px;'>Units: {_escape(units)}</p>"
        
        f"<div style='margin-top: 12px; padding-top: 12px; border-top: 1px solid #475569; "
        f"display: flex; justify-content: space-between; font-size: 12px;'>"
        f"<span style='color: #94a3b8;'>Pixels: <strong style='color: #e2e8f0;'>{pixel_count}</strong></span>"
        f"{_build_height_footer(height)}"
        f"</div>"
        f"</div>"
    )
