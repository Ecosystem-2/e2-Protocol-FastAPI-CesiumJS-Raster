from fastapi import APIRouter
# from app.api.endpoints.geotif_converter import router as geotif_converter_router

tags_metadata = [
    {"name": "geotif_converter", "description": "Geotif converter endpoints."},
]

api_router = APIRouter(prefix="/api")

# api_router.include_router(geotif_converter_router, tags=["geotif_converter"])





