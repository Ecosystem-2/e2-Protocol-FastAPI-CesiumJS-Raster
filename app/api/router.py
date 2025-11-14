from fastapi import APIRouter

from app.api.geotif.endpoints import router as geotif_converter_router
from app.api.demo.cesium import router as cesium_demo_router

tags_metadata = [
    {"name": "geotif_converter", "description": "Geotif converter endpoints."},
]

api_router = APIRouter(prefix="/api")
api_router.include_router(geotif_converter_router, tags=["geotif_converter"])
api_router.include_router(cesium_demo_router, tags=["demo"])


