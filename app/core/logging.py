# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import os
import sys
from typing import Optional

# Below DEBUG, so library firehoses can be opted into without making DEBUG
# unusable. Python defines nothing under DEBUG (10), hence the custom level.
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

# Third-party loggers held above the app's own level. pymongo is the worst
# offender: at DEBUG it emits an SDAM heartbeat pair per replica-set member
# every ~10s, which buries application logs entirely against an Atlas cluster.
_NOISY_LOGGERS = (
    "pymongo",
    "urllib3",
    "google",
    "rasterio",
    "matplotlib",
    "fiona",
    "PIL",
    "botocore",
    "asyncio",
)

# app level -> level applied to _NOISY_LOGGERS
_NOISY_LEVEL_FOR = {
    TRACE: logging.DEBUG,
    logging.DEBUG: logging.INFO,
}


def _resolve_level(name: str) -> int:
    if name == "TRACE":
        return TRACE
    resolved = logging.getLevelName(name)
    return resolved if isinstance(resolved, int) else logging.INFO


def configure_logging(level: Optional[str] = None) -> None:
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    app_level = _resolve_level(level_name)
    app_name = os.getenv("APP_NAME", "fastapi-app")

    logging.basicConfig(
        level=app_level,
        format=f"{app_name} %(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # reset any prior config (useful under reload)
    )

    # Tame Uvicorn verbosity (keeps things quiet without custom handlers)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    noisy_level = _NOISY_LEVEL_FOR.get(app_level, logging.WARNING)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(noisy_level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
