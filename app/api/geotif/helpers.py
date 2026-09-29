# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any, Callable, Final, Generator

import pandas as pd
from affine import Affine
from fastapi import UploadFile
import numpy as np
from rasterio.crs import CRS
from pathlib import Path

CHUNK_SIZE: Final[int] = 1024 * 1024  # 1 MiB

__all__ = [
    "serialise_metadata",
    "read_upload_bytes",
    "dataframe_to_records",
    "suggest_variable_name",
    "dataframe_to_csv_stream",
]


async def read_upload_bytes(
    upload: UploadFile,
    *,
    max_bytes: int,
    chunk_size: int = CHUNK_SIZE,
) -> bytes:
    """Stream an UploadFile into memory, enforcing a maximum size."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive.")

    data = bytearray()
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ValueError("Upload exceeds the supported size.")

    return bytes(data)


def serialise_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Convert raster metadata into JSON-serialisable primitives."""

    def _affine_to_dict(value: Affine) -> dict[str, float]:
        return {
            "a": float(value.a),
            "b": float(value.b),
            "c": float(value.c),
            "d": float(value.d),
            "e": float(value.e),
            "f": float(value.f),
        }

    def _coerce(value: Any) -> Any:
        if isinstance(value, Affine):
            return _affine_to_dict(value)
        if isinstance(value, CRS):
            return value.to_string() if value else None
        if isinstance(value, Mapping):
            return {str(k): _coerce(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [_coerce(v) for v in value]
        if isinstance(value, (np.generic,)):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        if hasattr(value, "tolist"):
            try:
                return value.tolist()
            except Exception:
                pass
        return value

    coerced = _coerce(metadata)
    if not isinstance(coerced, dict):
        raise TypeError("Metadata serialisation must produce a dictionary.")
    return coerced


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-serialisable records."""

    def _convert(value: Any) -> Any:
        if isinstance(value, (np.generic,)):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return value.isoformat()
        if pd.isna(value):
            return None
        return value

    records = df.to_dict(orient="records")
    return [{k: _convert(v) for k, v in row.items()} for row in records]


def suggest_variable_name(filename: str | None, raster_name: str | None) -> str:
    if raster_name:
        return raster_name

    if filename:
        stem = Path(filename).stem
        return stem.replace(" ", "_")

    return "value"


def dataframe_to_csv_stream(
    df: pd.DataFrame,
    *,
    include_header: bool = True,
    chunk_size: int = 1024 * 64,
) -> Generator[bytes, None, None]:
    """Yield CSV output incrementally to avoid holding entire payloads in memory."""

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=include_header)
    buffer.seek(0)
    while True:
        chunk = buffer.read(chunk_size)
        if not chunk:
            break
        yield chunk.encode("utf-8")


