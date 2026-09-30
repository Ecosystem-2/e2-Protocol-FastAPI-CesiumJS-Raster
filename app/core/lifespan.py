# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from contextlib import asynccontextmanager
import os
import time
from typing import Tuple

from fastapi import FastAPI

from app.core import source_offer
from app.db.mongo import (
    get_async_client,
    close_async_client,
    get_mongo_uri,
    redact_uri,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_WIDTH = 64


def _rule(char: str = "-") -> None:
    logger.info(char * _WIDTH)


def _setting(label: str, value: object) -> None:
    logger.info("  %-15s %s", label, value)


def _log_runtime_settings() -> None:
    _rule("=")
    logger.info("  e2 Protocol: FastAPI + CesiumJS (Raster)")
    logger.info("  Climatology microservice for the Heart of Borneo project")
    _rule("=")
    logger.info("  RUNTIME SETTINGS")
    _setting("Log level", os.getenv("LOG_LEVEL", "INFO").upper())
    _setting("Mongo URI", redact_uri(get_mongo_uri()))
    _setting("Mongo DB", os.getenv("MONGO_DB", "climate_indices"))
    _setting("GCS bucket", os.getenv("GCS_BUCKET") or "(unset)")
    _setting("GCS prefix", os.getenv("GCS_PREFIX", "uploads"))
    _setting("Demo API", os.getenv("DEMO_API_BASE") or "(unset)")
    _setting("Cesium token", "set" if os.getenv("CESIUM_ION_TOKEN") else "(unset)")
    _setting("Source offer", source_offer.source_url() or "(unset)")
    _setting("Revision", source_offer.revision() or "(unset)")
    _rule()


async def _check_mongo() -> Tuple[bool, str]:
    started = time.perf_counter()
    try:
        await get_async_client().admin.command("ping")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, f"ping succeeded in {(time.perf_counter() - started) * 1000:.0f} ms"


def _check_gcs() -> Tuple[bool, str]:
    bucket = os.getenv("GCS_BUCKET")
    if not bucket:
        return False, "GCS_BUCKET is not set"
    prefix = os.getenv("GCS_PREFIX", "uploads")
    try:
        from google.cloud import storage

        # Lists objects rather than calling bucket.exists(): the latter needs
        # storage.buckets.get, which object-scoped service accounts correctly
        # lack, so it reports failure on a perfectly working deployment.
        next(iter(storage.Client().list_blobs(bucket, prefix=prefix, max_results=1)), None)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, f"bucket '{bucket}' readable"


def _report(name: str, ok: bool, detail: str) -> None:
    if ok:
        logger.info("  %-15s OK   %s", name, detail)
    else:
        logger.error("  %-15s FAIL %s", name, detail)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_runtime_settings()

    logger.info("  DEPENDENCY CHECKS")
    mongo_ok, mongo_detail = await _check_mongo()
    _report("MongoDB", mongo_ok, mongo_detail)
    gcs_ok, gcs_detail = _check_gcs()
    _report("Google Storage", gcs_ok, gcs_detail)
    _rule()

    if mongo_ok and gcs_ok:
        logger.info("  SERVICE READY - accepting requests")
    else:
        # Kept serving rather than exiting: a crash-loop under restart:always
        # hides the failure detail above, which is the part worth reading.
        logger.error("  SERVICE DEGRADED - started with failing dependencies")
    _rule("=")

    try:
        yield
    finally:
        close_async_client()
        logger.info("Service stopped; MongoDB client closed")
