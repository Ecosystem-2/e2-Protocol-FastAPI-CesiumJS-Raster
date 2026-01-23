# Documentation Index

Documentation for the HOB FastAPI Climate Raster Tile Server project.

## Getting Started

Start here if you're new to the project:

1. **[Development Setup](dev_instruction.md)** - Clone repo, install dependencies, configure environment (recommended for local development)
2. **[Docker Deployment](docker-deployment.md)** - Production deployment using Docker
3. **[GCS Credentials Setup](setup-gcs-credentials.md)** - Generate Google Cloud service account credentials
4. **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions

## Architecture & Design

- **[Pipeline Design Brainstorm](geotif-pipeline-brainstorm.md)** - Original design decisions and rationale


## Key Concepts

### Climate Raster Tiles
This service ingests GeoTIFF climate index files, stores them in Google Cloud Storage, and serves them as PNG tiles for visualisation in Cesium.

**Workflow:**
1. Upload GeoTIFF via `/ingest/store`
2. Service extracts metadata, converts to EPSG:4326, uploads to GCS
3. Metadata stored in MongoDB
4. Tiles served via `/tiles/{asset_id}/{z}/{x}/{y}.png`
5. Polygon queries via `/query/polygon`


## Technology Stack

- **Backend**: FastAPI (Python 3.13+)
- **Dependency Management**: uv
- **Raster Processing**: rasterio, rio-tiler
- **Storage**: Google Cloud Storage (GCS)
- **Database**: MongoDB
- **Visualization**: Cesium (frontend)


## Need Help?

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review existing GitHub issues
3. Create a new issue with:
   - Error messages
   - Steps to reproduce
   - Relevant logs (redact credentials)

---

**Last Updated**: January 2026
