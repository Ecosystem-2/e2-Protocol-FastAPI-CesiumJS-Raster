"""Climate indices endpoints package."""

from fastapi import APIRouter

from app.api.climate.endpoints.tiles import router as tiles_router
from app.api.climate.endpoints.assets import router as assets_router
from app.api.climate.endpoints.ingest import router as ingest_router
from app.api.climate.endpoints.polygons import router as polygons_router
from app.api.climate.endpoints.selections import router as selections_router
from app.api.climate.endpoints.czml import router as czml_router

# Create main router with prefix
router = APIRouter(prefix="/climate-indices")

# Include sub-routers with specific tags for better docs organisation
router.include_router(tiles_router, tags=["climate_tiles"])
router.include_router(assets_router, tags=["climate_assets"])
router.include_router(ingest_router, tags=["climate_ingest"])
router.include_router(polygons_router, tags=["climate_polygons"])
router.include_router(selections_router, tags=["climate_selections"])
router.include_router(czml_router, tags=["climate_czml"])

__all__ = ["router"]
