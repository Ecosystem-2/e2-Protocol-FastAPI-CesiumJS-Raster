# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.geotif_converter.csv2czml import (
    Interval,
    csv_to_czml,
)
from app.geotif_converter.csv2czml_timestamp import (
    csv_to_czml_timestamp,
)


SEGAMA_INTERVALS = (
    Interval(
        label="Historic (1981-2010)",
        start="1981-01-01T00:00:00Z",
        end="2010-12-31T23:59:59Z",
        column="segama_historic_1981-2010_wbgt-sun_max_threat_level",
        timestamp="1995-01-01T00:00:00Z",
    ),
    Interval(
        label="Mid-century (2041-2070)",
        start="2041-01-01T00:00:00Z",
        end="2070-12-31T23:59:59Z",
        column="segama_all245_2041-2070_wbgt-sun_max_threat_level",
        timestamp="2055-01-01T00:00:00Z",
    ),
    Interval(
        label="Late-century (2071-2100)",
        start="2071-01-01T00:00:00Z",
        end="2100-12-31T23:59:59Z",
        column="segama_all245_2071-2100_wbgt-sun_max_threat_level",
        timestamp="2085-01-01T00:00:00Z",
    ),
)


def main() -> None:
    csv_path = PROJECT_ROOT / "data" / "humid-heat-stress" / "ssp245_WBGT_Sun_Segama_River_combined.csv"
    output_dir = PROJECT_ROOT / "data" / "humid-heat-stress"
    output_dir.mkdir(parents=True, exist_ok=True)

    interval_czml = output_dir / "ssp245_WBGT_Sun_Segama_River_interval.czml"
    timestamp_czml = output_dir / "ssp245_WBGT_Sun_Segama_River_timestamp.czml"

    interval_count, _ = csv_to_czml(
        csv_path=str(csv_path),
        out_path=str(interval_czml),
        intervals=SEGAMA_INTERVALS,
    )
    print(f"Wrote interval CZML with {interval_count} entities -> {interval_czml}")

    timestamp_count, _ = csv_to_czml_timestamp(
        csv_path=str(csv_path),
        out_path=str(timestamp_czml),
        intervals=SEGAMA_INTERVALS,
    )
    print(f"Wrote timestamp CZML with {timestamp_count} entities -> {timestamp_czml}")


if __name__ == "__main__":
    main()
