from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId  # type: ignore
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.db.mongo import get_sync_client

from .models import AssetRecord

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

    def insert_asset(self, asset: AssetRecord) -> str:
        doc = asset.model_dump(by_alias=True, exclude_none=True)
        result = self.collection.insert_one(doc)
        asset_id = str(result.inserted_id)
        logger.info("Inserted asset %s into MongoDB", asset_id)
        return asset_id
    
    def upsert_asset_by_filename(self, asset: AssetRecord) -> tuple[str, bool]:
        """
        Insert or update asset by filename.
        
        If an asset with the same filename exists, replace it entirely.
        Otherwise, insert a new asset.
        
        Returns:
            tuple[str, bool]: (asset_id, was_replaced)
                - asset_id: The MongoDB ObjectId as string
                - was_replaced: True if existing record was replaced, False if newly inserted
        """
        doc = asset.model_dump(by_alias=True, exclude_none=True)
        
        # Find existing asset by filename
        existing = self.collection.find_one({"filename": asset.filename})
        
        if existing:
            # Replace existing document, keeping the same _id
            asset_id = str(existing["_id"])
            doc["_id"] = existing["_id"]  # Preserve original _id
            doc["created_at"] = existing.get("created_at")  # Preserve creation timestamp
            doc["updated_at"] = datetime.utcnow()  # Update modification timestamp
            
            self.collection.replace_one({"_id": existing["_id"]}, doc)
            logger.info("Replaced existing asset %s (filename: %s)", asset_id, asset.filename)
            return asset_id, True
        else:
            # Insert new document
            result = self.collection.insert_one(doc)
            asset_id = str(result.inserted_id)
            logger.info("Inserted new asset %s (filename: %s)", asset_id, asset.filename)
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

    def list_assets(self, limit: int = 100, skip: int = 0) -> list[AssetRecord]:
        """List all assets with pagination."""
        cursor = self.collection.find().skip(skip).limit(limit).sort("created_at", -1)
        assets = []
        for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            assets.append(AssetRecord.model_validate(doc))
        logger.info("Retrieved %d assets (skip=%d, limit=%d)", len(assets), skip, limit)
        return assets

    def count_assets(self) -> int:
        """Count total number of assets in the collection."""
        return self.collection.count_documents({})

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
