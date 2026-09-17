# Testing

## The shape of the suite

The service has two external dependencies it cannot fake — MongoDB and Google Cloud Storage —
and that fact drives the whole test strategy. Tests fall into three tiers:

| Tier | Needs infrastructure | Runs in CI |
|---|---|---|
| Pure logic — tile rescaling, mask construction, model validation | No | Yes |
| Routing and contract — endpoints registered, form aliases accepted, error codes | No | Yes |
| Round trip — real ingest, real tile render, real polygon query | MongoDB + GCS | No |

The first two tiers are the ones worth protecting. They run anywhere, catch the regressions
that actually happen (a renamed form alias, a route that stopped being mounted, a rescale that
overflows), and they are fast.

The third tier skips itself when credentials are absent rather than failing. That is deliberate
— a contributor without a GCS bucket should be able to clone, run `pytest`, and get a green
result that means something.

## Running them

```bash
uv sync
uv run pytest tests/ -v
```

Narrow to a file or a class:

```bash
uv run pytest tests/test_climate_endpoints.py -v
uv run pytest tests/test_climate_endpoints.py::TestTileEndpoint -v
```

With infrastructure, so the third tier participates:

```bash
export MONGO_URI="mongodb+srv://…"
export GCS_BUCKET="your-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="./data/gcs_credentials.json"
uv run pytest tests/ -v
```

Watch the skip count. A run where everything skipped is not a passing run, and it is the
easiest way to fool yourself into thinking a change is safe.

## What is covered

**Covered.** Endpoint routing and registration, Pydantic model validation, tile rendering logic
(mask handling, manual rescale), form-alias acceptance on ingest, polygon query parameter
parsing, error handling for invalid formats and missing assets, multi-asset and multi-polygon
requests, CSV and JSON output switching.

**Skipped without infrastructure.** GCS blob operations, MongoDB CRUD, tile rendering from real
COGs, the full ingestion pipeline, real polygon queries.

**Not covered at all.** These are the known gaps, in rough priority order:

- No mock fixtures for GCS or MongoDB — this is what keeps the third tier out of CI, and
  closing it would move most of the round-trip coverage into the runnable tiers
- No concurrency tests, despite upserts being the core write pattern
- No large-polygon or large-raster cases, where the memory profile is least understood
- No performance baselines for tile rendering

## The files

| File | Purpose |
|---|---|
| `test_climate_endpoints.py` | Integration tests across ingest, tiles, assets, polygons, and route registration |
| `test_climate_indices_todo.py` | Domain-layer unit tests — models, storage, repositories, service |
| `test_tile_endpoint.py` | Tile helper functions in isolation: mask logic, rescaling |
| `test_ingest_form_aliases.py` | That ingest accepts its camelCase form aliases |
| `test_polygon_query.py` | CLI tool, not a pytest module — see below |
| `test_polygons.json` | Shared polygon fixtures for the Segama River region |

`test_polygons.json` provides `small_center` (440 km²), `kampung_dagat` (44 km²),
`full_extent` (the whole Segama bounding box), and `edge_southwest` / `edge_northeast` for
boundary behaviour.

## The polygon query CLI

`test_polygon_query.py` is an interactive tool for hitting a **running server**, not a test
module. It is the fastest way to check a real raster behaves.

```bash
# What fixtures are available
uv run python tests/test_polygon_query.py --list-polygons

# Zonal statistics for one asset and one polygon
uv run python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center

# Several of each
uv run python tests/test_polygon_query.py --asset-ids ID1,ID2 --polygons small_center,kampung_dagat

# Raw pixel extraction
uv run python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels
uv run python tests/test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels --format json
```

Statistics print to the console; pixel extraction writes `tests/output_pixels.csv` or
`tests/output_pixels.json`.

## Writing new tests

**Put it in the lowest tier that can hold it.** If a bug can be reproduced against a numpy
array, do not write an integration test for it.

**Skip, do not fail, on missing infrastructure.** Use `pytest.mark.skipif` at module level, or
`pytest.skip()` inside the test, matching what `test_climate_endpoints.py` already does.

**Use `TestClient` rather than a live server.** Integration tests construct
`TestClient(app)` — no server process, no port conflicts.

**Send form data.** Ingest and polygon endpoints take `multipart/form-data` with camelCase
aliases (`assetIds`, `polygonsGeojson`, `indexType`). A test that posts JSON is testing the
`422` path whether it means to or not.

## Known problems with the suite

Two things a new contributor should know before trusting it.

**There is no `conftest.py` and no custom markers.** Any CI configuration that filters with
`-m "not requires_infra"` will not work — that marker does not exist. Skipping is decided
inside each module. Adding a real marker set is worthwhile and has not been done.

**`test_locale_site_structure.py` may be dead.** It posts to live endpoints for `localeData`
and `siteData` structures. Only `localeID` and `siteID` on `PolygonSelectionRecord` still
correspond to anything in `app/`. It also requires a server already running at
`127.0.0.1:8080`, so it does not behave like the rest of the suite. Treat its result as
unreliable until someone confirms which way it is wrong.
