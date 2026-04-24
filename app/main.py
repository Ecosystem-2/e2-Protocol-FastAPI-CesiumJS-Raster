from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.middleware import add_middlewares
# from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.api.router import api_router, tags_metadata
from dotenv import load_dotenv
import os
from pathlib import Path
load_dotenv()

def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    configure_logging()

    app = FastAPI(
        title="HOB FastAPI",
        description="Data ingestion and conversion service for CesiumJS visualisation",
        version="1.0.0",
        # lifespan=lifespan,
        openapi_tags=tags_metadata,
    )

    add_middlewares(app)
    app.include_router(api_router)
    
    # Mount static demo files
    demo_dir = Path(__file__).parent / "demo"
    app.mount("/demo", StaticFiles(directory=str(demo_dir), html=True), name="demo")

    @app.get("/")
    def root():
        return {
            "service": "hob-fastapi",
            "routers": ["geotif_converter", "climate_indices", "demo"],
            "docs": "/docs",
            "demo": "/demo/"
        }

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)
