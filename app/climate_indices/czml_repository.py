"""Repository for CZML document persistence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional, List

from bson import ObjectId  # type: ignore

from app.core.logging import get_logger
from app.db.mongo import get_sync_client
from app.climate_indices.models import CZMLRecord

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
        # Sparse unique index on czmlID (only indexes documents where czmlID exists)
        self.collection.create_index(
            [("czmlID", 1)],
            unique=True,
            sparse=True
        )
        # Index on selectionRef for lookups
        self.collection.create_index([("selectionRef", 1)])
        # Compound index for selectionRef + indexType + visualisationType
        self.collection.create_index([
            ("selectionRef", 1),
            ("indexType", 1),
            ("exportOptions.visualisationType", 1)
        ])
        # Index on createdAt for sorting
        self.collection.create_index([("createdAt", -1)])
        # Sparse indexes for ownership filtering
        self.collection.create_index([("userID", 1)], sparse=True)
        self.collection.create_index([("projectID", 1)], sparse=True)
        logger.debug("Ensured indexes for czml_documents collection")

    def save_czml(
        self,
        record: CZMLRecord
    ) -> tuple[str, bool]:
        """
        Insert or update CZML document.

        If a CZML with the same selection_ref, index_type, and visualisation_type
        exists, replace it. Otherwise, insert a new document.

        Returns:
            tuple[str, bool]: (czml_id, was_replaced)
                - czml_id: The MongoDB ObjectId as string
                - was_replaced: True if existing record was replaced
        """
        doc = record.model_dump(by_alias=True, exclude={"id"}, exclude_none=True)
        doc["updatedAt"] = datetime.now(timezone.utc)

        # Find existing CZML by selectionRef + indexType + visualisationType
        vis_type = record.export_options.visualisation_type
        index_type = record.index_type
        existing = self.collection.find_one({
            "selectionRef": record.selection_ref,
            "indexType": index_type,
            "exportOptions.visualisationType": vis_type
        })

        if existing:
            # Replace existing document, keeping the same _id
            czml_id = str(existing["_id"])
            doc["_id"] = existing["_id"]
            doc["createdAt"] = existing.get("createdAt", datetime.now(timezone.utc))

            self.collection.replace_one({"_id": existing["_id"]}, doc)
            logger.info(
                "Replaced existing CZML %s (selection: %s, index: %s, type: %s)",
                czml_id, record.selection_ref, index_type, vis_type
            )
            return czml_id, True
        else:
            # Insert new document
            if "createdAt" not in doc:
                doc["createdAt"] = datetime.now(timezone.utc)
            result = self.collection.insert_one(doc)
            czml_id = str(result.inserted_id)
            logger.info(
                "Inserted new CZML %s (selection: %s, index: %s, type: %s)",
                czml_id, record.selection_ref, index_type, vis_type
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
        """Fetch CZML document by frontend-generated czmlID (UUID)."""
        doc = self.collection.find_one({"czmlID": czml_id})
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return CZMLRecord.model_validate(doc)

    def get_czml_by_selection(
        self,
        selection_ref: str,
        index_type: Optional[str] = None,
        visualisation_type: Optional[str] = None
    ) -> List[CZMLRecord]:
        """
        Fetch all CZML documents for a selection.

        Args:
            selection_ref: The selection MongoDB ObjectId as string
            index_type: Optional filter by climate index (ppet, wbgt, etc.)
            visualisation_type: Optional filter by type (bar, polygon, polygon2d, circle2d)

        Returns:
            List of CZMLRecord documents
        """
        query = {"selectionRef": selection_ref}
        if index_type:
            query["indexType"] = index_type
        if visualisation_type:
            query["exportOptions.visualisationType"] = visualisation_type

        cursor = self.collection.find(query).sort("createdAt", -1)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(CZMLRecord.model_validate(doc))

        logger.info(
            "Retrieved %d CZML documents for selection %s (type=%s)",
            len(results), selection_ref, visualisation_type
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
            .sort("createdAt", -1)
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

    def update_czml_metadata(
        self,
        czml_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[CZMLRecord]:
        """
        Update CZML metadata fields without regenerating the stored CZML document.

        Only provided fields are updated. Returns the updated document, or None
        when the id is invalid or no matching document exists.
        """
        try:
            oid = ObjectId(czml_id)
        except Exception:
            logger.warning("Invalid czml_id provided for update: %s", czml_id)
            return None

        update_fields: dict[str, Any] = {
            "updatedAt": datetime.now(timezone.utc)
        }

        if title is not None:
            update_fields["title"] = title
        if description is not None:
            update_fields["description"] = description
        if user_id is not None:
            update_fields["userID"] = user_id
        if project_id is not None:
            update_fields["projectID"] = project_id

        if len(update_fields) == 1:
            logger.warning("No fields to update for CZML document %s", czml_id)
            return self.get_czml(czml_id)

        result = self.collection.update_one({"_id": oid}, {"$set": update_fields})
        if result.matched_count == 0:
            logger.warning("CZML document not found for update: %s", czml_id)
            return None

        logger.info("Updated CZML document %s: %s", czml_id, list(update_fields.keys()))
        return self.get_czml(czml_id)
