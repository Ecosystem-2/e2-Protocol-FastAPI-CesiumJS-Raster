import logging
import os
import sys
from typing import Optional

def configure_logging(level: Optional[str] = None) -> None:
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    app_name = os.getenv("APP_NAME", "fastapi-app")

    logging.basicConfig(
        level=level,
        format=f"{app_name} %(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # reset any prior config (useful under reload)
    )

    # Tame Uvicorn verbosity (keeps things quiet without custom handlers)
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("uvicorn.error").setLevel("INFO")
    logging.getLogger("fastapi").setLevel("INFO")

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)