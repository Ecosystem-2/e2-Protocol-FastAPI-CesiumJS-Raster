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


def period_full_range_iso(stats: list[Any]) -> tuple[str, str] | None:
    """Return the (start, end) ISO timestamps spanning every stat's actual time range.

    Interpolation-mode CZML samples values at each period's midpoint (so a
    30-year normal like 1981-2010 is represented at 1995-96), but the clock
    and entity availability should still span the real data coverage rather
    than shrinking to the first/last midpoint. Using midpoints for both would
    clip roughly half a period off each end of the visible timeline.
    """
    starts = [stat.time_range.start for stat in stats if stat.time_range and stat.time_range.start]
    ends = [stat.time_range.end for stat in stats if stat.time_range and stat.time_range.end]
    if not starts or not ends:
        return None
    return min(starts).isoformat(), max(ends).isoformat()
