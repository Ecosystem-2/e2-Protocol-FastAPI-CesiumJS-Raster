# HOB FastAPI — API Reference

> **Base URL**: `http://localhost:8080/api`  
> **Interactive docs**: `http://localhost:8080/docs` (Swagger UI) | `http://localhost:8080/redoc` (ReDoc)

---

## Climate Indices (`/api/climate-indices`)

The core API for the Heart of Borneo climate visualisation system. Follows a six-step workflow: Ingest → Tiles → Draw → Query → Save → Export.

### Ingest — Upload Climate Data

| Method | Endpoint | Summary |
|--------|----------|---------|
| `POST` | `/ingest` | Ingest and persist a GeoTIFF climate index |

**`POST /ingest`** — Upload a GeoTIFF, validate it, reproject to EPSG:4326, store raw + COG to Google Cloud Storage, and record metadata in MongoDB. If a `rasterID` is provided and already exists, the asset is replaced (upsert).

Form parameters:
- `file` *(required)* — `.tif/.tiff` binary
- `indexType` *(required)* — Climate index name (e.g. `ppet`, `humid-heat-stress`)
- `timeStart` / `timeEnd` *(required)* — ISO datetime range covered by the dataset
- `units` — Measurement units (e.g. `°C`, `mm`, `ratio`)
- `rasterID` — Frontend-generated UUID. Re-uploading with the same value replaces the existing asset. GCS blobs are named by this UUID
- `userID` — Owner user UUID for access control
- `projectID` — Project UUID for grouping assets
- `customGroup` — Custom grouping identifier for organising assets

---

### Tiles — Raster Map Visualisation

| Method | Endpoint | Summary |
|--------|----------|---------|
| `GET` | `/tiles/{id}/{z}/{x}/{y}.png` | Serve a PNG tile for an asset (COG-backed) |

**`GET /tiles/{id}/{z}/{x}/{y}.png`** — Renders a single 256×256 PNG tile from a Cloud Optimized GeoTIFF via rio-tiler. Used by Cesium's `UrlTemplateImageryProvider` for map overlay.

Query parameters:
- `colourmapName` — Matplotlib colourmap name (default: `viridis`). See `/colourmaps` for available options
- `scaleMin` / `scaleMax` — Manual rescale range. Falls back to asset metadata, then tile percentiles

---

### Assets — Browse & Manage

| Method | Endpoint | Summary |
|--------|----------|---------|
| `GET` | `/assets` | List all ingested assets (paginated, filterable) |
| `GET` | `/assets/search?q=...` | Fuzzy search by filename, index type, or units |
| `GET` | `/assets/by-filename/{filename}` | Lookup by original uploaded filename |
| `GET` | `/assets/by-raster-id/{rasterID}` | Lookup by frontend-generated UUID |
| `GET` | `/assets/{id}` | Get full asset details by MongoDB ObjectId |
| `PUT` | `/assets/{id}` | Update asset metadata (indexType, units, userID, projectID) |
| `DELETE` | `/assets/{id}` | Delete asset from MongoDB + GCS (irreversible) |

**Filtering**: `GET /assets` supports `userID` and `projectID` query parameters to scope results by ownership.

**Dual ID support**: Polygon query and selection endpoints accept both MongoDB ObjectId and `rasterID` UUID in the `assetIds` parameter.

---

### Polygon Queries — Zonal Statistics & Pixel Extraction

| Method | Endpoint | Summary |
|--------|----------|---------|
| `POST` | `/query/polygons/stats` | Compute zonal statistics within polygons |
| `POST` | `/query/polygons/pixels` | Extract raw pixel values within polygons |

**`POST /query/polygons/stats`** — Computes count, min, max, mean, std for raster pixels within one or more drawn polygons, across one or more assets. Used by the demo's "Query" step.

**`POST /query/polygons/pixels`** — Extracts individual pixel coordinates and values. Returns CSV (default) or JSON. Useful for downstream analysis or creating point-based visualisations.

Both endpoints accept Form data:
- `assetIds` — Comma-separated MongoDB ObjectIds or rasterID UUIDs
- `polygonsGeojson` — JSON array of GeoJSON Polygon objects as string
- `format` *(pixels only)* — `csv` or `json`

---

### Selections — Saved Polygon Groups

| Method | Endpoint | Summary |
|--------|----------|---------|
| `POST` | `/selections/save` | Save polygon selection with computed statistics |
| `GET` | `/selections` | List all saved selections (paginated, tag-filterable) |
| `GET` | `/selections/by-name/{name}` | Lookup by title (case-insensitive) |
| `GET` | `/selections/by-selection-id/{selectionID}` | Lookup by frontend-generated UUID |
| `GET` | `/selections/{id}` | Get full selection by MongoDB ObjectId |
| `PUT` | `/selections/{id}` | Update selection metadata (title, description, tags, ownership) |
| `DELETE` | `/selections/{id}` | Delete selection permanently |

**`POST /selections/save`** — Persists one or more drawn polygons as a named selection. Automatically computes zonal statistics for all provided assets. Re-saving with the same `selectionID` replaces the existing record.

Form parameters include: `title`, `geometry` (GeoJSON string), `assetIds`, `description`, `tags`, `localeID`, `siteID`, `userID`, `projectID`, `selectionID`.

---

### CZML Export — Cesium Visualisation

| Method | Endpoint | Summary |
|--------|----------|---------|
| `POST` | `/selections/{id}/export-czml` | Generate CZML from a saved selection |
| `GET` | `/czml/{id}` | Retrieve a saved CZML document |
| `GET` | `/czml/by-czml-id/{czmlID}` | Lookup by frontend-generated UUID |
| `GET` | `/selections/{id}/czml` | List all CZML documents for a selection |
| `PUT` | `/czml/{id}` | Update CZML document metadata |
| `DELETE` | `/czml/{id}` | Delete a CZML document |
| `GET` | `/colourmaps` | List available Matplotlib colourmaps |
| `GET` | `/colourmaps/categories` | Get colourmaps organised by category |

**`POST /selections/{id}/export-czml`** — Generates a CZML document for Cesium from a saved selection's statistics. Supports four visualisation types:
- **`polygon`** — Extruded coloured polygons. Height and fill colour are based on the selected statistic value.
- **`polygon2d`** — Flat saved polygon geometry. Fill colour is based on the selected statistic value; no extrusion is generated.
- **`circle2d`** — Flat circles centred on each saved polygon centroid. Circle radius is user-defined; fill colour is based on the selected statistic value.
- **`bar`** — 3D cylinders positioned at polygon centroids. Height is proportional to the selected statistic value.

Configurable options:

| Field | Type | Default | Applies to | Description |
|-------|------|---------|------------|-------------|
| `indexType` | string | required | all | Climate index to export, e.g. `ppet` or `humid-heat-stress`. |
| `visualisationType` | enum | `polygon` | all | One of `polygon`, `polygon2d`, `circle2d`, or `bar`. |
| `colourmapName` | string | `viridis` | all | Matplotlib colourmap name. |
| `scaleMin` / `scaleMax` | number | auto | all | Optional fixed colour scale bounds. |
| `valueField` | enum | `mean` | all | Statistic used for colour/height: `mean`, `min`, `max`, `median`, or `std`. |
| `interpolationMode` | enum | `step` | all temporal exports | `step` creates one entity per period; `interpolation` samples values at period midpoints and linearly interpolates between them. |
| `polygonHeightMultiplier` | number | `1000.0` | `polygon` | Multiplier for extruded polygon heights in metres. |
| `polygonFillOpacity` | number | `0.7` | `polygon`, `polygon2d`, `circle2d` | Fill opacity from `0` to `1`. |
| `polygonOutline` | boolean | `true` | `polygon`, `polygon2d`, `circle2d` | Show entity outline. |
| `circleRadius` | number | `1000.0` | `circle2d` | Circle radius in metres. |
| `barHeightMultiplier` | number | `10000.0` | `bar` | Multiplier for cylinder heights in metres. |
| `barRadiusMultiplier` | number | `10.0` | `bar` | Radius multiplier based on source pixel count. |
| `barMinimumRadius` | number | `500.0` | `bar` | Minimum cylinder radius in metres. |
| `showLabels` | boolean | `true` | all entity modes | Display value labels. |
| `saveToDb` | boolean | `true` | all | Save generated CZML to MongoDB. |
| `czmlID` | UUID | optional | all | Frontend-generated cross-system CZML UUID. |
| `userID` / `projectID` | string | optional | all | Ownership metadata. |

Example 2D circle export:

```bash
curl -X POST "http://localhost:8080/api/climate-indices/selections/{selection_id}/export-czml" \
  -F "indexType=ppet" \
  -F "visualisationType=circle2d" \
  -F "circleRadius=2500" \
  -F "colourmapName=viridis" \
  -F "valueField=mean" \
  -F "interpolationMode=step"
```

---

### Configuration

| Method | Endpoint | Summary |
|--------|----------|---------|
| `GET` | `/config` | Get demo frontend configuration |

Returns `api_base` URL and `cesium_ion_token` from environment variables. Used by the demo HTML pages to auto-configure API calls.

---

## GeoTIFF Converter (`/api/geotif`)

Standalone utility endpoints for generic GeoTIFF processing. **Not part of the main climate workflow** — these are independent tools for raster inspection and tabular export.

| Method | Endpoint | Summary |
|--------|----------|---------|
| `POST` | `/geotif/metadata` | Extract metadata from GeoTIFF files |
| `POST` | `/geotif/csv` | Convert GeoTIFF raster data to CSV |

**`POST /geotif/metadata`** — Upload one or more GeoTIFF files and receive their raster metadata (CRS, bounds, resolution, band info, nodata values). Files are reprojected to the target CRS before extraction. Useful for inspecting raster properties before ingestion.

**`POST /geotif/csv`** — Upload one or more GeoTIFFs and receive a merged CSV with columns: `x` (longitude), `y` (latitude), and one value column per file. Useful for exporting pixel data for charting, tabular analysis, or legacy CZML generation pipelines.

Query parameters:
- `target_crs` — Target coordinate system (default: `EPSG:4326`)
- `drop_na` *(csv only)* — Whether to exclude NoData pixels (default: `true`)

---

## ID System

The API uses a dual-ID approach:

| ID Type | Format | Purpose | Example |
|---------|--------|---------|---------|
| MongoDB `_id` | 24-char hex ObjectId | Internal primary key, used in URL paths as `{id}` | `6632a1f4e8b3c9d1a0f5e2b7` |
| `rasterID` | UUID v4 | Frontend-generated UUID for assets | `550e8400-e29b-41d4-a716-446655440000` |
| `selectionID` | UUID v4 | Frontend-generated UUID for selections | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `czmlID` | UUID v4 | Frontend-generated UUID for CZML documents | `b2c3d4e5-f6a7-8901-bcde-f12345678901` |

**Lookup endpoints**: Each entity has a `/by-{type}-id/{uuid}` endpoint for UUID-based retrieval.

**Upsert behaviour**: Re-uploading with the same UUID replaces the existing record while preserving `_id` and `createdAt`.

---

## Ownership Fields

All entities accept optional ownership fields:

| Field | Description |
|-------|-------------|
| `userID` | Owner user UUID — frontend responsibility to manage user records |
| `projectID` | Project UUID — groups assets/selections/CZML under a project |

**Filtering**: `GET /assets` supports `?userID=...&projectID=...` query parameters.

---

## Common Patterns

### Form Data (not JSON)
All `POST` and `PUT` endpoints use `multipart/form-data`, not `application/json`. Frontend must use `FormData`:

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('indexType', 'ppet');
// ...
const response = await fetch('/api/climate-indices/ingest', {
  method: 'POST',
  body: formData  // No Content-Type header — browser sets boundary automatically
});
```

### Error Responses
Standard HTTP error codes with JSON detail:
```json
{
  "detail": "Asset with rasterID '...' not found."
}
```

| Code | Meaning |
|------|---------|
| `400` | Bad request — invalid input, missing required fields |
| `404` | Not found — asset/selection/CZML doesn't exist |
| `415` | Unsupported media type — wrong file format |
| `500` | Server error — GCS/MongoDB configuration issues |
