from fastapi import APIRouter

from app.api.geotif.endpoints import router as geotif_converter_router
from app.api.climate import router as climate_indices_router

tags_metadata = [
    {"name": "geotif_converter", "description": "Geotif converter endpoints."},
    # {"name": "demo", "description": "html demo poc routers."},
    
    # Climate indices - organized by functionality
    {"name": "climate_ingest", "description": "Upload and ingest climate GeoTIFF files"},
    {"name": "climate_tiles", "description": "Serve raster tiles for map visualization"},
    {"name": "climate_assets", "description": "Browse and search climate data assets"},
    {"name": "climate_polygons", "description": "Query zonal statistics for polygons"},
    {"name": "climate_selections", "description": "Save and manage polygon selections"},
    {"name": "climate_czml", "description": "Export selections as CZML for Cesium"},
]

api_router = APIRouter(prefix="/api")

# Include routers
api_router.include_router(geotif_converter_router, tags=["geotif_converter"])
# api_router.include_router(humid_heat_stress_geotif_router, tags=["demo"])
api_router.include_router(climate_indices_router)  # Tags set in climate endpoint modules
