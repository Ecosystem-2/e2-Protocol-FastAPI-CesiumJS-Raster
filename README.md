<p align="center"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Full_Logo/e2_full_logo_navy.svg" /></p>

# e2 Protocol: FastAPI + CesiumJS (Raster)

Climate-data microservice for the Heart of Borneo project. It ingests GeoTIFF climate-index
rasters, stores them in Google Cloud Storage and MongoDB, and serves them to a CesiumJS
frontend as PNG map tiles, zonal statistics, and CZML 3D-visualisation documents.

This is the development microservice. Branch from `development`; see
[Contributing](#contributing) before opening a pull request.

## Quick start

You need Python 3.13, [uv](https://docs.astral.sh/uv/), a MongoDB instance, and a GCS bucket
with a service-account key. MongoDB and GCS are not optional: ingestion writes to object
storage and metadata goes to MongoDB, so there is no local-only mode.

```bash
uv sync                          # create .venv from uv.lock
cp .env.example .env             # then fill in MONGO_URI, GCS_BUCKET, CESIUM_ION_TOKEN
uv run python -m app.main
```

That serves on `http://localhost:8080`. Interactive API reference at `/docs`, the demo
workflow at `/demo/`.

With Docker instead:

```bash
docker compose up -d
```

[Getting started](docs/getting-started.md) covers the same ground properly, including the
credentials file and what to do when a step fails.

## Documentation

The full docs are a MkDocs site built from `docs/`. To read them locally at
`http://localhost:8000`:

```bash
uv run --no-project --with-requirements docs/requirements.txt mkdocs serve
```

The docs toolchain is pinned in `docs/requirements.txt` rather than `pyproject.toml`, so
building the site does not drag in GDAL and the rest of the geospatial stack.

| If you want to… | Read |
|---|---|
| Run it locally | [Getting started](docs/getting-started.md) |
| Understand how it fits together | [Architecture](docs/architecture.md) |
| Know what the API returns | [Data model](docs/schema.md), plus `/docs` on a running instance |
| Deploy it, or publish an image | [Deployment](docs/deployment.md) |
| Set up Google Cloud Storage | [GCS credentials](docs/gcs-credentials.md) |
| Fix something broken | [Troubleshooting](docs/troubleshooting.md) |
| Run or extend the tests | [Testing](docs/testing.md) |

There is no hand-written endpoint reference. The service generates its own from the running
application at `/docs`, `/redoc` and `/openapi.json`, which is the only version that cannot
drift from the code.

## Branches

| Branch | Purpose | Image build |
|---|---|---|
| `development` | Active development, expect it to change under you | Manual |
| `testing` | Stable enough for UAT | Automatic on push |
| `deployment` | Production | Requires a published release |

Anything very unstable or experimental is better off on its own branch, merged back into
`development` once it settles. Direct commits to `testing` and `deployment` are blocked, so
both are reached by pull request.

## Contributing

Pull requests are welcome. Contributions are accepted under the same licence as the project,
AGPL-3.0-or-later, so there is no separate contributor agreement to sign: opening a pull
request offers your work under that licence. If you are not the copyright holder of what you
are contributing, say so in the pull request.

Dependencies are managed with `uv`, so use `uv add` rather than editing
`pyproject.toml`, and never hand-edit `uv.lock`. Keep modules under 300 lines.
[Architecture](docs/architecture.md) explains the conventions the code does not make obvious,
such as the frontend-generated UUIDs that drive upserts.

Contributors are recorded in [AUTHORS.md](AUTHORS.md).

## Licence

Copyright (c) the respective contributors, as shown by the AUTHORS file.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Because it is AGPL, a deployment that users reach over a network owes them the source of what
is actually running. The service answers that itself at `/source`, driven by `SOURCE_URL` and
`SOURCE_REVISION`; see the notes in `.env.example`.
