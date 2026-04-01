"""Repository for CZML document persistence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId  # type: ignore

from app.core.logging import get_logger
from app.db.mongo import get_sync_client

from .models import CZMLRecord, CZMLExportOptions

logger = get_logger(__name__)


class CZMLRepository:
    """Synchronous MongoDB repository for CZML documents."""

    def __init__(self, collection_name: str = "czml_documents"):
        """Initialise repository with CZML collection."""
        client = get_sync_client()
        db_name = os.getenv("MONGO_DB", "climate_indices")
        self.collection = client[db_name][collection_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Sparse unique index on czml_id (only indexes documents where czml_id exists)
        self.collection.create_index(
            [("czml_id", 1)],
            unique=True,
            sparse=True
        )
        # Index on selection_id for lookups
        self.collection.create_index([("selection_id", 1)])
        # Compound index for selection_id + index_type + visualisation_type
        self.collection.create_index([
            ("selection_id", 1),
            ("index_type", 1),
            ("export_options.visualisation_type", 1)
        ])
        # Index on created_at for sorting
        self.collection.create_index([("created_at", -1)])
        logger.debug("Ensured indexes for czml_documents collection")

    def save_czml(
        self,
        record: CZMLRecord
    ) -> tuple[str, bool]:
        """
        Insert or update CZML document.

        If a CZML with the same selection_id, index_type, and visualisation_type
        exists, replace it. Otherwise, insert a new document.

        Returns:
            tuple[str, bool]: (czml_id, was_replaced)
                - czml_id: The MongoDB ObjectId as string
                - was_replaced: True if existing record was replaced
        """
        doc = record.model_dump(by_alias=True, exclude={"id"})
        doc["updated_at"] = datetime.now(timezone.utc)

        # Find existing CZML by selection_id + index_type + visualisation_type
        vis_type = record.export_options.visualisation_type
        index_type = record.index_type
        existing = self.collection.find_one({
            "selection_id": record.selection_id,
            "index_type": index_type,
            "export_options.visualisation_type": vis_type
        })

        if existing:
            # Replace existing document, keeping the same _id
            czml_id = str(existing["_id"])
            doc["_id"] = existing["_id"]
            doc["created_at"] = existing.get("created_at", datetime.now(timezone.utc))

            self.collection.replace_one({"_id": existing["_id"]}, doc)
            logger.info(
                "Replaced existing CZML %s (selection: %s, index: %s, type: %s)",
                czml_id, record.selection_id, index_type, vis_type
            )
            return czml_id, True
        else:
            # Insert new document
            if "created_at" not in doc:
                doc["created_at"] = datetime.now(timezone.utc)
            result = self.collection.insert_one(doc)
            czml_id = str(result.inserted_id)
            logger.info(
                "Inserted new CZML %s (selection: %s, index: %s, type: %s)",
                czml_id, record.selection_id, index_type, vis_type
            )
            return czml_id, False

    def get_czml(self, czml_id: str) -> Optional[CZMLRecord]:
        """Fetch CZML document by MongoDB ObjectId."""
        try:
            oid = ObjectId(czml_id)
        except Exception:
            logger.warning("Invalid czml_id provided: %s", czml_id)
            return None

        doc = self.collection.find_one({"_id": oid})
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return CZMLRecord.model_validate(doc)

    def get_czml_by_czml_id(self, czml_id: str) -> Optional[CZMLRecord]:
        """Fetch CZML document by frontend-generated czml_id (UUID)."""
        doc = self.collection.find_one({"czml_id": czml_id})
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return CZMLRecord.model_validate(doc)

    def get_czml_by_selection(
        self,
        selection_id: str,
        index_type: Optional[str] = None,
        visualisation_type: Optional[str] = None
    ) -> List[CZMLRecord]:
        """
        Fetch all CZML documents for a selection.

        Args:
            selection_id: The selection ObjectId as string
            index_type: Optional filter by climate index (ppet, wbgt, etc.)
            visualisation_type: Optional filter by type (bar, polygon)

        Returns:
            List of CZMLRecord documents
        """
        query = {"selection_id": selection_id}
        if index_type:
            query["index_type"] = index_type
        if visualisation_type:
            query["export_options.visualisation_type"] = visualisation_type

        cursor = self.collection.find(query).sort("created_at", -1)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(CZMLRecord.model_validate(doc))

        logger.info(
            "Retrieved %d CZML documents for selection %s (type=%s)",
            len(results), selection_id, visualisation_type
        )
        return results

    def list_czml(
        self,
        limit: int = 100,
        skip: int = 0
    ) -> List[CZMLRecord]:
        """List CZML documents with pagination."""
        cursor = (
            self.collection.find()
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(CZMLRecord.model_validate(doc))

        logger.info("Retrieved %d CZML documents (skip=%d, limit=%d)", len(results), skip, limit)
        return results

    def delete_czml(self, czml_id: str) -> bool:
        """Delete CZML document by ID. Returns True if deleted."""
        try:
            oid = ObjectId(czml_id)
        except Exception:
            logger.warning("Invalid czml_id for deletion: %s", czml_id)
            return False

        result = self.collection.delete_one({"_id": oid})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info("Deleted CZML document: %s", czml_id)
        else:
            logger.warning("CZML document not found for deletion: %s", czml_id)
        return deleted

    def delete_by_selection(self, selection_id: str) -> int:
        """Delete all CZML documents for a selection. Returns count deleted."""
        result = self.collection.delete_many({"selection_id": selection_id})
        logger.info(
            "Deleted %d CZML documents for selection: %s",
            result.deleted_count, selection_id
        )
        return result.deleted_count
