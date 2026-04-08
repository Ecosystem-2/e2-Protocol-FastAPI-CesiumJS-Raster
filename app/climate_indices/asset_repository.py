"""MongoDB repository for asset documents."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId  # type: ignore

from app.core.logging import get_logger
from app.db.mongo import get_sync_client
from app.climate_indices.models import AssetRecord

logger = get_logger(__name__)


def _get_collection():
    client = get_sync_client()
    db_name = os.getenv("MONGO_DB", "climate_indices")
    collection_name = os.getenv("MONGO_ASSETS_COLLECTION", "assets")
    return client[db_name][collection_name]


class AssetRepository:
    """Synchronous Mongo repository for asset documents."""

    def __init__(self):
        self.collection = _get_collection()
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Sparse unique index on raster_id (only indexes documents where raster_id exists)
        self.collection.create_index(
            [("raster_id", 1)],
            unique=True,
            sparse=True
        )
        # Non-unique index on filename for search (not upsert)
        self.collection.create_index([("filename", 1)])
        # Index on index_type for filtering
        self.collection.create_index([("index_type", 1)])
        # Index on created_at for sorting
        self.collection.create_index([("created_at", -1)])
        # Sparse indexes for ownership filtering
        self.collection.create_index([("user_id", 1)], sparse=True)
        self.collection.create_index([("project_id", 1)], sparse=True)
        logger.debug("Ensured indexes for assets collection")

    def insert_asset(self, asset: AssetRecord) -> str:
        doc = asset.model_dump(by_alias=True, exclude_none=True)
        result = self.collection.insert_one(doc)
        asset_id = str(result.inserted_id)
        logger.info("Inserted asset %s into MongoDB", asset_id)
        return asset_id

    def upsert_asset(self, asset: AssetRecord) -> tuple[str, bool]:
        """
        Insert or update asset by raster_id.

        If the asset has a raster_id and an asset with the same raster_id exists,
        replace it entirely. Otherwise, insert a new asset.

        Returns:
            tuple[str, bool]: (asset_id, was_replaced)
                - asset_id: The MongoDB ObjectId as string
                - was_replaced: True if existing record was replaced, False if newly inserted
        """
        doc = asset.model_dump(by_alias=True, exclude_none=True)

        # Only upsert by raster_id if raster_id is provided
        existing = None
        if asset.raster_id:
            existing = self.collection.find_one({"raster_id": asset.raster_id})

        if existing:
            # Replace existing document, keeping the same _id
            asset_id = str(existing["_id"])
            doc["_id"] = existing["_id"]  # Preserve original _id
            doc["created_at"] = existing.get("created_at")  # Preserve creation timestamp
            doc["updated_at"] = datetime.now(timezone.utc)  # Update modification timestamp

            self.collection.replace_one({"_id": existing["_id"]}, doc)
            logger.info("Replaced existing asset %s (raster_id: %s)", asset_id, asset.raster_id)
            return asset_id, True
        else:
            # Insert new document
            result = self.collection.insert_one(doc)
            asset_id = str(result.inserted_id)
            logger.info("Inserted new asset %s (raster_id: %s, filename: %s)", asset_id, asset.raster_id, asset.filename)
            return asset_id, False

    def get_asset(self, asset_id: str) -> Optional[AssetRecord]:
        try:
            oid = ObjectId(asset_id)
        except Exception:
            logger.warning("Invalid asset_id provided: %s", asset_id)
            return None
        doc = self.collection.find_one({"_id": oid})
        if not doc:
            return None
        # Cast ObjectId to string for Pydantic validation
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return AssetRecord.model_validate(doc)

    def list_assets(
        self,
        limit: int = 100,
        skip: int = 0,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[AssetRecord]:
        """List assets with pagination and optional ownership filtering."""
        query_filter: dict[str, Any] = {}
        if user_id:
            query_filter["user_id"] = user_id
        if project_id:
            query_filter["project_id"] = project_id

        cursor = self.collection.find(query_filter).skip(skip).limit(limit).sort("created_at", -1)
        assets = []
        for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            assets.append(AssetRecord.model_validate(doc))
        logger.info("Retrieved %d assets (skip=%d, limit=%d, user_id=%s, project_id=%s)", len(assets), skip, limit, user_id, project_id)
        return assets

    def count_assets(self, user_id: Optional[str] = None, project_id: Optional[str] = None) -> int:
        """Count total number of assets, optionally filtered by ownership."""
        query_filter: dict[str, Any] = {}
        if user_id:
            query_filter["user_id"] = user_id
        if project_id:
            query_filter["project_id"] = project_id
        return self.collection.count_documents(query_filter)

    def search_assets(self, query: str, limit: int = 20) -> list[AssetRecord]:
        """Search assets by filename, index_type, or units using fuzzy matching."""
        # Use MongoDB text search or regex for fuzzy matching
        search_filter = {
            "$or": [
                {"filename": {"$regex": query, "$options": "i"}},
                {"index_type": {"$regex": query, "$options": "i"}},
                {"units": {"$regex": query, "$options": "i"}},
            ]
        }
        cursor = self.collection.find(search_filter).limit(limit).sort("created_at", -1)
        assets = []
        for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            assets.append(AssetRecord.model_validate(doc))
        logger.info("Found %d assets matching query '%s'", len(assets), query)
        return assets

    def get_asset_by_filename(self, filename: str) -> Optional[AssetRecord]:
        """Get asset by exact filename match."""
        doc = self.collection.find_one({"filename": filename})
        if not doc:
            return None
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return AssetRecord.model_validate(doc)

    def get_asset_by_raster_id(self, raster_id: str) -> Optional[AssetRecord]:
        """Get asset by frontend-generated raster_id (UUID)."""
        doc = self.collection.find_one({"raster_id": raster_id})
        if not doc:
            return None
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return AssetRecord.model_validate(doc)

    def delete_asset(self, asset_id: str) -> bool:
        """Delete asset by MongoDB ObjectId. Returns True if deleted."""
        try:
            oid = ObjectId(asset_id)
        except Exception:
            logger.warning("Invalid asset_id provided for deletion: %s", asset_id)
            return False

        result = self.collection.delete_one({"_id": oid})
        deleted = result.deleted_count > 0

        if deleted:
            logger.info("Deleted asset %s from MongoDB", asset_id)
        else:
            logger.warning("Asset not found for deletion: %s", asset_id)

        return deleted

    def update_asset_metadata(
        self,
        asset_id: str,
        *,
        index_type: Optional[str] = None,
        units: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[AssetRecord]:
        """
        Update asset metadata fields (not file replacement).

        Only provided fields are updated; None values are ignored.
        Returns the updated asset, or None if not found.
        """
        try:
            oid = ObjectId(asset_id)
        except Exception:
            logger.warning("Invalid asset_id provided for update: %s", asset_id)
            return None

        update_fields: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc)
        }

        if index_type is not None:
            update_fields["index_type"] = index_type
        if units is not None:
            update_fields["units"] = units
        if user_id is not None:
            update_fields["user_id"] = user_id
        if project_id is not None:
            update_fields["project_id"] = project_id

        if len(update_fields) == 1:  # Only updated_at
            logger.warning("No fields to update for asset %s", asset_id)
            return self.get_asset(asset_id)

        result = self.collection.update_one({"_id": oid}, {"$set": update_fields})

        if result.matched_count == 0:
            logger.warning("Asset not found for update: %s", asset_id)
            return None

        logger.info("Updated asset %s: %s", asset_id, list(update_fields.keys()))
        return self.get_asset(asset_id)
