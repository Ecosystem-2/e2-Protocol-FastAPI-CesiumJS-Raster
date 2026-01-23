# Docker Deployment Guide

Simple guide for running the HOB FastAPI Climate Tile Server using Docker.

## Prerequisites

- **Docker & Docker Compose**: 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **MongoDB Atlas**: Cloud-hosted MongoDB ([Get free cluster](https://www.mongodb.com/cloud/atlas))
- **GCS Credentials**: Service account JSON file ([Setup Guide](setup-gcs-credentials.md))

Verify Docker is installed:
```bash
docker --version
docker-compose --version
```

---

## Quick Start

### 1. Prepare Credentials

Ensure your GCS credentials file exists:
```bash
ls -la data/gcs_credentials.json
```

If missing, follow the [GCS Credentials Setup Guide](setup-gcs-credentials.md).

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your values
nano .env
```

Required settings in `.env`:
```bash
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
GCS_BUCKET=your-bucket-name
```

### 3. Start the Service

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### 4. Access the Application

- **API Documentation**: http://localhost:8080/docs
- **Alternative Docs**: http://localhost:8080/redoc
- **Demo Viewer**: http://localhost:8080/demo/climate_tiles_viewer.html

### 5. Stop the Service

```bash
docker-compose down
```


---

## Docker Image

The Dockerfile uses **multi-stage build** for optimization:

- **Builder stage**: Installs dependencies with UV
- **Runtime stage**: Minimal image with only necessary files

**Features:**
- Base: `python:3.13-slim`
- Non-root user
- GDAL for raster processing
- Health checks
- Size: ~400-500MB

---
### Manual Build

```bash
# Build image
docker build -t hob-fastapi:latest .

# Run without docker-compose
docker run -d \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data/gcs_credentials.json:/app/data/gcs_credentials.json:ro \
  hob-fastapi:latest
```



## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker-compose logs
```

**Common issues:**

**Missing credentials:**
```
Error: FileNotFoundError: data/gcs_credentials.json
```
Solution: Create `data/gcs_credentials.json` ([guide](setup-gcs-credentials.md))

**MongoDB connection failed:**
```
Error: ServerSelectionTimeoutError
```
Solutions:
- Verify `MONGO_URI` in `.env`
- Check IP allowlist in MongoDB Atlas
- Test connection string format

**Port conflict:**
```
Error: port 8080 is already allocated
```
Solution: Change port in `docker-compose.yml`:
```yaml
ports:
  - "8081:8080"  # Use different port
```

### Test Connections

**Test MongoDB:**
```bash
docker-compose exec api python -c "from pymongo import MongoClient; print(MongoClient('YOUR_URI').server_info())"
```

**Test GCS:**
```bash
docker-compose exec api python -c "from google.cloud import storage; storage.Client()"
```

**Verify credentials mounted:**
```bash
docker-compose exec api ls -la /app/data/
```

### Rebuild After Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Force rebuild (ignore cache)
docker-compose build --no-cache && docker-compose up -d
```

### Clean Up

```bash
# Stop containers
docker-compose down

# Remove images
docker rmi hob-fastapi:latest

# Clean everything
docker system prune -a
```


---

## Command Reference

```bash
# Start
docker-compose up -d

# Logs
docker-compose logs -f

# Status
docker-compose ps

# Stop
docker-compose down

# Rebuild
docker-compose up -d --build

# Shell access
docker-compose exec api bash

# Clean up
docker-compose down && docker system prune -a
```
