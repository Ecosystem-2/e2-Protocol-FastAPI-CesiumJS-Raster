# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Integration tests for reorganised climate API endpoints.

Tests all endpoints in the new structure:
- /ingest (metadata only)
- /ingest/store (persist to GCS + MongoDB)
- /tiles/{asset_id}/{z}/{x}/{y}.png
- /query/polygons/stats (zonal statistics)
- /query/polygons/pixels (raw pixel extraction)
- /assets, /assets/search, /assets/by-filename/{filename}

Run with:
    pytest tests/test_climate_endpoints.py -v
    pytest tests/test_climate_endpoints.py::test_ingest_metadata -v
"""

import pytest
import json
from pathlib import Path
from io import BytesIO

# Skip all tests if no test environment configured
pytestmark = pytest.mark.skipif(
    not Path("data/p-pet-ratio/geotif").exists(),
    reason="Test data not available"
)


class TestIngestEndpoints:
    """Test /ingest and /ingest/store endpoints."""
    
    @pytest.fixture
    def sample_geotiff(self):
        """Load a sample GeoTIFF for testing."""
        geotiff_dir = Path("data/p-pet-ratio/geotif")
        tiff_files = list(geotiff_dir.glob("*.tif"))
        if not tiff_files:
            pytest.skip("No GeoTIFF files found for testing")
        
        with open(tiff_files[0], "rb") as f:
            return {
                "filename": tiff_files[0].name,
                "content": f.read()
            }
    
    def test_ingest_metadata_only(self, client, sample_geotiff):
        """Test POST /api/climate-indices/ingest - metadata extraction only."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/climate-indices/ingest",
            files={"file": (sample_geotiff["filename"], BytesIO(sample_geotiff["content"]), "image/tiff")},
            data={
                "index_type": "ppet",
                "units": "ratio",
            }
        )
        
        assert response.status_code == 201
        result = response.json()
        
        # Verify structure
        assert "asset" in result
        assert "raster" in result
        assert result["asset"]["index_type"] == "ppet"
        assert result["asset"]["units"] == "ratio"
        
        # Verify raster metadata
        raster = result["raster"]
        assert raster["epsg"] == 4326  # Always converted to WGS84
        assert "bounds" in raster
        assert "resolution" in raster
        assert "nodata" in raster
    
    def test_ingest_and_store(self, client, sample_geotiff):
        """Test POST /api/climate-indices/ingest/store - full persistence."""
        pytest.skip("Requires GCS credentials and MongoDB connection")
        # Implementation would test actual storage
    
    def test_ingest_invalid_file_type(self, client):
        """Test rejection of non-GeoTIFF files."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/climate-indices/ingest",
            files={"file": ("test.txt", BytesIO(b"not a tiff"), "text/plain")},
            data={"index_type": "test"}
        )
        
        assert response.status_code == 415  # Unsupported Media Type


class TestTileEndpoint:
    """Test /tiles/{asset_id}/{z}/{x}/{y}.png endpoint."""
    
    def test_tile_rendering(self, client, test_asset_id):
        """Test GET /api/climate-indices/tiles/{asset_id}/{z}/{x}/{y}.png"""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_tile_with_custom_colormap(self, client, test_asset_id):
        """Test tile rendering with different colormap."""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_tile_outside_bounds(self, client, test_asset_id):
        """Test tile request outside asset bounds returns 404."""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_tile_invalid_colormap(self, client, test_asset_id):
        """Test invalid colormap name returns 400."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get(
            f"/api/climate-indices/tiles/{test_asset_id}/10/500/500.png",
            params={"colormap_name": "invalid_colormap_xyz"}
        )
        
        # Should return 400 for invalid colormap or 404 for missing asset
        assert response.status_code in [400, 404]


class TestPolygonEndpoints:
    """Test /query/polygons/* endpoints."""
    
    @pytest.fixture
    def test_polygon(self):
        """Simple test polygon within Segama bounds."""
        return {
            "type": "Polygon",
            "coordinates": [[
                [118.0, 5.0],
                [118.2, 5.0],
                [118.2, 5.2],
                [118.0, 5.2],
                [118.0, 5.0]
            ]]
        }
    
    def test_query_polygons_stats(self, client, test_asset_id, test_polygon):
        """Test POST /api/climate-indices/query/polygons/stats"""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_query_polygons_stats_multiple(self, client, test_polygon):
        """Test stats with multiple assets and polygons."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        polygons = [test_polygon, test_polygon]  # Two polygons
        
        response = client.post(
            "/api/climate-indices/query/polygons/stats",
            data={
                "asset_ids": "asset1,asset2",
                "polygons_geojson": json.dumps(polygons)
            }
        )
        
        # Will fail without valid assets, but tests endpoint routing
        assert response.status_code in [404, 200]
    
    def test_query_polygons_pixels_csv(self, client, test_asset_id, test_polygon):
        """Test POST /api/climate-indices/query/polygons/pixels with CSV format."""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_query_polygons_pixels_json(self, client, test_asset_id, test_polygon):
        """Test POST /api/climate-indices/query/polygons/pixels with JSON format."""
        pytest.skip("Requires existing asset in MongoDB")
    
    def test_query_polygons_pixels_invalid_format(self, client, test_polygon):
        """Test pixels endpoint with invalid format parameter."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/climate-indices/query/polygons/pixels",
            data={
                "asset_ids": "test_id",
                "polygons_geojson": json.dumps([test_polygon]),
                "format": "invalid_format"
            }
        )
        
        assert response.status_code == 400
        assert "csv" in response.json()["detail"].lower() or "json" in response.json()["detail"].lower()


class TestAssetEndpoints:
    """Test /assets/* endpoints."""
    
    def test_list_assets(self, client):
        """Test GET /api/climate-indices/assets"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/api/climate-indices/assets", params={"limit": 10, "skip": 0})
        
        assert response.status_code == 200
        result = response.json()
        
        assert "total" in result
        assert "assets" in result
        assert isinstance(result["assets"], list)
    
    def test_search_assets(self, client):
        """Test GET /api/climate-indices/assets/search"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/api/climate-indices/assets/search", params={"q": "ppet"})
        
        assert response.status_code == 200
        result = response.json()
        
        assert "assets" in result
        assert isinstance(result["assets"], list)
    
    def test_get_asset_by_filename(self, client):
        """Test GET /api/climate-indices/assets/by-filename/{filename}"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/api/climate-indices/assets/by-filename/nonexistent.tif")
        
        # Should return 404 if not found
        assert response.status_code == 404


class TestEndpointRouting:
    """Test that all endpoints are correctly routed."""
    
    def test_all_endpoints_registered(self, client):
        """Verify all expected endpoints are registered."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Get OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        paths = schema["paths"]
        
        # Verify all expected endpoints exist
        expected_paths = [
            "/api/climate-indices/ingest",
            "/api/climate-indices/ingest/store",
            "/api/climate-indices/tiles/{asset_id}/{z}/{x}/{y}.png",
            "/api/climate-indices/query/polygons/stats",
            "/api/climate-indices/query/polygons/pixels",
            "/api/climate-indices/assets",
            "/api/climate-indices/assets/search",
            "/api/climate-indices/assets/by-filename/{filename}",
        ]
        
        for path in expected_paths:
            assert path in paths, f"Expected endpoint {path} not found in API"
    
    def test_old_endpoint_removed(self, client):
        """Verify old /query/polygon endpoint is replaced."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/openapi.json")
        schema = response.json()
        
        # Old endpoint should NOT exist
        assert "/api/climate-indices/query/polygon" not in schema["paths"]


# Fixtures
@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def test_asset_id():
    """Mock asset ID for testing."""
    return "507f1f77bcf86cd799439011"  # Valid ObjectId format


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
