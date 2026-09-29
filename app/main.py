# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.middleware import add_middlewares
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.api.router import api_router, tags_metadata
from app.core import service_token
from dotenv import load_dotenv
import logging
import os
from pathlib import Path
load_dotenv()

def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    configure_logging()

    # Whether the API is closed is not something to have to infer from a 401.
    if service_token.enabled():
        logging.getLogger(__name__).info(
            "Service tokens enabled as '%s' — climate endpoints require x-service-token",
            service_token.service_name(),
        )
    else:
        logging.getLogger(__name__).warning(
            "Service tokens not configured — climate endpoints are open to anyone "
            "who can reach this process"
        )

    app = FastAPI(
        title="HOB FastAPI",
        description="Data ingestion and conversion service for CesiumJS visualisation",
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=tags_metadata,
    )

    add_middlewares(app)
    app.include_router(api_router)

    # The demo is a browser client, and a browser cannot hold a signing key. Once
    # service tokens are configured every endpoint it calls returns 401, so it is
    # not mounted — serving a page that cannot work is worse than not serving it.
    if not service_token.enabled():
        demo_dir = Path(__file__).parent / "demo"
        app.mount("/demo", StaticFiles(directory=str(demo_dir), html=True), name="demo")

    @app.get("/")
    def root():
        return {
            "service": "e2-visengine-service",
            "routers": ["geotif_converter", "climate_indices"]
            + ([] if service_token.enabled() else ["demo"]),
            "auth": "service-token" if service_token.enabled() else "open",
            "docs": "/docs",
            **({} if service_token.enabled() else {"demo": "/demo/"}),
        }

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)
