# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Sequence

from fastapi import HTTPException, UploadFile, status
import xarray as xr

from app.api.geotif.helpers import read_upload_bytes, suggest_variable_name
from app.core.logging import get_logger
from app.geotif_converter.raster_io import read_geotiff

logger = get_logger(__name__)


@dataclass(slots=True)
class ProcessedRaster:
    filename: str
    target_crs: str
    raster: xr.DataArray
    variable_name: str


class GeoTiffService:
    def __init__(
        self,
        *,
        max_upload_bytes: int,
        accepted_content_types: set[str],
    ) -> None:
        self.max_upload_bytes = max_upload_bytes
        self.accepted_content_types = {ct.lower() for ct in accepted_content_types}

    async def iter_rasters(
        self,
        files: Sequence[UploadFile],
        *,
        target_crs: str,
    ) -> AsyncIterator[ProcessedRaster]:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide at least one GeoTIFF file.",
            )

        for upload in files:
            self._validate_upload(upload)
            raw = await self._read_bytes(upload)
            raster = self._read_raster(raw, upload.filename, target_crs=target_crs)
            variable = suggest_variable_name(upload.filename, raster.name)
            yield ProcessedRaster(
                filename=upload.filename or "unknown",
                target_crs=target_crs,
                raster=raster,
                variable_name=variable,
            )

    def _validate_upload(self, upload: UploadFile) -> None:
        if not upload.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One of the uploads is missing a filename.",
            )

        content_type = (upload.content_type or "").lower()
        if content_type and content_type not in self.accepted_content_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Only GeoTIFF uploads are supported (file: {upload.filename}).",
            )

    async def _read_bytes(self, upload: UploadFile) -> bytes:
        try:
            return await read_upload_bytes(upload, max_bytes=self.max_upload_bytes)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Larger size is not supported yet (file: {upload.filename or 'unknown'}).",
            ) from exc

    def _read_raster(
        self,
        raw_data: bytes,
        filename: str | None,
        *,
        target_crs: str,
    ) -> xr.DataArray:
        try:
            return read_geotiff(raw_data, target_crs=target_crs)
        except (ValueError, FileNotFoundError) as exc:
            logger.info("GeoTIFF processing failed (%s): %s", filename, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The uploaded file '{filename}' could not be processed as a GeoTIFF.",
            ) from exc
