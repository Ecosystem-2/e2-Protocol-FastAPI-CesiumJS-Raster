GeoTIFF Climate Index Pipeline – Brainstorm
===========================================

Goal
----
- Accept climate index GeoTIFFs (humid-heat-stress, p-pet-ratio, etc.) across multiple time ranges.
- Convert each upload into queryable GeoJSON (per-feature climate indices + start/end timestamps).
- Persist metadata and assets in MongoDB (and object storage) and expose them for CesiumJS visualization and polygon-based queries.

Ingestion + Conversion
----------------------
- Upload API: accept GeoTIFF + form fields (index type, time_range or start/end, units). Validate CRS (target EPSG:4326), nodata, and bounds.
- Convert to Cloud-Optimized GeoTIFF (COG) to enable range requests and pyramids; store original + COG.
- Derive vector footprints and basic stats: bounding box, mask nodata, compute histograms, min/max, and percentiles.
- Generate GeoJSON:
  - For gridded summaries, polygonize masked cells (rasterio.features) but limit resolution; include properties: `index`, `time_start`, `time_end`, `mean`, `std`, `min`, `max`, `source_uri`.
  - For large rasters, prefer tiling + per-polygon sampling on demand instead of dense polygonization.
- Asynchronous jobs (Celery/RQ) for heavy work: COG creation, tiling, stats, GeoJSON extraction, uploads.

Storage Strategy (Mongo + GCS)
------------------------------
- MongoDB collections:
  - `assets`: one doc per upload (index type, time range, CRS, resolution, bbox, COG URL, raw URL, checksum, creation metadata). Uses **upsert-by-filename** strategy to prevent duplicates whilst preserving `_id` and `created_at` on re-uploads.
  - `geojson_layers`: optional precomputed GeoJSON/VectorTiles references with `asset_id`, tiling scheme, and simplification level.
  - `timeseries_cache`: per polygon hash storing smoothed series + params used.
- Google Cloud Storage (GCS) for blob storage via `GCSBlobStore` (simplified from original BlobStore abstraction).
  - Stores both raw GeoTIFF and `.cog.tif` variant (currently duplicated, not true COG conversion - requires `rio-cogeo` integration).
  - Returns `gs://` URIs for use with rio-tiler's COGReader.
- Indexes: `filename` (unique), `index`, `time_start/time_end`, `bbox` (2dsphere), `asset_id`.

CesiumJS Visualization Options
------------------------------
- Direct COG imagery: serve via HTTPS with range requests; use `UrlTemplateImageryProvider` or `SingleTileImageryProvider` for small rasters.
- Tiled imagery: generate XYZ/WMTS from COG (rio-cogeo, titiler) for performant zooming; best balance for large rasters.
- CZML: good for time-dynamic overlays and polygons; can wrap imagery tiles as `ImageMaterial` with `availability` per time slice.
- Recommendation: store COG + expose tiled service; for time slider, switch tile URLs per time slice and expose CZML for temporal availability if needed.

Polygon Query + Smoothing
-------------------------
- User draws polygon → send GeoJSON to backend with target `index` and time window.
- Backend workflow:
  - Fetch relevant assets by bbox/time.
  - Clip raster to polygon (rasterio.mask) and compute zonal stats (mean, median, std, pXX). For multiple timestamps, iterate assets ordered by time.
  - Optional resampling to common resolution before stats.
- Smoothing options for time series:
  - Rolling mean/median (window configurable).
  - LOESS/LOWESS with bandwidth control.
  - Exponential moving average for responsiveness.
  - Gap filling: forward/backward fill for missing dates; flag interpolated points.
- Cache results keyed by polygon hash + smoothing params in `timeseries_cache`.

API Sketch (Implemented)
------------------------
**Ingestion** (`app/api/climate/endpoints/ingest.py`):
- `POST /api/climate-indices/ingest` (FormData): Parse GeoTIFF metadata without persisting.
- `POST /api/climate-indices/ingest/store` (FormData): Upload + persist to GCS + MongoDB with upsert-by-filename.

**Tile Serving** (`app/api/climate/endpoints/tiles.py`):
- `GET /api/climate-indices/tiles/{asset_id}/{z}/{x}/{y}.png?colormap_name=viridis&scale_min=0&scale_max=2`: PNG tiles via rio-tiler with manual rescaling (avoids numpy warnings).

**Polygon Queries** (`app/api/climate/endpoints/polygons.py`):
- `POST /api/climate-indices/query/polygons/stats` (FormData): Zonal statistics (min/max/mean/std/median) for multiple assets/polygons.
- `POST /api/climate-indices/query/polygons/pixels` (FormData): Raw pixel extraction as CSV (lon, lat, asset_id, value) or JSON. Supports `format` parameter (default: csv).

**Asset Discovery** (`app/api/climate/endpoints/assets.py`):
- `GET /api/climate-indices/assets`: List all assets.
- `GET /api/climate-indices/assets/search?index=ppet&time_start=...`: Filter by criteria.
- `GET /api/climate-indices/assets/by-filename/{filename}`: Fetch by filename.

**Note**: All endpoints use **FormData** for multipart requests, not JSON body. Polygon queries support multiple `asset_ids` (comma-separated) and `polygons_geojson` (array of GeoJSON polygons).

Frontend (CesiumJS) - Implemented Demo
---------------------------------------
**Demo**: `app/demo/ppet_tiles.html` - Interactive PPET visualization with polygon queries.

**Features**:
- **Time slice selector**: Switch between 3 time periods (1981-2010, 2041-2070, 2071-2100) with auto-requery of drawn polygons.
- **Tile rendering**: `UrlTemplateImageryProvider` with configurable colourmap (viridis) and scale parameters.
- **Polygon drawing**: Click-based polygon creation with double-click to finish.
- **Zonal statistics**: Query `/query/polygons/stats` across all time periods simultaneously, display formatted JSON results.
- **Pixel export**: "Export Pixel Data (CSV)" button calls `/query/polygons/pixels`, downloads CSV with lon/lat/asset_id/value.
- **API documentation panel**: Toggleable help section showing all 4 demonstrated endpoints with descriptions.
- **Auto-requery**: Automatically queries new time slice when switching tiles whilst polygon remains drawn.

**Technical Details**:
- Uses FormData for all API requests (not JSON).
- Hardcoded asset IDs for 3 PPET time slices.
- Results panel displays multi-asset statistics with time range metadata.
- Cesium v1.124.0 with custom coordinate conversion for GeoJSON polygon creation.

Testing (Implemented)
---------------------
**Integration Tests** (`tests/test_climate_endpoints.py`):
- `TestIngestEndpoints`: Upload validation, metadata extraction, storage persistence.
- `TestTileEndpoint`: PNG tile rendering with colourmap parameters.
- `TestPolygonEndpoints`: Zonal statistics and pixel extraction (CSV/JSON formats).
- `TestAssetEndpoints`: Asset listing, search, and filename lookup.
- `TestEndpointRouting`: Verifies all endpoints properly registered.

**CLI Testing Tools**:
- `tests/test_tile_endpoint.py`: Tile rendering validation.
- `tests/test_polygons.json`: GeoJSON test fixtures for polygon queries.

**Domain Tests** (`tests/test_climate_indices_todo.py`):
- Service layer unit tests (placeholder for future coverage).

**Testing Strategy**: FastAPI TestClient for endpoint integration tests; pytest for fixtures and assertions. Uses `@pytest.mark.integration` for tests requiring external dependencies.

Operational Notes
-----------------
- Enforce CRS to EPSG:4326 during upload; reject if unprojectable.
- Keep provenance: source filenames, processing steps, software versions in `assets`.
- Background workers should stream uploads directly to storage to avoid local disk pressure.
- **Current COG limitation**: `.cog.tif` files are duplicates, not true Cloud Optimised GeoTIFFs (requires `rio-cogeo` integration).

Module Layout (Implemented)
---------------------------
**Domain Layer** (`app/climate_indices/`):
- `models.py`: Pydantic models (`AssetRecord`, `AssetIngestRequest`, `RasterSummary`).
- `service.py`: Business logic orchestration (`ingest_upload()`, `persist_climate_index()`).
- `repository.py`: MongoDB data access (`AssetRepository` with upsert-by-filename).
- `storage.py`: GCS blob storage (`GCSBlobStore` - simplified, no abstraction).

**API Layer** (`app/api/climate/endpoints/`):
- `ingest.py` (134 lines): GeoTIFF upload endpoints with helper functions (`_validate_upload()`, `_initialise_storage()`).
- `tiles.py` (145 lines): PNG tile serving with manual rescaling helpers (`_build_valid_mask()`, `_rescale_array()`).
- `polygons.py` (305 lines): Polygon query endpoints for stats and pixel extraction (`_generate_pixels_csv()`, `_fetch_assets()`).
- `assets.py`: Asset discovery and search endpoints.
- `query.py`: Core raster operations (`zonal_stats_from_cog()`, `extract_pixels_from_cog()`).

**Shared Utilities** (`app/geotif_converter/`):
- `raster_io.py`: `read_geotiff()` (always converts to EPSG:4326), `get_raster_metadata()`.
- Legacy converters: `raster2dataframe.py`, `csv2czml.py`.

**Architecture Pattern**: Domain-Driven Design with clear separation of concerns. API endpoints delegate to domain services, which coordinate repository and storage layers.

Deployment Steps (draft)
------------------------
- Build artifacts: package the FastAPI app; ensure COG tooling (`rasterio`, `rio-cogeo` or equivalents) is in the runtime image.
- Storage wiring: configure env for Mongo connection, object storage bucket/keys (or GridFS fallback), and optional tiler base URL (titiler or internal).
- Worker stack: deploy Celery/RQ workers alongside the API (shared code from `app/geotif_converter` and `app/climate_indices`); ensure a broker (Redis) and result backend are available.
- Static/tiles: if using titiler, deploy it as a sidecar/service; otherwise serve tiles through the FastAPI tiler endpoints backed by COGs in storage.
- Observability: add health checks for Mongo, broker, storage, and tiler; log job failures and processing durations.
- Infra testing: run upload → COG convert → tile fetch → polygon query smoke test in staging before promoting to production.
