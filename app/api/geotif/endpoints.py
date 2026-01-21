from __future__ import annotations

from typing import Any, Final
import re
import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.geotif.helpers import (
    dataframe_to_csv_stream,
    serialise_metadata,
)
from app.geotif_converter.raster2dataframe import raster_to_dataframe
from app.geotif_converter.raster_io import get_raster_metadata
from app.api.geotif.services import GeoTiffService

router = APIRouter(prefix="/geotif", tags=["geotif_converter"])

ACCEPTED_CONTENT_TYPES: Final[set[str]] = {
    "image/tiff",
    "image/tif",
    "image/geotiff",
    "application/octet-stream",
}
MAX_UPLOAD_MB: Final[int] = 50
MAX_UPLOAD_BYTES: Final[int] = MAX_UPLOAD_MB * 1024 * 1024
DEFAULT_TARGET_CRS: Final[str] = "EPSG:4326"
geotif_service = GeoTiffService(
    max_upload_bytes=MAX_UPLOAD_BYTES,
    accepted_content_types=ACCEPTED_CONTENT_TYPES,
)


# %% - Get GeoTIFF Metadata
@router.post("/metadata", name="get_geotif_metadata")
async def get_geotif_metadata(
    files: list[UploadFile] = File(...),
    target_crs: str = DEFAULT_TARGET_CRS,
) -> dict[str, Any]:
    """Upload one or many GeoTIFFs and return their metadata."""

    items: list[dict[str, Any]] = []
    async for payload in geotif_service.iter_rasters(files, target_crs=target_crs):
        metadata = get_raster_metadata(payload.raster)
        serialised = serialise_metadata(metadata)
        items.append(
            {
                "filename": payload.filename,
                "target_crs": payload.target_crs,
                "metadata": serialised,
            }
        )

    return {
        "target_crs": target_crs,
        "items": items,
    }


# %% - Convert GeoTIFF to CSV
@router.post("/csv", name="convert_geotifs_to_csv")
async def convert_geotifs_to_csv(
    files: list[UploadFile] = File(...),
    target_crs: str = DEFAULT_TARGET_CRS,
    drop_na: bool = True,
) -> StreamingResponse:
    """Upload GeoTIFFs and stream back CSV rows for each file."""


    async def _generator() -> bytes:
        header_written = False
        frames: list[pd.DataFrame] = []
        async for payload in geotif_service.iter_rasters(files, target_crs=target_crs):
            variable_name = re.sub(r"\.(tif|tiff|geotiff)$", "", payload.variable_name.lower())
            df = raster_to_dataframe(
                payload.raster,
                variable_name=variable_name,
                drop_na=drop_na,
                exclude_columns=["band", "spatial_ref"],
            )
            frames.append(df[["x", "y", variable_name]])

        combined = frames[0]
        for frame in frames[1:]:
            combined = combined.merge(frame, on=["x", "y"], how="outer")

        for chunk in dataframe_to_csv_stream(combined, include_header=not header_written):
            header_written = True
            yield chunk

    return StreamingResponse(
        _generator(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="geotif-dataframe.csv"',
            "X-Target-CRS": target_crs,
        },
    )


