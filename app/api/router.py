from fastapi import APIRouter

from app.api.geotif.endpoints import router as geotif_converter_router
from app.api.climate import router as climate_indices_router

tags_metadata = [
    {"name": "geotif_converter", "description": "Geotif converter endpoints."},
    # {"name": "demo", "description": "html demo poc routers."},
    {"name": "climate_indices", "description": "Climate indices ingest and query endpoints."},
]

api_router = APIRouter(prefix="/api")

# 1. 
api_router.include_router(geotif_converter_router, tags=["geotif_converter"])
# api_router.include_router(humid_heat_stress_geotif_router, tags=["demo"])
api_router.include_router(climate_indices_router, tags=["climate_indices"])
