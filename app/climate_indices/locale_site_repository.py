"""Repository for LocaleData and SiteData collections."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId  # type: ignore

from app.core.logging import get_logger
from app.db.mongo import get_sync_client

from .models import LocaleData, SiteData

logger = get_logger(__name__)


class LocaleSiteRepository:
    """Repository for managing localeData and siteData collections."""

    def __init__(
        self,
        locale_collection: str = "localeData",
        site_collection: str = "siteData"
    ):
        """Initialise repository with locale and site collections."""
        client = get_sync_client()
        db_name = os.getenv("MONGO_DB", "climate_indices")
        self.locale_collection = client[db_name][locale_collection]
        self.site_collection = client[db_name][site_collection]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # LocaleData indexes
        self.locale_collection.create_index([("localeID", 1)], unique=True)
        self.locale_collection.create_index([("title", 1)])

        # SiteData indexes
        self.site_collection.create_index([("siteID", 1)], unique=True)
        self.site_collection.create_index([("localeID", 1)])
        self.site_collection.create_index(
            [("title", 1)],
            collation={"locale": "en", "strength": 2}
        )
        logger.debug("Ensured indexes for localeData and siteData collections")

    def get_or_create_locale(
        self,
        locale_id: str,
        title: str = "Segama River",
        description: str = "Humid Heat Stress and PPET selection"
    ) -> str:
        """
        Get or create the default locale record.

        Returns the MongoDB ObjectId as string.
        """
        # Check if locale exists
        existing = self.locale_collection.find_one({"localeID": locale_id})

        if existing:
            return str(existing["_id"])

        # Create new locale
        locale = LocaleData(
            locale_id=locale_id,
            site_id=[],
            title=title,
            description=description,
            creation_date=datetime.now(timezone.utc)
        )

        doc = locale.model_dump(by_alias=True, exclude={"id"})
        result = self.locale_collection.insert_one(doc)
        locale_obj_id = str(result.inserted_id)

        logger.info("Created new locale: %s (localeID: %s)", locale_obj_id, locale_id)
        return locale_obj_id

    def add_site_to_locale(self, locale_id: str, site_id: str) -> None:
        """Add site ID to locale's siteID list (prevents duplicates)."""
        result = self.locale_collection.update_one(
            {"localeID": locale_id},
            {"$addToSet": {"siteID": site_id}}  # Add if not exists
        )
        if result.modified_count > 0:
            logger.info("Added site %s to locale %s", site_id, locale_id)
        else:
            logger.debug("Site %s already in locale %s", site_id, locale_id)

    def save_site(self, site: SiteData) -> tuple[str, bool]:
        """
        Save or update site by title (case-insensitive).

        Returns:
            tuple[str, bool]: (site_id UUID, was_replaced)
        """
        # Check if site with same title exists
        existing = self.site_collection.find_one(
            {"title": site.title},
            collation={"locale": "en", "strength": 2}
        )

        doc = site.model_dump(by_alias=True, exclude_unset=False)

        if existing:
            # Update existing site, preserve original siteID and creationDateTime
            self.site_collection.replace_one(
                {"siteID": existing["siteID"]},
                {
                    **doc,
                    "siteID": existing["siteID"],  # Keep original UUID
                    "creationDateTime": existing.get("creationDateTime", datetime.now(timezone.utc))
                }
            )
            logger.info("Updated site: %s (title: %s)", existing["siteID"], site.title)
            return existing["siteID"], True
        else:
            # Insert new site
            result = self.site_collection.insert_one(doc)
            logger.info("Created new site: %s (title: %s)", site.site_id, site.title)
            return site.site_id, False

    def get_site_by_title(self, title: str) -> Optional[SiteData]:
        """Fetch site by case-insensitive title."""
        doc = self.site_collection.find_one(
            {"title": title},
            collation={"locale": "en", "strength": 2}
        )
        if not doc:
            return None

        return SiteData.model_validate(doc)

    def list_sites(self, locale_id: Optional[str] = None) -> list[SiteData]:
        """List sites, optionally filtered by locale."""
        query = {}
        if locale_id:
            query["localeID"] = locale_id

        cursor = self.site_collection.find(query).sort("creationDateTime", -1)

        results = []
        for doc in cursor:
            results.append(SiteData.model_validate(doc))

        return results
