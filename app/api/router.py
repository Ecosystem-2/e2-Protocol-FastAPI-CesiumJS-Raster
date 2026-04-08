from fastapi import APIRouter

from app.api.geotif.endpoints import router as geotif_converter_router
from app.api.climate import router as climate_indices_router

tags_metadata = [
    # Climate indices — core workflow (actively used by frontend)
    {
        "name": "climate_ingest",
        "description": "**Core workflow.** Upload and ingest GeoTIFF climate files. "
                       "Validates, reprojects to EPSG:4326, stores raw + COG to GCS, and records metadata in MongoDB. "
                       "Supports frontend-generated raster_id UUIDs for upsert and ownership tracking.",
    },
    {
        "name": "climate_tiles",
        "description": "**Core workflow.** Serve PNG map tiles from COG-backed assets via rio-tiler. "
                       "Used by Cesium's UrlTemplateImageryProvider for raster overlay visualisation.",
    },
    {
        "name": "climate_assets",
        "description": "**Core workflow.** Browse, search, retrieve, update, and delete climate data assets. "
                       "Supports lookup by MongoDB ObjectId, raster_id UUID, or filename. "
                       "Filterable by user_id and project_id for ownership scoping.",
    },
    {
        "name": "climate_polygons",
        "description": "**Core workflow.** Compute zonal statistics or extract raw pixel values within drawn polygons. "
                       "Operates on GCS-stored COGs. Supports multiple assets × multiple polygons in a single request. "
                       "Stats endpoint returns count/min/max/mean/std; pixels endpoint returns CSV or JSON.",
    },
    {
        "name": "climate_selections",
        "description": "**Core workflow.** Persist named polygon selections with pre-computed zonal statistics. "
                       "Selections group one or more drawn polygons with their statistics across multiple assets. "
                       "Used as input for CZML export.",
    },
    {
        "name": "climate_czml",
        "description": "**Core workflow.** Export saved selections as CZML documents for 3D Cesium visualisation. "
                       "Supports bar-chart and extruded-polygon visualisation types with configurable colourmaps. "
                       "Also provides colourmap discovery endpoints.",
    },
    {
        "name": "climate_config",
        "description": "**Utility.** Serves runtime configuration to the demo frontend (API base URL, Cesium Ion token). "
                       "Values sourced from environment variables.",
    },
    # GeoTIF converter — standalone utility (not part of main workflow)
    {
        "name": "geotif_converter",
        "description": "**Utility — standalone.** Generic GeoTIFF processing endpoints for metadata extraction and "
                       "CSV conversion. Not part of the main climate ingest workflow. Useful for inspecting raster "
                       "properties or exporting pixel data for external analysis pipelines.",
    },
]

api_router = APIRouter(prefix="/api")

# Include routers
api_router.include_router(geotif_converter_router, tags=["geotif_converter"])
# api_router.include_router(humid_heat_stress_geotif_router, tags=["demo"])
api_router.include_router(climate_indices_router)  # Tags set in climate endpoint modules
