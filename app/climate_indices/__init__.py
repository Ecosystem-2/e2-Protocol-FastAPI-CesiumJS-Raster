"""Climate indices domain layer.

This module provides domain models, repositories, and services for climate index asset management.
"""

# Domain models
from app.climate_indices.models import (
    TimeRange,
    StorageInfo,
    AssetStorage,
    AssetStyle,
    AssetIngestRequest,
    RasterSummary,
    AssetIngestResult,
    AssetRecord,
    AssetPersistenceResult,
    PolygonGeometry,
    SelectionStatistics,
    PolygonWithStatistics,
    PolygonSelectionRecord,
    CZMLExportOptions,
    CZMLRecord,
)

# Repositories
from app.climate_indices.asset_repository import AssetRepository
from app.climate_indices.selections_repository import SelectionRepository
from app.climate_indices.czml_repository import CZMLRepository

# Services
from app.climate_indices.blob_storage import GCSBlobStore
from app.climate_indices.asset_service import ingest_upload, persist_climate_index

__all__ = [
    # Domain models
    "TimeRange",
    "StorageInfo",
    "AssetStorage",
    "AssetStyle",
    "AssetIngestRequest",
    "RasterSummary",
    "AssetIngestResult",
    "AssetRecord",
    "AssetPersistenceResult",
    "PolygonGeometry",
    "SelectionStatistics",
    "PolygonWithStatistics",
    "PolygonSelectionRecord",
    "CZMLExportOptions",
    "CZMLRecord",
    # Repositories
    "AssetRepository",
    "SelectionRepository",
    "CZMLRepository",
    # Services
    "GCSBlobStore",
    "ingest_upload",
    "persist_climate_index",
]
