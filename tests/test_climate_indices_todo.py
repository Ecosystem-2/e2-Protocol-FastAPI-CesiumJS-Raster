"""Unit tests for climate_indices domain layer.

Tests the business logic independent of API endpoints.
"""

import pytest
from datetime import datetime
from pathlib import Path


class TestModels:
    """Test Pydantic models."""
    
    def test_time_range_model(self):
        """Test TimeRange model."""
        from app.climate_indices.models import TimeRange
        
        tr = TimeRange(
            start=datetime(2020, 1, 1),
            end=datetime(2050, 12, 31)
        )
        
        assert tr.start.year == 2020
        assert tr.end.year == 2050
    
    def test_asset_ingest_request(self):
        """Test AssetIngestRequest model."""
        from app.climate_indices.models import AssetIngestRequest, TimeRange
        
        req = AssetIngestRequest(
            index_type="ppet",
            time_range=TimeRange(start=datetime(2020, 1, 1)),
            units="ratio",
            filename="test.tif"
        )
        
        assert req.index_type == "ppet"
        assert req.units == "ratio"
        assert req.filename == "test.tif"
    
    def test_raster_summary_from_metadata(self):
        """Test RasterSummary.from_raster_metadata()."""
        from app.climate_indices.models import RasterSummary
        
        raw_metadata = {
            "epsg": 4326,
            "bounds": {"left": 117.0, "bottom": 4.0, "right": 119.0, "top": 6.0},
            "resolution": (0.01, 0.01),
            "dtype": "float32",
            "nodata": -9999.0,
            "min": 0.0,
            "max": 2.0,
            "mean": 0.85,
            "std": 0.42
        }
        
        summary = RasterSummary.from_raster_metadata(raw_metadata)
        
        assert summary.epsg == 4326
        assert summary.bounds["left"] == 117.0
        assert summary.resolution == (0.01, 0.01)
        assert summary.nodata == -9999.0


class TestGCSBlobStore:
    """Test GCS blob storage (requires mocking or credentials)."""
    
    def test_gcs_blob_store_init(self):
        """Test GCSBlobStore initialisation."""
        pytest.skip("Requires google-cloud-storage and credentials")
    
    def test_save_bytes(self):
        """Test saving bytes to GCS."""
        pytest.skip("Requires GCS credentials and actual bucket")


class TestAssetRepository:
    """Test MongoDB repository (requires MongoDB connection)."""
    
    def test_repository_init(self):
        """Test AssetRepository initialisation."""
        pytest.skip("Requires MongoDB connection")
    
    def test_upsert_by_filename(self):
        """Test upsert_asset_by_filename logic."""
        pytest.skip("Requires MongoDB connection")


class TestServiceLayer:
    """Test service layer business logic."""
    
    @pytest.fixture
    def sample_geotiff_path(self):
        """Get path to sample GeoTIFF."""
        geotiff_dir = Path("data/p-pet-ratio/geotif")
        tiff_files = list(geotiff_dir.glob("*.tif"))
        if not tiff_files:
            pytest.skip("No test GeoTIFF available")
        return tiff_files[0]
    
    def test_ingest_upload(self, sample_geotiff_path):
        """Test ingest_upload function."""
        from app.climate_indices.service import ingest_upload
        from app.climate_indices.models import AssetIngestRequest, TimeRange
        
        with open(sample_geotiff_path, "rb") as f:
            payload = f.read()
        
        request = AssetIngestRequest(
            index_type="ppet",
            units="ratio",
            filename=sample_geotiff_path.name
        )
        
        result = ingest_upload(payload, request)
        
        # Verify result structure
        assert result.asset.index_type == "ppet"
        assert result.raster.epsg == 4326  # Always converted
        assert result.raster.bounds is not None
        assert result.raster.resolution is not None
    
    def test_persist_climate_index(self):
        """Test persist_climate_index function."""
        pytest.skip("Requires GCS and MongoDB setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
