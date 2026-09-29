# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Climate indices endpoints package."""

from fastapi import APIRouter, Depends

from app.api.climate.endpoints.tiles import router as tiles_router
from app.api.climate.endpoints.assets import router as assets_router
from app.api.climate.endpoints.ingest import router as ingest_router
from app.api.climate.endpoints.polygons import router as polygons_router
from app.api.climate.endpoints.selections import router as selections_router
from app.api.climate.endpoints.czml import router as czml_router
from app.api.climate.endpoints.config import router as config_router
from app.core.service_token import require_service_token

# Create main router with prefix
router = APIRouter(prefix="/climate-indices")

# Scopes are attached per sub-router rather than per endpoint, so a newly added
# endpoint inherits its router's requirement instead of shipping unguarded.
# These must stay in step with what Express sends in climateIndices.controller.ts.
router.include_router(
    tiles_router,
    tags=["climate_tiles"],
    dependencies=[Depends(require_service_token("climate:read"))],
)
router.include_router(
    assets_router,
    tags=["climate_assets"],
    dependencies=[Depends(require_service_token("climate:read"))],
)
router.include_router(
    ingest_router,
    tags=["climate_ingest"],
    dependencies=[Depends(require_service_token("climate:ingest"))],
)
router.include_router(
    polygons_router,
    tags=["climate_polygons"],
    dependencies=[Depends(require_service_token("climate:query"))],
)
router.include_router(
    selections_router,
    tags=["climate_selections"],
    dependencies=[Depends(require_service_token("climate:query"))],
)
router.include_router(
    czml_router,
    tags=["climate_czml"],
    dependencies=[Depends(require_service_token("climate:export"))],
)
router.include_router(
    config_router,
    tags=["climate_config"],
    dependencies=[Depends(require_service_token("climate:read"))],
)

__all__ = ["router"]
