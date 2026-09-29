# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from app.core.middleware import add_middlewares
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.api.router import api_router, tags_metadata
from app.core import service_token, source_offer
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

    # Starting without it is allowed, since a missing URL shouldn't take the service
    # down, but a network deployment that can't tell users where the source is isn't
    # meeting section 13.
    if source_offer.source_url() is None:
        logging.getLogger(__name__).warning(
            "SOURCE_URL not set — /source cannot tell users where to get the code, "
            "which leaves any network-facing deployment short of AGPL section 13"
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
            "source": "/source",
            **({} if service_token.enabled() else {"demo": "/demo/"}),
        }

    # Section 13 obliges us to offer the source to everyone interacting with this
    # service over a network, so neither route sits behind the service token.
    @app.get("/source", tags=["licence"])
    def source():
        """Where to get the Corresponding Source for the version running here."""
        return source_offer.offer()

    @app.get("/licence", tags=["licence"], response_class=PlainTextResponse)
    def licence():
        """The full licence text, so the notice resolves without leaving the service."""
        text = source_offer.licence_text()
        if text is None:
            raise HTTPException(
                status_code=500,
                detail=f"Licence text missing from this deployment. See {source_offer.source_url()}",
            )
        return text

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)
