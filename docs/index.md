# e2 Protocol: FastAPI + CesiumJS (Raster)

A climate-data microservice for the Heart of Borneo project. It ingests GeoTIFF climate-index
rasters, stores them in Google Cloud Storage and MongoDB, and serves them to a CesiumJS
frontend as PNG map tiles, zonal statistics, and CZML 3D-visualisation documents.

## What it does

- **Ingests GeoTIFFs** — validates an upload, reprojects it to EPSG:4326, extracts raster
  metadata and statistics, then stores the raw file and a `.cog.tif` in GCS alongside a
  MongoDB record.
- **Serves map tiles** — renders any ingested raster as PNG tiles at
  `/tiles/{assetID}/{z}/{x}/{y}.png`, with a choice of colourmap.
- **Computes zonal statistics** — clips a raster to a GeoJSON polygon and returns count, min,
  max, mean, median and standard deviation.
- **Persists selections** — named groups of polygons with their computed statistics, organised
  by tag.
- **Exports CZML** — turns a selection into a Cesium document as extruded polygons
  (`polygon`), flat polygons (`polygon2d`), centroid circles (`circle2d`), or 3D bars whose
  height encodes the statistic (`bar`).

## Where to start

| If you want to… | Read |
|---|---|
| Run the service locally | [Getting started](getting-started.md) |
| Understand how it fits together | [Architecture](architecture.md) |
| Know what the API returns | [Data model](schema.md), plus the live OpenAPI docs at `/docs` |
| Deploy it | [Deployment](deployment.md) |
| Set up Google Cloud Storage | [GCS credentials](gcs-credentials.md) |
| Fix something that is broken | [Troubleshooting](troubleshooting.md) |
| Run or extend the test suite | [Testing](testing.md) |

## API reference

This site deliberately contains no hand-written endpoint reference — one would drift from the
code within a release. The service generates its own reference from the running application:

- **Swagger UI** — `/docs`
- **ReDoc** — `/redoc`
- **OpenAPI JSON** — `/openapi.json`

[Architecture](architecture.md) covers the conventions those signatures do not show: the ID
system, the form-data convention, and upsert behaviour.

## Requirements

Python 3.13, a MongoDB instance, and a Google Cloud Storage bucket with service-account
credentials. MongoDB and GCS are external dependencies; there is no local-only mode.

## Licence

Released under the GNU Affero General Public License v3.0. See `LICENSE.md` in the
repository root.
