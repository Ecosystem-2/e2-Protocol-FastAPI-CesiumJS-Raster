"""Repository for polygon selection persistence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId  # type: ignore

from app.core.logging import get_logger
from app.db.mongo import get_sync_client

from .models import PolygonSelectionRecord

logger = get_logger(__name__)


class SelectionRepository:
    """Synchronous MongoDB repository for polygon selection documents."""

    def __init__(self, collection_name: str = "polygon_selections"):
        """Initialise repository with selections collection."""
        client = get_sync_client()
        db_name = os.getenv("MONGO_DB", "climate_indices")
        self.collection = client[db_name][collection_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Sparse unique index on selection_id (only indexes documents where selection_id exists)
        self.collection.create_index(
            [("selection_id", 1)],
            unique=True,
            sparse=True
        )
        # Non-unique index on title for search (allows duplicate titles)
        self.collection.create_index([("title", 1)])
        # Index on tags for filtering
        self.collection.create_index([("tags", 1)])
        # Index on created_at for sorting
        self.collection.create_index([("created_at", -1)])
        logger.debug("Ensured indexes for polygon_selections collection")

    def save_selection(
        self,
        record: PolygonSelectionRecord
    ) -> tuple[str, bool]:
        """
        Insert or update selection by selection_id.

        If the record has a selection_id and a selection with the same selection_id exists,
        replace it entirely. Otherwise, insert a new selection.

        Returns:
            tuple[str, bool]: (selection_id, was_replaced)
                - selection_id: The MongoDB ObjectId as string
                - was_replaced: True if existing record was replaced, False if newly inserted
        """
        doc = record.model_dump(by_alias=True, exclude={"id"})
        doc["updated_at"] = datetime.now(timezone.utc)

        # Only upsert by selection_id if selection_id is provided
        existing = None
        if record.selection_id:
            existing = self.collection.find_one({"selection_id": record.selection_id})

        if existing:
            # Replace existing document, keeping the same _id
            mongo_id = str(existing["_id"])
            doc["_id"] = existing["_id"]  # Preserve original _id
            doc["created_at"] = existing.get("created_at", datetime.now(timezone.utc))  # Preserve creation timestamp

            self.collection.replace_one({"_id": existing["_id"]}, doc)
            logger.info("Replaced existing selection %s (selection_id: %s)", mongo_id, record.selection_id)
            return mongo_id, True
        else:
            # Insert new document
            if "created_at" not in doc:
                doc["created_at"] = datetime.now(timezone.utc)
            result = self.collection.insert_one(doc)
            mongo_id = str(result.inserted_id)
            logger.info("Inserted new selection %s (selection_id: %s, title: %s)", mongo_id, record.selection_id, record.title)
            return mongo_id, False

    def get_selection(self, selection_id: str) -> Optional[PolygonSelectionRecord]:
        """Fetch selection by MongoDB ObjectId."""
        try:
            oid = ObjectId(selection_id)
        except Exception:
            logger.warning("Invalid selection_id provided: %s", selection_id)
            return None

        doc = self.collection.find_one({"_id": oid})
        if not doc:
            return None

        # Cast ObjectId to string for Pydantic validation
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return PolygonSelectionRecord.model_validate(doc)

    def get_selection_by_name(self, name: str) -> Optional[PolygonSelectionRecord]:
        """Fetch selection by case-insensitive title."""
        doc = self.collection.find_one(
            {"title": name},
            collation={"locale": "en", "strength": 2}
        )
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return PolygonSelectionRecord.model_validate(doc)

    def get_selection_by_selection_id(self, selection_id: str) -> Optional[PolygonSelectionRecord]:
        """Fetch selection by frontend-generated selection_id (UUID)."""
        doc = self.collection.find_one({"selection_id": selection_id})
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return PolygonSelectionRecord.model_validate(doc)

    def list_selections(
        self,
        tags: Optional[list[str]] = None,
        limit: int = 100,
        skip: int = 0
    ) -> list[PolygonSelectionRecord]:
        """List selections with optional tag filtering."""
        query = {}
        if tags:
            query["tags"] = {"$in": tags}

        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(PolygonSelectionRecord.model_validate(doc))

        logger.info(
            "Retrieved %d selections (tags=%s, skip=%d, limit=%d)",
            len(results), tags, skip, limit
        )
        return results

    def delete_selection(self, selection_id: str) -> bool:
        """Delete selection by ID. Returns True if deleted."""
        try:
            oid = ObjectId(selection_id)
        except Exception:
            logger.warning("Invalid selection_id provided for deletion: %s", selection_id)
            return False

        result = self.collection.delete_one({"_id": oid})
        deleted = result.deleted_count > 0

        if deleted:
            logger.info("Deleted selection %s", selection_id)
        else:
            logger.warning("Selection not found for deletion: %s", selection_id)

        return deleted

    def count_selections(self, tags: Optional[list[str]] = None) -> int:
        """Count total number of selections, optionally filtered by tags."""
        query = {}
        if tags:
            query["tags"] = {"$in": tags}
        return self.collection.count_documents(query)
