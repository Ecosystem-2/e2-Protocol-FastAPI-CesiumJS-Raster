# Getting started

Getting a development instance running locally. This is the one-path version; where a step has
real choices behind it, it links out rather than covering them here.

## Prerequisites

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management
- Git
- A MongoDB instance — Atlas or self-hosted
- A Google Cloud Storage bucket and a service-account key

MongoDB and GCS are not optional. The service has no local-only mode: ingestion writes to
object storage and metadata goes to MongoDB.

## 1. Clone and install

```bash
git clone https://github.com/ORG/REPO.git
cd HOB-FastAPI.Python
```

Install uv if you do not have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then sync the environment:

```bash
uv sync
```

This creates `.venv`, installs everything pinned in `uv.lock`, and uses the Python version in
`.python-version`. Do not edit `uv.lock` by hand; add dependencies with `uv add <package>`.

Activating the virtualenv is optional — `uv run <command>` works without it.

## 2. Set up GCS credentials

You need a service account with object read/write on your bucket, and its JSON key saved to
`data/gcs_credentials.json`:

```bash
mkdir -p data
mv ~/Downloads/your-project-xxxxx.json data/gcs_credentials.json
```

If you do not already have that key, or the bucket does not exist yet,
[GCS credentials](gcs-credentials.md) walks through creating both in the Google Cloud console,
including which IAM role to grant.

Never commit this file. `data/gcs_credentials.json` must stay ignored by git.

## 3. Configure the environment

```bash
cp .env.example .env
```

The settings the service actually reads:

```bash
# MongoDB
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGO_DB=climate_indices                 # optional, this is the default
MONGO_ASSETS_COLLECTION=assets           # optional, this is the default

# Google Cloud Storage
GCS_BUCKET=your-bucket-name
GCS_PREFIX=uploads
GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json

# Demo frontend — served to the browser, so it must be reachable from the browser
DEMO_API_BASE=http://localhost:8080/api/climate-indices
CESIUM_ION_TOKEN=your-cesium-ion-token

# Logging
LOG_LEVEL=INFO
```

Only `MONGO_URI`, `GCS_BUCKET` and `GOOGLE_APPLICATION_CREDENTIALS` have no workable default.

If your MongoDB password contains characters such as `@`, `/` or `:`, URL-encode it:

```bash
python -c "from urllib.parse import quote_plus; print(quote_plus('p@ssw0rd!'))"
```

## 4. Run the server

```bash
uv run python -m app.main
```

Or with reload, which is what you want while editing:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

The server starts on `http://127.0.0.1:8080`.

## 5. Check it works

Open the generated API documentation — if this renders, the app started cleanly:

- Swagger UI: <http://127.0.0.1:8080/docs>
- ReDoc: <http://127.0.0.1:8080/redoc>

Then confirm MongoDB is actually reachable, which the previous step does not prove:

```bash
curl http://127.0.0.1:8080/api/climate-indices/assets
```

An empty list is a success. A 500 means the Mongo connection failed — see
[Troubleshooting](troubleshooting.md#database-connection-issues).

## 6. Walk the demo

`http://127.0.0.1:8080/demo/` is a static CesiumJS frontend that exercises the whole service in
five steps: upload a GeoTIFF, view its tiles, draw polygons, save the selection, export CZML.
It is the fastest way to see what the API does, and useful for reproducing bugs.

The globe needs `CESIUM_ION_TOKEN` set. Without it the API still works, but the demo has no
base imagery.

## Running tests

```bash
uv run pytest tests/test_climate_endpoints.py -v
```

Most integration tests skip without MongoDB and GCS configured. See [Testing](testing.md) for
what is covered, what needs infrastructure, and the polygon-query CLI tool.

## Things that will surprise you

- **`/ingest*` and `/query/polygons/*` take form data, not JSON.** GeoJSON is passed as a
  stringified form field. Sending JSON gets you a `422`. See
  [Architecture](architecture.md#endpoints-take-form-data-not-json).
- **Re-uploading with the same `rasterID` replaces the record.** Omit it and you always get a
  new one.
- **Everything is reprojected to EPSG:4326 on ingest.** The stored raster is not in its
  original projection.
- **The codebase uses British spelling** — `colour`, `colourmap`, `visualisation` — but the
  API is not consistent about it. CZML export takes `colourmapName`; the tile endpoint accepts
  `colormap_name`, `colormapName` or `colourMap`. When in doubt, check the parameter name in
  `/docs` rather than guessing from the spelling convention.

## Where to go next

- [Architecture](architecture.md) — how the layers fit together and why
- [Data model](schema.md) — what the collections and payloads look like
- [Deployment](deployment.md) — running it in Docker
- [Troubleshooting](troubleshooting.md) — when the above does not work
