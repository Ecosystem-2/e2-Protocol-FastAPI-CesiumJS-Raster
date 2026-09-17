# Deployment

Running the service with Docker, locally or on a public host.

## Prerequisites

- Docker and Docker Compose 20.10 or newer
- A MongoDB instance ([Atlas free tier](https://www.mongodb.com/cloud/atlas) is sufficient)
- A GCS service-account key at `data/gcs_credentials.json` — see
  [GCS credentials](gcs-credentials.md)

## Quick start

```bash
# 1. Confirm the credentials file is in place
ls -la data/gcs_credentials.json

# 2. Configure the environment
cp .env.example .env
$EDITOR .env

# 3. Build and start
docker compose up -d

# 4. Watch it come up
docker compose logs -f
```

The minimum you must set in `.env`:

```bash
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
GCS_BUCKET=your-bucket-name
DEMO_API_BASE=http://localhost:8080/api/climate-indices
CESIUM_ION_TOKEN=your-cesium-ion-token
```

Once running:

- API documentation — <http://localhost:8080/docs>
- Demo workflow — <http://localhost:8080/demo/>

Stop with `docker compose down`.

## The image

A multi-stage build on `python:3.13-slim`. The builder stage installs GDAL and the Python
dependencies with uv; the runtime stage copies only what is needed. Roughly 400–500 MB, mostly
GDAL.

It runs as a **non-root user**, and the GCS key is expected as a **read-only volume mount**,
never baked into the image:

```bash
docker build -t hob-fastapi:latest .

docker run -d \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data/gcs_credentials.json:/app/data/gcs_credentials.json:ro \
  hob-fastapi:latest
```

`GOOGLE_APPLICATION_CREDENTIALS` is adjusted to the container path automatically, so the same
`.env` works locally and in Docker.

## Deploying to a public host

### `DEMO_API_BASE` must be the public URL

This is the step that catches people. `DEMO_API_BASE` is fetched by JavaScript running in the
**user's browser**, not by the container. If it says `localhost`, the browser resolves that to
the user's own machine and the demo silently fails.

| Component | Runs where | URL to use |
|---|---|---|
| Container healthcheck | Inside the container | `localhost:8080` |
| Demo frontend | The user's browser | The public URL |

So on a public host:

```bash
DEMO_API_BASE=https://climate.your-domain.com/api/climate-indices
CESIUM_ION_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Restart and verify from a machine that is not the server:

```bash
docker compose down && docker compose up -d
curl https://climate.your-domain.com/api/climate-indices/config
```

Leave the healthcheck URLs in `Dockerfile` and `docker-compose.yml` as `localhost:8080` — they
run inside the container.

### Open the port

```bash
# ufw
sudo ufw allow 8080/tcp

# firewalld
sudo firewall-cmd --permanent --add-port=8080/tcp && sudo firewall-cmd --reload
```

### Terminate TLS with a reverse proxy

```nginx
server {
    listen 443 ssl;
    server_name climate.your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

The bundled `docker-compose.yml` assumes Traefik for routing and certificates. Any reverse
proxy works, or you can expose the port directly — though see the warning below before doing
that.

## Before you expose an instance publicly

Two things are wide open by default and are your responsibility to close.

**There is no authentication.** No API keys, no sessions, no authorisation checks. Anyone who
can reach the service can upload rasters, consume your GCS quota and delete stored selections.
Put authentication in front of it — reverse-proxy auth, an API gateway, or a private network.

**CORS allows all origins.** `app/core/middleware.py` sets `allow_origins=["*"]`, which is
convenient in development and wrong in production. Restrict it to your frontend's origin.

Beyond those: uploads are validated for content type and size, MongoDB connections use TLS via
`certifi`, and the container runs as a non-root user. Those are handled.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `MONGO_URI` | Yes | MongoDB connection string |
| `MONGO_DB` | No | Database name, defaults to `climate_indices` |
| `MONGO_ASSETS_COLLECTION` | No | Defaults to `assets` |
| `GCS_BUCKET` | Yes | Bucket for rasters |
| `GCS_PREFIX` | No | Key prefix within the bucket |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes | Path to the service-account key |
| `DEMO_API_BASE` | For remote hosts | Public API URL, used by the browser |
| `CESIUM_ION_TOKEN` | For the demo globe | Cesium Ion access token |
| `LOG_LEVEL` | No | Defaults to `INFO` |
| `GDAL_DISABLE_READDIR_ON_OPEN` | Recommended | Set to `EMPTY_DIR`; see below |
| `VSI_CACHE` | Recommended | Set to `FALSE`; see below |

### GDAL tile-visibility settings

If freshly uploaded rasters return "file not found" from the tile endpoint, GDAL is caching a
negative lookup. Set these in the container environment:

```yaml
environment:
  GDAL_DISABLE_READDIR_ON_OPEN: "EMPTY_DIR"
  VSI_CACHE: "FALSE"
```

Do **not** use `CPL_VSIL_CURL_CACHE_SIZE=0` — GDAL 3.10.x rejects that value and silently
falls back to its minimum cache size, so it does not do what it appears to.
[Troubleshooting](troubleshooting.md#newly-uploaded-files-return-file-not-found-when-serving-tiles)
covers the symptom in full.

## Branches and images

| Branch | Purpose | Image build |
|---|---|---|
| `development` | Active development | Manual |
| `testing` | UAT and staging | Automatic on push |
| `deployment` | Production | Requires a release tag |

Feature work branches from `development`. Anything likely to be unstable should get its own
branch and merge back when it settles. The workflows are in `.github/workflows/`.

## Operating it

```bash
docker compose ps                              # status
docker compose logs -f                         # follow logs
docker compose exec api bash                   # shell in the container
docker compose up -d --build                   # rebuild and restart
docker compose build --no-cache                # rebuild ignoring cache
docker compose down                            # stop
```

Raise the log level while diagnosing:

```bash
LOG_LEVEL=DEBUG docker compose up
```

## When the container will not start

Check `docker compose logs` first. The three common causes:

**`FileNotFoundError: data/gcs_credentials.json`** — the key is missing or the volume mount
path is wrong. See [GCS credentials](gcs-credentials.md).

**`ServerSelectionTimeoutError`** — MongoDB is unreachable. Verify `MONGO_URI`, and check the
IP allowlist under Network Access in Atlas. The server's public IP must be allowed, not your
laptop's.

**`port 8080 is already allocated`** — remap in `docker-compose.yml`:

```yaml
ports:
  - "8081:8080"
```

To test each dependency from inside the container:

```bash
docker compose exec api python -c "from google.cloud import storage; storage.Client()"
docker compose exec api ls -la /app/data/
```

Anything not covered here is in [Troubleshooting](troubleshooting.md).
