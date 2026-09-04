# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Heart of Borneo climatology microservice. A FastAPI server that ingests GeoTIFF climate-index rasters, stores them in Google Cloud Storage (GCS) + MongoDB, and serves them to a CesiumJS frontend as PNG map tiles, zonal statistics, and CZML 3D-visualisation documents.

## Commands

Dependency management is `uv` (Python 3.13, pinned in `.python-version` / `uv.lock`). Never edit `uv.lock` by hand.

```bash
uv sync                                                  # install/refresh venv from pyproject.toml + uv.lock
uv add <package>                                         # add a dependency (don't hand-edit pyproject)
uv run python -m app.main                                # run server (127.0.0.1:8080, reload on)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

uv run pytest tests/test_climate_endpoints.py -v         # integration tests
uv run pytest tests/test_climate_endpoints.py::TestTileEndpoint -v   # single test class
uv run python tests/test_polygon_query.py --list-polygons            # CLI tool to hit live polygon endpoints
```

Server requires a populated `.env` (copy `.env.example`) plus a GCS service-account JSON at the path in `GOOGLE_APPLICATION_CREDENTIALS` (default `./data/gcs_credentials.json`). MongoDB and GCS are external; there is no local-only mode.

Docs: `docs/dev_instruction.md` (full setup), `docs/setup-gcs-credentials.md`, `docs/troubleshooting.md`, `docs/API.md`.

## Architecture

Three layers, wired top-down in `app/main.py` → `app/api/router.py`:

- **`app/api/`** — HTTP layer. `router.py` mounts everything under `/api`. The climate API lives under `/api/climate-indices` and is assembled in `app/api/climate/endpoints/__init__.py`, which composes one router file per concern: `ingest`, `tiles`, `assets`, `polygons`, `selections`, `czml`, `config`. `app/api/geotif/` is a **standalone** generic-GeoTIFF utility, not part of the climate workflow.
- **`app/climate_indices/`** — domain layer. Services (`asset_service.py`: `ingest_upload`, `persist_climate_index`), repositories (`asset_repository.py`, `selections_repository.py`, `czml_repository.py` — MongoDB access), storage (`blob_storage.py`: `GCSBlobStore`), Pydantic models (`models.py`), and CZML generation (`czml_generate.py` orchestrates `czml_bar.py` / `czml_polygon.py` / `czml_circle.py`). Public API is re-exported from `__init__.py`.
- **`app/geotif_converter/`** — shared raster helpers (`raster_io.py` etc.). Always reprojects to EPSG:4326.

`app/core/` holds logging, middleware, lifespan. `app/db/mongo.py` is the Mongo client. `app/demo/` is a static CesiumJS frontend mounted at `/demo` (a 5-step workflow: upload → tiles → draw → save → export).

### End-to-end data flow

```
Upload GeoTIFF → validate → reproject to EPSG:4326 → extract metadata
  → GCSBlobStore stores raw + .cog.tif → AssetRepository upserts MongoDB record
Tile request → asset lookup → rio-tiler COGReader(gs://…) → manual rescale → PNG
Polygon query → COG → rasterio.mask → numpy stats → JSON
Selection (named polygons + stats) → persisted → exported as CZML for Cesium
```

## Project-specific conventions

- **British spelling everywhere** — code, comments, docstrings, UI strings: `colour`, `colourmap`, `initialise`, `optimise`, `summarise`.
- **Form data, not JSON** — `/ingest*` and `/query/polygons/*` take `Form(...)` params (file uploads + stringified GeoJSON). Frontend must send `FormData`.
- **Frontend-generated UUIDs drive upserts** — `raster_id` (assets), `selection_id` (selections), `czml_id` (CZML). Re-uploading with the same `raster_id` replaces the record while preserving `_id`/`created_at`; omitting it always creates a new record.
- **Tile rescaling is manual** — do **not** use `ImageData.rescale()` / `render(rescale=...)` (emits numpy warnings). Rescale valid pixels to 0–255 uint8 by hand and build a separate uint8 alpha mask. `ImageData` is immutable — construct new instances, never mutate masks.
- **MongoDB ObjectIds** — convert `str(doc["_id"])` before Pydantic validation.
- The `.cog.tif` is currently a copy of the raw TIFF, **not** a true Cloud-Optimized GeoTIFF (no `rio-cogeo` conversion yet).

### Style (from `.cursor/rules/`)
Keep modules ≤300 lines (prefer ≤200); decompose with small functions and private `_`-prefixed helpers. Type hints + concise docstrings explaining "why". Prefer functional/procedural style; reach for OOP only for stateful/reusable components. Don't over-engineer.

## Git workflow

Branch from `development` (the working branch). `testing` → UAT containers; `deployment`/releases → production containers via the workflows in `.github/workflows/`. Commit/push only when asked.
