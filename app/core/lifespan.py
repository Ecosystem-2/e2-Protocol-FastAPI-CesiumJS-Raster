from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.mongo import get_async_client, close_async_client
from app.core.logging import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_async_client()
    logger.info("Async MongoDB client initialised")
    try:
        yield
    finally:
        close_async_client()
        logger.info("Async MongoDB client closed")