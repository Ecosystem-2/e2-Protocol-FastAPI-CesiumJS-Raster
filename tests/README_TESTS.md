# Climate API Tests - Updated for Reorganized Structure

## Test Files Overview

### 1. **test_climate_endpoints.py** (NEW) - Integration Tests
Comprehensive tests for the reorganized API endpoints structure.

**Test Classes:**
- `TestIngestEndpoints` - Tests `/ingest` and `/ingest/store`
- `TestTileEndpoint` - Tests `/tiles/{asset_id}/{z}/{x}/{y}.png`
- `TestPolygonEndpoints` - Tests `/query/polygons/stats` and `/query/polygons/pixels`
- `TestAssetEndpoints` - Tests `/assets`, `/assets/search`, `/assets/by-filename/{filename}`
- `TestEndpointRouting` - Verifies all endpoints are correctly registered

**Run:**
```bash
pytest tests/test_climate_endpoints.py -v
```

---

### 2. **test_polygon_query.py** - CLI Testing Tool (UPDATED)
Interactive command-line tool for testing polygon queries against live endpoints.

**New Features:**
- ✅ Updated to use `/query/polygons/stats` (renamed endpoint)
- ✅ New `--pixels` flag for `/query/polygons/pixels` endpoint
- ✅ Support for multiple assets and polygons
- ✅ CSV and JSON output formats

**Usage Examples:**

```bash
# List available test polygons
python tests/test_polygon_query.py --list-polygons

# Query statistics (single asset + polygon)
python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center

# Query statistics (multiple assets + polygons)
python tests/test_polygon_query.py --asset-ids ID1,ID2 --polygons small_center,kampung_dagat

# Extract pixels as CSV
python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels

# Extract pixels as JSON
python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels --format json
```

**Output:**
- Stats: Prints zonal statistics to console
- Pixels (CSV): Saves to `tests/output_pixels.csv`
- Pixels (JSON): Saves to `tests/output_pixels.json`

---

### 3. **test_climate_indices_todo.py** - Unit Tests (UPDATED)
Tests for the `climate_indices` domain layer (models, service, repository).

**Test Classes:**
- `TestModels` - Pydantic model validation
- `TestGCSBlobStore` - Storage layer (requires credentials)
- `TestAssetRepository` - MongoDB operations (requires connection)
- `TestServiceLayer` - Business logic (`ingest_upload`, `persist_climate_index`)

**Run:**
```bash
pytest tests/test_climate_indices_todo.py -v
```

---

### 4. **test_tile_endpoint.py** - Tile Logic Tests (UNCHANGED)
Unit tests for tile rendering helper functions (mask logic, rescaling, etc.).

**Run:**
```bash
python tests/test_tile_endpoint.py
```

---

### 5. **test_polygons.json** - Test Data (UNCHANGED)
Test polygon geometries for Segama River region.

**Available Polygons:**
- `small_center` - 440 km² test area
- `kampung_dagat` - 44 km² village polygon
- `full_extent` - Entire Segama bounding box
- `edge_southwest` - Edge case for boundary testing
- `edge_northeast` - Edge case for boundary testing

---

## API Endpoint Changes

### Renamed Endpoints
| Old Endpoint | New Endpoint | Status |
|--------------|--------------|--------|
| `/query/polygon` | `/query/polygons/stats` | ✅ Renamed |

### New Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query/polygons/pixels` | POST | Extract raw pixel values (CSV/JSON) |

### Reorganized Files
| Old | New |
|-----|-----|
| `endpoints/tiles.py` (565 lines) | Split into 4 files: |
| | `endpoints/tiles.py` (145 lines) |
| | `endpoints/ingest.py` (134 lines) |
| | `endpoints/polygons.py` (305 lines) |
| | `endpoints/assets.py` (94 lines) |

---

## Running All Tests

### Quick Test (No Infrastructure Required)
```bash
# Unit tests for tile logic
python tests/test_tile_endpoint.py

# Integration tests (most will skip without MongoDB/GCS)
pytest tests/test_climate_endpoints.py -v
```

### Full Integration Tests (Requires MongoDB + GCS)
```bash
# Set up environment
export MONGO_URI="mongodb+srv://..."
export GCS_BUCKET="your-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="./data/gcs_credentials.json"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_climate_endpoints.py::TestPolygonEndpoints -v
```

### Manual Testing with Real Data
```bash
# Start server
python -m app.main

# Test polygon stats
python tests/test_polygon_query.py --asset-id YOUR_ID --polygon small_center

# Test pixel extraction
python tests/test_polygon_query.py --asset-id YOUR_ID --polygon small_center --pixels
```

---

## Test Coverage

### ✅ Covered
- Endpoint routing and registration
- Model validation (Pydantic)
- Tile rendering logic (mask, rescale)
- Polygon query parameter parsing
- Error handling (invalid formats, missing assets)
- Multiple assets/polygons support
- CSV/JSON format switching

### ⚠️ Requires Infrastructure (Skipped by Default)
- GCS blob storage operations
- MongoDB CRUD operations
- Actual tile rendering from COGs
- Full ingestion pipeline
- Real polygon query execution

### 📝 To Be Added
- Mock fixtures for GCS/MongoDB
- Performance benchmarks
- Concurrency tests
- Large polygon handling

---

## Migration Notes

### For Existing Tests
If you have existing scripts using the old endpoint:

**Before:**
```python
response = requests.post(
    f"{base_url}/api/climate-indices/query/polygon",
    data={
        "asset_id": "abc123",
        "polygon_geojson": json.dumps(polygon)
    }
)
```

**After (Stats):**
```python
response = requests.post(
    f"{base_url}/api/climate-indices/query/polygons/stats",
    data={
        "asset_ids": "abc123",  # Now supports multiple, comma-separated
        "polygons_geojson": json.dumps([polygon])  # Now an array
    }
)
```

**After (Pixels):**
```python
response = requests.post(
    f"{base_url}/api/climate-indices/query/polygons/pixels",
    data={
        "asset_ids": "abc123",
        "polygons_geojson": json.dumps([polygon]),
        "format": "csv"  # or "json"
    }
)
```

---

## CI/CD Recommendations

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: pip install -e .[test]
      
      - name: Run unit tests
        run: |
          python tests/test_tile_endpoint.py
          pytest tests/test_climate_indices_todo.py -v --tb=short
      
      - name: Run integration tests (without infrastructure)
        run: pytest tests/test_climate_endpoints.py -v -m "not requires_infra"
```
