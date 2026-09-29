# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

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


def period_sample_times(stats: list[Any]) -> list[tuple[Any, str]]:
    """Pair each stat with the ISO timestamp to sample it at for interpolation.

    The first and last periods (ordered by time_range.start) are sampled at
    their actual start/end bounds rather than their midpoint, so the
    interpolated value ramps across the full period instead of holding flat
    between the data's true edge and the first/last period's midpoint.
    Interior periods still sample at their midpoint, representing the centre
    of that climatological normal. Stats without a usable start are skipped.
    """
    usable = [stat for stat in stats if stat.time_range and stat.time_range.start]
    n = len(usable)
    pairs: list[tuple[Any, str]] = []
    for i, stat in enumerate(usable):
        if n > 1 and i == 0:
            sample_time: str | None = stat.time_range.start.isoformat()
        elif n > 1 and i == n - 1 and stat.time_range.end:
            sample_time = stat.time_range.end.isoformat()
        else:
            sample_time = period_midpoint_iso(stat)
        if sample_time:
            pairs.append((stat, sample_time))
    return pairs


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
