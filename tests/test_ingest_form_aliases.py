# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for /ingest multipart form field names."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.api.climate.endpoints import ingest as ingest_endpoint
from app.climate_indices.models import (
    AssetPersistenceResult,
    AssetStorage,
    RasterSummary,
    StorageInfo,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def stub_persistence(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    captured_requests: list[object] = []

    monkeypatch.setattr(ingest_endpoint, "_initialise_storage", lambda: (object(), object()))

    def fake_persist_climate_index(payload, request, *, blob_store, repo):
        captured_requests.append(request)
        return AssetPersistenceResult(
            asset=request,
            asset_id="asset-123",
            raster_id=request.raster_id,
            user_id=request.user_id,
            project_id=request.project_id,
            storage=AssetStorage(
                raw=StorageInfo(kind="gcs", uri="gs://bucket/uploads/test.tif"),
                cog=StorageInfo(kind="gcs", uri="gs://bucket/uploads/test.cog.tif"),
            ),
            raster=RasterSummary(epsg=4326),
            replaced=False,
        )

    monkeypatch.setattr(ingest_endpoint, "persist_climate_index", fake_persist_climate_index)
    return captured_requests


def _post_ingest(client: TestClient, data: dict[str, str]):
    return client.post(
        "/api/climate-indices/ingest",
        files={"file": ("test.tif", BytesIO(b"fake-tiff-bytes"), "image/tiff")},
        data=data,
    )


def test_ingest_accepts_docs_snake_case_form_fields(
    client: TestClient,
    stub_persistence: list[object],
) -> None:
    response = _post_ingest(
        client,
        {
            "index_type": "ppet",
            "time_start": "2001-01-01T00:00:00Z",
            "time_end": "2070-12-30T23:59:59Z",
            "raster_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "user-123",
            "project_id": "project-123",
            "custom_group": "group-123",
            "pallete": "viridis",
        },
    )

    assert response.status_code == 201
    request = stub_persistence[0]
    assert request.index_type == "ppet"
    assert request.raster_id == "550e8400-e29b-41d4-a716-446655440000"
    assert request.user_id == "user-123"
    assert request.project_id == "project-123"
    assert request.custom_group == "group-123"
    assert request.style.pallete == "viridis"


def test_ingest_keeps_accepting_demo_camel_case_form_fields(
    client: TestClient,
    stub_persistence: list[object],
) -> None:
    response = _post_ingest(
        client,
        {
            "indexType": "ppet",
            "timeStart": "2001-01-01T00:00:00Z",
            "timeEnd": "2070-12-30T23:59:59Z",
            "rasterID": "550e8400-e29b-41d4-a716-446655440000",
            "userID": "user-123",
            "projectID": "project-123",
            "customGroup": "group-123",
            "pallete": "viridis",
        },
    )

    assert response.status_code == 201
    request = stub_persistence[0]
    assert request.index_type == "ppet"
    assert request.raster_id == "550e8400-e29b-41d4-a716-446655440000"
    assert request.user_id == "user-123"
    assert request.project_id == "project-123"
    assert request.custom_group == "group-123"
    assert request.style.pallete == "viridis"
