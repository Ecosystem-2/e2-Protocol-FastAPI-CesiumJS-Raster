
"""
Unified MongoDB setup for both asynchronous (Motor) and synchronous (PyMongo) access.

- Reads MongoDB URI from environment or .env (MONGO_URI)
- Provides shared async and sync clients (global singletons)
- Safe for reuse across FastAPI app and standalone scripts
"""

from __future__ import annotations

import os
from typing import Optional, AsyncGenerator, Generator, TYPE_CHECKING
from contextlib import asynccontextmanager, contextmanager

from app.core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import MongoClient

# Global singletons (lazy-initialised)
_async_client: Optional["AsyncIOMotorClient"] = None
_sync_client: Optional["MongoClient"] = None


# ---------------------------------------------------------------------------
# Utility: get MongoDB URI
# ---------------------------------------------------------------------------

def get_mongo_uri() -> str:
    """
    Read MongoDB URI from environment or .env file.
    Defaults to local instance if not defined.
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
    except Exception:
        # dotenv is optional; skip if not installed
        pass
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return uri


# ---------------------------------------------------------------------------
# Internal: build client kwargs (Atlas/non-Atlas safe)
# ---------------------------------------------------------------------------

def _client_kwargs_for_uri(uri: str) -> dict:
    """
    Return kwargs for Mongo clients that are safe for Atlas and on-prem.
    - Adds a reasonable server selection timeout
    - For mongodb+srv (Atlas), attempts to provide CA bundle via certifi when available
    """
    kwargs: dict = {
        "serverSelectionTimeoutMS": int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
    }

    is_srv = uri.startswith("mongodb+srv://")
    force_tls = os.getenv("MONGO_FORCE_TLS", "0") in {"1", "true", "True"}

    if is_srv or force_tls:
        try:
            import certifi  # type: ignore

            kwargs["tlsCAFile"] = certifi.where()
        except Exception:  # certifi not installed or not available
            logger.warning(
                "TLS CA bundle not provided (install 'certifi' to avoid SSL issues with Atlas)."
            )

    return kwargs


# ---------------------------------------------------------------------------
# Async (Motor) client setup
# ---------------------------------------------------------------------------

def _new_async_client(uri: Optional[str] = None):
    """Create a new AsyncIOMotorClient (never cached)."""
    from motor.motor_asyncio import AsyncIOMotorClient  # Lazy import

    mongo_uri = uri or get_mongo_uri()
    kwargs = _client_kwargs_for_uri(mongo_uri)
    logger.info(f"Connecting (async) to MongoDB at {mongo_uri}")
    return AsyncIOMotorClient(mongo_uri, **kwargs)


def get_async_client(uri: Optional[str] = None):
    """Return the global AsyncIOMotorClient instance."""
    global _async_client
    if _async_client is None:
        _async_client = _new_async_client(uri=uri)
    return _async_client


def close_async_client() -> None:
    """Close the global async client."""
    global _async_client
    if _async_client:
        _async_client.close()
        _async_client = None
        logger.info("Async MongoDB client closed.")


@asynccontextmanager
async def async_session(client=None) -> AsyncGenerator:
    """
    Async context manager yielding a Motor ClientSession.
    Example:
        async with async_session() as session:
            async with session.start_transaction():
                ...
    """
    created_client = False
    if client is None:
        # Use a short-lived client for this session to avoid closing the global one
        client = _new_async_client()
        created_client = True

    session = await client.start_session()
    try:
        yield session
    finally:
        await session.end_session()
        if created_client:
            client.close()


# ---------------------------------------------------------------------------
# Sync (PyMongo) client setup
# ---------------------------------------------------------------------------

def _new_sync_client(uri: Optional[str] = None):
    """Create a new synchronous MongoClient (never cached)."""
    from pymongo import MongoClient  # Lazy import

    mongo_uri = uri or get_mongo_uri()
    kwargs = _client_kwargs_for_uri(mongo_uri)
    logger.info(f"Connecting (sync) to MongoDB at {mongo_uri}")
    return MongoClient(mongo_uri, **kwargs)


def get_sync_client(uri: Optional[str] = None):
    """Return the global synchronous MongoClient instance."""
    global _sync_client
    if _sync_client is None:
        _sync_client = _new_sync_client(uri=uri)
    return _sync_client


def close_sync_client() -> None:
    """Close the global sync client."""
    global _sync_client
    if _sync_client:
        _sync_client.close()
        _sync_client = None
        logger.info("Sync MongoDB client closed.")


@contextmanager
def sync_session(client=None) -> Generator:
    """
    Context manager yielding a PyMongo ClientSession.
    Example:
        with sync_session() as session:
            session.with_transaction(lambda s: ...)
    """
    created_client = False
    if client is None:
        # Use a short-lived client for this session to avoid closing the global one
        client = _new_sync_client()
        created_client = True

    session = client.start_session()
    try:
        yield session
    finally:
        session.end_session()
        if created_client:
            client.close()


__all__ = [
    "get_mongo_uri",
    "get_async_client",
    "close_async_client",
    "async_session",
    "get_sync_client",
    "close_sync_client",
    "sync_session",
]