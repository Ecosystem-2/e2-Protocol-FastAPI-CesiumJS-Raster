"""Demo configuration endpoint.

Serves frontend configuration values from environment variables,
enabling centralised management of API base URL and Cesium tokens.
"""

import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class DemoConfig(BaseModel):
    """Configuration values for demo frontend."""
    api_base: str
    cesium_ion_token: str


def _get_api_base() -> str:
    """Determine API base URL from environment or request context."""
    # Priority: explicit env var > default localhost
    return os.getenv(
        "DEMO_API_BASE",
        "http://localhost:8080/api/climate-indices"
    )


def _get_cesium_token() -> str:
    """Get Cesium Ion access token from environment."""
    return os.getenv(
        "CESIUM_ION_TOKEN",
        ""  # Empty default - frontend should handle missing token gracefully
    )


@router.get(
    "/config",
    response_model=DemoConfig,
    summary="Get demo frontend configuration",
    description="Returns configuration values for the demo frontend including "
                "API base URL and Cesium Ion token. Values are sourced from "
                "environment variables.",
)
async def get_demo_config() -> DemoConfig:
    """Return frontend configuration from environment variables."""
    return DemoConfig(
        api_base=_get_api_base(),
        cesium_ion_token=_get_cesium_token(),
    )
