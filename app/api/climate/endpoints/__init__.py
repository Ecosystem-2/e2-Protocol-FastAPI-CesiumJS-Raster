"""Climate indices endpoints package."""

from fastapi import APIRouter

from app.api.climate.endpoints.tiles import router as tiles_router
from app.api.climate.endpoints.assets import router as assets_router
from app.api.climate.endpoints.ingest import router as ingest_router
from app.api.climate.endpoints.polygons import router as polygons_router
from app.api.climate.endpoints.selections import router as selections_router

# Create main router with prefix
router = APIRouter(prefix="/climate-indices", tags=["climate_indices"])

# Include sub-routers
router.include_router(tiles_router)
router.include_router(assets_router)
router.include_router(ingest_router)
router.include_router(polygons_router)
router.include_router(selections_router)

__all__ = ["router"]
