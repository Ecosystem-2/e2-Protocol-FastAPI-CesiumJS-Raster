"""Domain models for climate indices.

This module contains all Pydantic models for:
- Common types (TimeRange, StorageInfo)
- Asset records (raster metadata, ingest requests)
- Polygon selections (geometry, statistics)
- CZML export (options, documents)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Common Models
# =============================================================================


class TimeRange(BaseModel):
    """Time range for temporal data."""

    start: Optional[datetime] = Field(default=None, description="Start timestamp for the asset.")
    end: Optional[datetime] = Field(default=None, description="End timestamp for the asset.")


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


# =============================================================================
# Asset Models
# =============================================================================


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


class AssetIngestRequest(BaseModel):
    """User-supplied context for a GeoTIFF upload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    raster_id: Optional[str] = Field(default=None, description="Frontend-generated UUID for cross-system reference.")
    index_type: str = Field(..., description="Climate index name, e.g., humid-heat-stress.")
    time_range: Optional[TimeRange] = Field(default=None, description="Time coverage for the asset.")
    units: Optional[str] = Field(default=None, description="Units of the raster values.")
    filename: Optional[str] = Field(default=None, description="Original filename (optional provenance).")
    user_id: Optional[str] = Field(default=None, description="Owner user UUID for access control.")
    project_id: Optional[str] = Field(default=None, description="Project UUID for grouping assets.")


class AssetIngestResult(BaseModel):
    """Result of an ingest attempt, ready to be persisted or queued for further processing."""

    asset: AssetIngestRequest
    raster: RasterSummary


class AssetRecord(BaseModel):
    """Full asset document suitable for MongoDB storage."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    raster_id: Optional[str] = Field(default=None, description="Frontend-generated UUID for cross-system reference.")
    index_type: str
    time_range: Optional[TimeRange] = None
    units: Optional[str] = None
    filename: Optional[str] = None
    user_id: Optional[str] = Field(default=None, description="Owner user UUID for access control.")
    project_id: Optional[str] = Field(default=None, description="Project UUID for grouping assets.")
    storage: AssetStorage
    raster: RasterSummary
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssetPersistenceResult(BaseModel):
    """Result of persisting an asset to storage and database."""

    asset: AssetIngestRequest
    asset_id: str
    raster_id: Optional[str] = Field(default=None, description="Frontend-generated UUID if provided.")
    user_id: Optional[str] = Field(default=None, description="Owner user UUID.")
    project_id: Optional[str] = Field(default=None, description="Project UUID.")
    storage: AssetStorage
    raster: RasterSummary
    replaced: bool = Field(default=False, description="True if an existing asset was replaced")


# =============================================================================
# Selection Models
# =============================================================================


class PolygonGeometry(BaseModel):
    """GeoJSON polygon geometry."""

    model_config = ConfigDict(str_strip_whitespace=True)

    type: Literal["Polygon", "MultiPolygon"] = "Polygon"
    coordinates: List[Any] = Field(..., description="GeoJSON coordinate arrays")


class SelectionStatistics(BaseModel):
    """Zonal statistics for a single asset-polygon pair."""

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_ref: str = Field(..., description="MongoDB ObjectId reference to the asset")
    index_type: str = Field(..., description="Climate index type (ppet, wbgt, etc.)")
    units: Optional[str] = Field(default=None)

    # Statistical measures
    count: int = Field(..., description="Number of valid pixels")
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None

    # Asset metadata snapshot
    asset_filename: Optional[str] = None
    time_range: Optional[TimeRange] = None


class PolygonWithStatistics(BaseModel):
    """Single polygon with its computed statistics and centroid."""

    model_config = ConfigDict(str_strip_whitespace=True)

    geometry: PolygonGeometry = Field(..., description="GeoJSON polygon geometry")
    centroid: Dict[str, float] = Field(..., description="Computed centroid {lon, lat}")
    statistics: List[SelectionStatistics] = Field(
        default_factory=list,
        description="Zonal statistics for this polygon across all queried assets"
    )


class PolygonSelectionRecord(BaseModel):
    """Persisted polygon selection with multi-polygon statistics."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    selection_id: Optional[str] = Field(default=None, description="Frontend-generated UUID for cross-system reference.")

    # Site identifiers
    locale_id: Optional[str] = Field(default=None, description="Locale UUID for grouping selections")
    site_id: Optional[str] = Field(default=None, description="Site UUID for this selection")

    # Ownership
    user_id: Optional[str] = Field(default=None, description="Owner user UUID for access control.")
    project_id: Optional[str] = Field(default=None, description="Project UUID for grouping selections.")

    # User metadata
    title: str = Field(..., min_length=1, max_length=200, description="Unique selection title")
    description: Optional[str] = Field(default=None, max_length=2000)
    tags: List[str] = Field(default_factory=list, description="User-defined tags for categorisation")

    # Polygons with bundled geometry, centroid, and statistics
    polygons: List[PolygonWithStatistics] = Field(
        default_factory=list,
        description="List of polygons, each with geometry, centroid, and statistics"
    )

    # Audit trail
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = Field(default=None, description="Deprecated: use user_id instead")


# =============================================================================
# CZML Models
# =============================================================================


class CZMLExportOptions(BaseModel):
    """Configuration for CZML export rendering."""

    model_config = ConfigDict(str_strip_whitespace=True)

    visualisation_type: Literal["bar", "polygon"] = Field(
        default="polygon",
        description="Cesium entity type: bar (3D cylinders) or polygon (extruded shapes)"
    )

    colourmap_name: str = Field(
        default="viridis",
        description="Matplotlib colourmap name (used with commons/colours.py)"
    )

    scale_min: Optional[float] = Field(
        default=None,
        description="Minimum value for colour scale (auto-computed if None)"
    )

    scale_max: Optional[float] = Field(
        default=None,
        description="Maximum value for colour scale (auto-computed if None)"
    )

    value_field: Literal["mean", "min", "max", "median", "std"] = Field(
        default="mean",
        description="Which statistic to visualise"
    )

    bar_height_multiplier: float = Field(
        default=10000.0,
        gt=0,
        description="Multiplier for bar chart heights (metres)"
    )

    bar_radius_multiplier: float = Field(
        default=10.0,
        gt=0,
        description="Multiplier for bar radius: radius = pixel_count * multiplier"
    )

    bar_minimum_radius: float = Field(
        default=500.0,
        ge=0,
        description="Minimum bar radius in metres (ensures visibility)"
    )

    polygon_height_multiplier: float = Field(
        default=1000.0,
        gt=0,
        description="Multiplier for polygon extrusion heights (metres)"
    )

    polygon_fill_opacity: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Fill opacity for extruded polygons (0-1)"
    )

    polygon_outline: bool = Field(
        default=True,
        description="Show polygon outline"
    )

    show_labels: bool = Field(default=True, description="Display value labels on entities")

    interpolation_mode: Literal["step", "interpolation"] = Field(
        default="step",
        description=(
            "Temporal animation mode: 'step' shows discrete values per period, "
            "'interpolation' smoothly transitions between period start values"
        )
    )


class CZMLRecord(BaseModel):
    """Persisted CZML document with selection reference."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    czml_id: Optional[str] = Field(default=None, description="Frontend-generated UUID for cross-system reference.")

    selection_ref: str = Field(
        ...,
        description="MongoDB ObjectId reference to polygon_selections collection"
    )

    index_type: str = Field(
        ...,
        description="Climate index type (e.g., ppet, wbgt)"
    )

    title: str = Field(..., description="CZML document name")
    description: Optional[str] = Field(default=None)

    # Ownership
    user_id: Optional[str] = Field(default=None, description="Owner user UUID for access control.")
    project_id: Optional[str] = Field(default=None, description="Project UUID for grouping CZML documents.")

    # Export configuration used to generate this CZML
    export_options: CZMLExportOptions = Field(
        ...,
        description="Options used for CZML generation"
    )

    # The CZML document itself (list of packets as JSON string or dict)
    czml_document: List[Dict[str, Any]] = Field(
        ...,
        description="CZML packet array"
    )

    # Metadata
    packet_count: int = Field(default=0, description="Number of CZML packets")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Common
    "TimeRange",
    "StorageInfo",
    "AssetStorage",
    # Asset
    "RasterSummary",
    "AssetIngestRequest",
    "AssetIngestResult",
    "AssetRecord",
    "AssetPersistenceResult",
    # Selection
    "PolygonGeometry",
    "SelectionStatistics",
    "PolygonWithStatistics",
    "PolygonSelectionRecord",
    # CZML
    "CZMLExportOptions",
    "CZMLRecord",
]
