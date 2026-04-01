# HOB FastAPI - Copilot Instructions

## Architecture Overview

**Climate Raster Tile Server**: FastAPI service that ingests GeoTIFF climate indices, stores them in Google Cloud Storage (GCS) + MongoDB, and serves them as PNG tiles for Cesium visualizations. This is a Heart of Borneo climatology visualization microservice.

### Core Components

1. **`app/climate_indices/`** - Domain layer for climate asset management
   - `service.py`: Orchestrates ingestion (`ingest_upload`, `persist_climate_index`)
   - `repository.py`: MongoDB data access (`AssetRepository` with upsert-by-raster_id)
   - `storage.py`: GCS blob storage (`GCSBlobStore`)
   - `models.py`: Pydantic models (`AssetRecord`, `AssetIngestRequest`, `RasterSummary`)

2. **`app/api/climate/endpoints.py`** - REST API endpoints
   - `/ingest`: Upload + persist to GCS + MongoDB (upserts by raster_id)
   - `/tiles/{asset_id}/{z}/{x}/{y}.png`: Serve PNG tiles via rio-tiler
   - `/query/polygon`: Compute zonal statistics (Form data, not JSON)
   - `/assets`, `/assets/search`, `/assets/by-filename/{filename}`, `/assets/by-raster-id/{raster_id}`: Asset discovery

3. **`app/geotif_converter/`** - Shared raster utilities
   - `raster_io.py`: `read_geotiff()`, `get_raster_metadata()` (always converts to EPSG:4326)
   - `raster2dataframe.py`, `csv2czml.py`: Legacy data transformation pipelines

4. **`app/demo/*.html`** - Interactive Cesium demos
   - `ppet_tiles.html`: Draw polygons, auto-query on tile switch, compare time periods

### Data Flow

```
Upload → validate → read_geotiff (CRS→4326) → extract metadata → 
  GCSBlobStore.save_bytes (raw + .cog.tif) → 
  AssetRepository.upsert_by_filename → MongoDB asset record
```

**Tile Serving**: `asset_id → MongoDB lookup → COGReader(gs://uri) → rio-tiler tile → manual rescaling (avoids numpy warnings) → uint8 alpha mask → ImageData → PNG`

**Polygon Query**: Form data `{asset_id, polygon_geojson}` → COG URI → rasterio.mask → numpy stats → JSON response

## Critical Patterns

### 1. British Spelling Convention
Use British English throughout: `colour`/`colourmap`, `initialise`, `optimise`, `summarise`. Example:
```python
def _initialise_storage() -> Tuple[GCSBlobStore, AssetRepository]:
    """Initialise GCS storage and asset repository."""
```

### 2. Tile Rendering (Manual Rescaling)
**DO NOT** use `ImageData.rescale()` or `render(rescale=...)` - causes numpy warnings. Instead:
```python
# Manually rescale valid pixels to 0-255 uint8
arr_rescaled = _rescale_array(arr, valid_mask, vmin, vmax)
alpha_mask = valid_mask.astype("uint8") * 255  # 0=transparent, 255=opaque
tile = ImageData(array=np.expand_dims(arr_rescaled, axis=0), alpha_mask=alpha_mask, ...)
```

### 3. Asset Upsert Strategy
Re-uploading with the same **raster_id** replaces the existing MongoDB record while preserving `_id` and `created_at`:
```python
asset_id, was_replaced = repo.upsert_asset(record)
```
If no raster_id is provided, a new record is always created. This allows the frontend to control when replacements occur.

**UUID Field Naming**:
- Assets: `raster_id` — frontend-generated UUID for rasters
- Selections: `selection_id` — frontend-generated UUID for polygon selections
- CZML: `czml_id` — frontend-generated UUID for CZML documents

### 4. Form Data vs JSON
- `/ingest*` endpoints: `Form(...)` parameters (multipart file uploads)
- `/query/polygon`: `Form(...)` with `polygon_geojson: str` (stringify GeoJSON)
- Frontend must use `FormData`, not `Content-Type: application/json`

### 5. Helper Function Extraction
Endpoints refactored to use private helpers prefixed with `_`:
```python
def _validate_upload(file, payload) -> None
def _initialise_storage() -> Tuple[GCSBlobStore, AssetRepository]
def _build_valid_mask(arr, tile_mask, nodata) -> np.ndarray
def _determine_rescale_range(...) -> Tuple[float, float]
def _rescale_array(arr, valid_mask, vmin, vmax) -> np.ndarray
```

### 6. COG Limitation
Current implementation **duplicates** raw TIFF to `.cog.tif` without actual Cloud Optimized GeoTIFF conversion. True COG creation would require `rio-cogeo` integration (not yet implemented).

## Development Workflow

### Local Setup
```bash
# Python 3.13+ required
uv sync  # or: pip install -e .
cp .env.example .env
# Edit .env: MONGO_URI, GCS_BUCKET, GCS_PREFIX, GOOGLE_APPLICATION_CREDENTIALS

# Run server
python -m app.main
# or: uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

### Environment Variables
```bash
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=climate_indices  # optional, default used
MONGO_ASSETS_COLLECTION=assets  # optional
GCS_BUCKET=climate-tiles-cluster
GCS_PREFIX=uploads
GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json
LOG_LEVEL=INFO  # optional
```

### Google Cloud Storage Credentials Setup

**Generating Service Account JSON Credentials:**

1. **Access Google Cloud Console**
   - Navigate to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project (or create a new one)

2. **Create Service Account**
   - Go to **IAM & Admin** → **Service Accounts**
   - Click **Create Service Account**
   - Enter name (e.g., `climate-tiles-service`)
   - Click **Create and Continue**

3. **Grant Permissions**
   - Add role: **Storage Admin** (for full bucket access)
   - Or **Storage Object Admin** (for object-only access)
   - Click **Continue** → **Done**

4. **Generate JSON Key**
   - Click on the newly created service account
   - Go to **Keys** tab
   - Click **Add Key** → **Create New Key**
   - Select **JSON** format
   - Click **Create** (file downloads automatically)

5. **Configure Project**
   ```bash
   # Create data directory if it doesn't exist
   mkdir -p data
   
   # Move downloaded JSON to project
   mv ~/Downloads/your-project-xxxxx.json ./data/gcs_credentials.json
   
   # Update .env file
   echo "GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json" >> .env
   ```

6. **Create GCS Bucket** (if not exists)
   ```bash
   # Using gcloud CLI
   gcloud storage buckets create gs://climate-tiles-cluster --location=us-central1
   
   # Or via Console: Storage → Buckets → Create Bucket
   ```

**Security Notes:**
- Never commit `gcs_credentials.json` to version control (already in `.gitignore`)
- Service account should have minimum required permissions
- Rotate keys periodically for enhanced security

### Testing Polygon Queries
```bash
python tests/test_polygon_query.py  # CLI tool with test polygons
# Or use tests/test_polygons.json with httpx/curl
```

### Demo Tiles
Open `http://localhost:8080/demo/ppet_tiles.html` (served via static file mount if configured, otherwise open directly from filesystem pointing to `http://127.0.0.1:8080/api/climate-indices`).

## Common Pitfalls

1. **ImageData is immutable** - Create new instances with updated masks, don't try to set `.mask` property
2. **rio-tiler colormap names** - 211 available, use `cmap.get(name)` to validate
3. **Polygon query expects FormData** - Not JSON body, despite being POST
4. **MongoDB ObjectId handling** - Always convert `str(doc["_id"])` before Pydantic validation
5. **GCS credentials** - Service account JSON must exist at path specified in env var

## Key Files Reference

- `app/api/climate/endpoints.py` - All climate API routes (386 lines, heavily commented)
- `app/climate_indices/repository.py` - MongoDB operations with upsert logic
- `app/api/climate/query.py` - Zonal statistics using rasterio.mask
- `app/demo/ppet_tiles.html` - Interactive polygon drawing + auto-requery on tile switch
- `docs/geotif-pipeline-brainstorm.md` - Original architecture decisions and rationale

## Cesium Integration

Frontend expects tile URLs like:
```javascript
const url = `${API_BASE}/tiles/${assetId}/{z}/{x}/{y}.png?colormap_name=viridis&scale_min=0&scale_max=2`;
new Cesium.UrlTemplateImageryProvider({ url, maximumLevel: 14, rectangle: bounds });
```

Polygon queries return:
```json
{
  "asset_id": "...",
  "index_type": "ppet",
  "units": "ratio",
  "stats": {"count": 536, "min": 0.0, "max": 1.0, "mean": 0.59, "std": 0.49},
  "metadata": {"filename": "...", "time_range": {...}}
}
```
