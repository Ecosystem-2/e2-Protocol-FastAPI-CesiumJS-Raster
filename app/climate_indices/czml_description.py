"""Shared CZML description HTML builder with dark modern theme."""

from __future__ import annotations

from typing import Any, Optional, List
from dataclasses import dataclass


@dataclass
class PeriodStats:
    """Statistics for a single time period."""
    start: str
    end: str
    mean: float
    std: float
    min: float
    max: float
    count: int
    units: str


def build_description_html(
    index_type: str,
    stat: Any,
    height: float,
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
        height: Extruded height in metres
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
        mode_label = (
            "Interpolated – drag timeline to animate"
            if is_interpolated
            else "Step Mode – use timeline to switch periods"
        )
        return _build_periods_table(index_type, all_periods, height, stat.count, mode_label)
    
    # Single period mode - show current period with stats grid
    period_html = ""
    if time_start and time_end:
        period_html = (
            f"<p style='margin: 8px 0; color: #60a5fa;'>"
            f"<strong>Period:</strong> {time_start} to {time_end}</p>"
        )
    elif time_label:
        period_html = (
            f"<p style='margin: 8px 0; color: #60a5fa;'>"
            f"<strong>Period:</strong> {time_label}</p>"
        )
    
    # Build available periods summary if present
    available_html = ""
    if all_periods and len(all_periods) > 1:
        period_years = [p.start[:4] for p in all_periods]
        available_html = (
            f"<p style='margin: 4px 0 8px 0; color: #94a3b8; font-size: 11px;'>"
            f"<strong>Available:</strong> {', '.join(period_years)} ({len(all_periods)} periods)</p>"
        )
    
    return (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        f"color: #e2e8f0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); "
        f"padding: 16px; border-radius: 8px; border: 1px solid #334155; "
        f"box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
        
        f"<h3 style='margin: 0 0 12px 0; color: #f8fafc; font-size: 16px; "
        f"border-bottom: 2px solid #3b82f6; padding-bottom: 8px;'>{index_type}</h3>"
        
        f"{period_html}"
        f"{available_html}"
        
        f"<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;'>"
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Mean</span><br>"
        f"<strong style='color: #10b981; font-size: 14px;'>{stat.mean:.2f}</strong> "
        f"<span style='color: #64748b; font-size: 11px;'>{stat.units or ''}</span></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Std Dev</span><br>"
        f"<strong style='color: #f59e0b; font-size: 14px;'>{stat.std:.2f}</strong></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Min</span><br>"
        f"<strong style='color: #06b6d4; font-size: 14px;'>{stat.min:.2f}</strong></div>"
        
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Max</span><br>"
        f"<strong style='color: #ef4444; font-size: 14px;'>{stat.max:.2f}</strong></div>"
        f"</div>"
        
        f"<div style='margin-top: 12px; padding-top: 12px; border-top: 1px solid #475569; "
        f"display: flex; justify-content: space-between; font-size: 12px;'>"
        f"<span style='color: #94a3b8;'>Pixels: <strong style='color: #e2e8f0;'>{stat.count}</strong></span>"
        f"<span style='color: #94a3b8;'>Height: <strong style='color: #a78bfa;'>{height:.0f}m</strong></span>"
        f"</div>"
        f"</div>"
    )


def _build_periods_table(
    index_type: str,
    all_periods: List[PeriodStats],
    height: float,
    pixel_count: int,
    mode_label: str
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
            f"<strong style='color: #10b981;'>{p.mean:.2f}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #f59e0b;'>{p.std:.2f}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #06b6d4;'>{p.min:.2f}</strong></td>"
            f"<td style='padding: 6px 4px; text-align: right;'>"
            f"<strong style='color: #ef4444;'>{p.max:.2f}</strong></td>"
            f"</tr>"
        )
    
    units = all_periods[0].units if all_periods else ""
    
    return (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        f"color: #e2e8f0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); "
        f"padding: 16px; border-radius: 8px; border: 1px solid #334155; "
        f"box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
        
        f"<h3 style='margin: 0 0 12px 0; color: #f8fafc; font-size: 16px; "
        f"border-bottom: 2px solid #3b82f6; padding-bottom: 8px;'>{index_type}</h3>"
        
        f"<p style='margin: 4px 0 8px 0; color: #60a5fa; font-size: 12px;'>"
        f"<strong>{mode_label}</strong></p>"
        
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
        
        f"<p style='margin: 4px 0; color: #64748b; font-size: 10px;'>Units: {units}</p>"
        
        f"<div style='margin-top: 12px; padding-top: 12px; border-top: 1px solid #475569; "
        f"display: flex; justify-content: space-between; font-size: 12px;'>"
        f"<span style='color: #94a3b8;'>Pixels: <strong style='color: #e2e8f0;'>{pixel_count}</strong></span>"
        f"<span style='color: #94a3b8;'>Height: <strong style='color: #a78bfa;'>{height:.0f}m</strong></span>"
        f"</div>"
        f"</div>"
    )
