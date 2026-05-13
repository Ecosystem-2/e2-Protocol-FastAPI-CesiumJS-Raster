"""Shared time helpers for CZML generation."""

from __future__ import annotations

from typing import Any


def period_midpoint_iso(stat: Any) -> str | None:
    """Return the ISO timestamp halfway through a statistic's time range."""
    if not stat.time_range or not stat.time_range.start:
        return None
    if not stat.time_range.end:
        return stat.time_range.start.isoformat()
    midpoint = stat.time_range.start + (stat.time_range.end - stat.time_range.start) / 2
    return midpoint.isoformat()


def period_midpoint_isos(stats: list[Any]) -> list[str]:
    """Return midpoint timestamps for all stats that have usable time ranges."""
    midpoints = []
    for stat in stats:
        midpoint = period_midpoint_iso(stat)
        if midpoint:
            midpoints.append(midpoint)
    return sorted(midpoints)
