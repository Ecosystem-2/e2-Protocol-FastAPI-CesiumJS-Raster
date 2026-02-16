"""Shared CZML description HTML builder with dark modern theme."""

from __future__ import annotations

from typing import Any, Optional


def build_description_html(
    index_type: str,
    stat: Any,
    height: float,
    time_label: Optional[str] = None
) -> str:
    """
    Build dark-themed HTML description for CZML entity info boxes.
    
    Args:
        index_type: Climate index name (e.g., 'ppet', 'wbgt')
        stat: Statistics object with mean, min, max, std, count, units
        height: Extruded height in metres
        time_label: Optional time period label (e.g., '2024-01-01')
    
    Returns:
        HTML string for CZML description property
    """
    period_html = (
        f"<p style='margin: 8px 0; color: #60a5fa;'>"
        f"<strong>Period:</strong> {time_label}</p>"
    ) if time_label else ""
    
    return (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; "
        f"color: #e2e8f0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); "
        f"padding: 16px; border-radius: 8px; border: 1px solid #334155; "
        f"box-shadow: 0 4px 6px rgba(0,0,0,0.3);'>"
        
        # Header
        f"<h3 style='margin: 0 0 12px 0; color: #f8fafc; font-size: 16px; "
        f"border-bottom: 2px solid #3b82f6; padding-bottom: 8px;'>{index_type}</h3>"
        
        f"{period_html}"
        
        # Statistics grid
        f"<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;'>"
        
        # Mean
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Mean</span><br>"
        f"<strong style='color: #10b981; font-size: 14px;'>{stat.mean:.2f}</strong> "
        f"<span style='color: #64748b; font-size: 11px;'>{stat.units or ''}</span></div>"
        
        # Std Dev
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Std Dev</span><br>"
        f"<strong style='color: #f59e0b; font-size: 14px;'>{stat.std:.2f}</strong></div>"
        
        # Min
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Min</span><br>"
        f"<strong style='color: #06b6d4; font-size: 14px;'>{stat.min:.2f}</strong></div>"
        
        # Max
        f"<div style='background: #334155; padding: 8px; border-radius: 4px;'>"
        f"<span style='color: #94a3b8; font-size: 11px;'>Max</span><br>"
        f"<strong style='color: #ef4444; font-size: 14px;'>{stat.max:.2f}</strong></div>"
        
        f"</div>"
        
        # Footer with pixel count and height
        f"<div style='margin-top: 12px; padding-top: 12px; border-top: 1px solid #475569; "
        f"display: flex; justify-content: space-between; font-size: 12px;'>"
        f"<span style='color: #94a3b8;'>Pixels: "
        f"<strong style='color: #e2e8f0;'>{stat.count}</strong></span>"
        f"<span style='color: #94a3b8;'>Height: "
        f"<strong style='color: #a78bfa;'>{height:.0f}m</strong></span>"
        f"</div>"
        
        f"</div>"
    )
