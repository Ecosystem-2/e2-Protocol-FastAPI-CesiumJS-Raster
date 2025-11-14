from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.demo.cesium.catalog import catalogue_payload, get_layer
from app.demo.cesium.tiles import render_png


router = APIRouter(prefix="/demo", tags=["demo"])

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "demo" / "cesium" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get(
    "/png",
    name="cesium_viewer_page",
    summary="Cesium climate story demo",
    description="Interactive CesiumJS scene showcasing the Segama climate scenarios.",
)
async def cesium_viewer(request: Request):
    return templates.TemplateResponse(
        "cesium_viewer.html",
        {
            "request": request,
            "config_url": request.url_for("cesium_config"),
            "image_url_template": request.url_for(
                "cesium_layer_image", collection_id="{collection_id}", layer_id="{layer_id}"
            ),
            "cesium_token": os.getenv("CESIUM_ION_TOKEN", ""),
        },
    )


@router.get("/config", name="cesium_config", summary="Cesium demo configuration")
async def cesium_config() -> JSONResponse:
    payload = catalogue_payload()
    return JSONResponse(payload)


@router.get(
    "/layers/{collection_id}/{layer_id}/image",
    name="cesium_layer_image",
    summary="Rendered GeoTIFF tile for Cesium demo",
)
async def cesium_layer_image(collection_id: str, layer_id: str) -> Response:
    try:
        layer = get_layer(collection_id, layer_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    png_bytes = render_png(
        str(layer.path),
        layer.colormap,
        tuple(layer.palette) if layer.palette else None,
    )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )
