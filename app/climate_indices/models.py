from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimeRange(BaseModel):
    start: Optional[datetime] = Field(default=None, description="Start timestamp for the asset.")
    end: Optional[datetime] = Field(default=None, description="End timestamp for the asset.")


class AssetIngestRequest(BaseModel):
    """User-supplied context for a GeoTIFF upload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    index_type: str = Field(..., description="Climate index name, e.g., humid-heat-stress.")
    time_range: Optional[TimeRange] = Field(default=None, description="Time coverage for the asset.")
    units: Optional[str] = Field(default=None, description="Units of the raster values.")
    filename: Optional[str] = Field(default=None, description="Original filename (optional provenance).")


class RasterSummary(BaseModel):
    """Lightweight metadata snapshot derived from the raster."""

    model_config = ConfigDict(str_strip_whitespace=True)

    epsg: Optional[int] = Field(default=None)
    crs_wkt: Optional[str] = Field(default=None, description="CRS represented as WKT.")
    bounds: Optional[Dict[str, float]] = Field(default=None)
    resolution: Optional[Tuple[float, float]] = Field(default=None)
    sizes: Optional[Dict[str, int]] = Field(default=None)
    dtype: Optional[str] = Field(default=None)
    nodata: Optional[float] = Field(default=None)
    min: Optional[float] = Field(default=None)
    max: Optional[float] = Field(default=None)
    mean: Optional[float] = Field(default=None)
    std: Optional[float] = Field(default=None)
    time_extent: Optional[Dict[str, Any]] = Field(default=None)

    @classmethod
    def from_raster_metadata(cls, raw: Dict[str, Any]) -> "RasterSummary":
        """Create a serialisable summary from geotif_converter metadata."""
        crs = raw.get("crs")
        crs_wkt = None
        try:
            if crs is not None:
                crs_wkt = str(crs.to_wkt()) if hasattr(crs, "to_wkt") else str(crs)
        except Exception:
            crs_wkt = None

        resolution = raw.get("resolution")
        if resolution is not None:
            try:
                resolution = (float(resolution[0]), float(resolution[1]))
            except Exception:
                resolution = None

        return cls(
            epsg=raw.get("epsg"),
            crs_wkt=crs_wkt,
            bounds=raw.get("bounds"),
            resolution=resolution,
            sizes=raw.get("sizes"),
            dtype=raw.get("dtype"),
            nodata=raw.get("nodata"),
            min=raw.get("min"),
            max=raw.get("max"),
            mean=raw.get("mean"),
            std=raw.get("std"),
            time_extent=raw.get("time_extent"),
        )


class AssetIngestResult(BaseModel):
    """Result of an ingest attempt, ready to be persisted or queued for further processing."""

    asset: AssetIngestRequest
    raster: RasterSummary


class StorageInfo(BaseModel):
    """Where the raw/COG is stored."""

    kind: Literal["local", "gridfs", "s3", "gcs", "unknown"] = "unknown"
    uri: str = Field(..., description="Location of the stored blob (path, URL, or key).")
    checksum: Optional[str] = Field(default=None, description="Checksum of the stored payload.")
    size_bytes: Optional[int] = Field(default=None, description="Size of the stored payload in bytes.")


class AssetStorage(BaseModel):
    """Raw and COG storage references."""

    raw: StorageInfo
    cog: StorageInfo


class AssetRecord(BaseModel):
    """Full asset document suitable for MongoDB storage."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    index_type: str
    time_range: Optional[TimeRange] = None
    units: Optional[str] = None
    filename: Optional[str] = None
    storage: AssetStorage
    raster: RasterSummary
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AssetPersistenceResult(BaseModel):
    asset: AssetIngestRequest
    asset_id: str
    storage: AssetStorage
    raster: RasterSummary
