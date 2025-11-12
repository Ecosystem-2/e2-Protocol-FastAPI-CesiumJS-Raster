from fastapi import FastAPI
from app.core.middleware import add_middlewares
# from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.api.router import api_router, tags_metadata

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

    @app.get("/")
    def root():
        return {"service": "hob-fastapi", "routers": ["geotif_converter"]}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
