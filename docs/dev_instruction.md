# HOB FastAPI Development Setup Guide

## Prerequisites

- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git
- MongoDB instance (local or cloud)
- Google Cloud Storage account with service account credentials

## Clone the Repository

Choose either HTTPS or SSH method:

### HTTPS
```bash
git clone https://github.com/Ecosystem-2/HOB-FastAPI.Python.git
cd HOB-FastAPI.Python
```

### SSH
```bash
git clone git@github.com:Ecosystem-2/HOB-FastAPI.Python.git
cd HOB-FastAPI.Python
```

## Set Up Development Environment with uv

### 1. Install uv (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using Homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Synchronise Project Dependencies

The project uses `uv` for dependency management. Run:

```bash
uv sync
```

This will:
- Create a virtual environment (.venv) if it doesn't exist
- Install all dependencies from `pyproject.toml` and `uv.lock`
- Use Python 3.13 as specified in `.python-version`

### 3. Activate the Virtual Environment (Optional)

While `uv` can run commands directly, you may want to activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

## Configure Environment Variables

### 1. Create Environment File

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

### 2. Edit .env File

Required environment variables:

```bash
# MongoDB Configuration
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/
MONGO_DB=climate_indices              # optional, defaults to 'climate_indices'
MONGO_ASSETS_COLLECTION=assets        # optional, defaults to 'assets'

# Google Cloud Storage Configuration
GCS_BUCKET=climate-tiles-cluster      # your GCS bucket name
GCS_PREFIX=uploads                    # storage prefix/folder
GOOGLE_APPLICATION_CREDENTIALS=./data/gcs_credentials.json

# Application Configuration
LOG_LEVEL=INFO                        # optional, defaults to 'INFO'
```

### 3. Set Up Google Cloud Storage Credentials

You'll need to generate a service account JSON key file for GCS access.

**Quick Setup:**
```bash
# Create data directory
mkdir -p data

# Move downloaded JSON key to project
mv ~/Downloads/your-project-xxxxx.json ./data/gcs_credentials.json
```

📖 **For detailed instructions**, see [GCS Credentials Setup Guide](setup-gcs-credentials.md)

This guide covers:
- Creating service accounts in Google Cloud Console
- Generating and downloading JSON keys
- Setting proper IAM permissions
- Creating GCS buckets
- Security best practices

### 4. Verify Configuration

```bash
# Check GCS credentials file exists
ls -la ./data/gcs_credentials.json

# Verify .env is configured
cat .env | grep -E "MONGO_URI|GCS_BUCKET|GOOGLE_APPLICATION_CREDENTIALS"
```

## Run the Development Server

### Using uv (Recommended)

```bash
uv run python -m app.main
```

### Using uvicorn directly

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

The server will start at `http://127.0.0.1:8080`

## Verify Installation

### 1. Check API Documentation

Open your browser and navigate to:
- Swagger UI: `http://127.0.0.1:8080/docs`
- ReDoc: `http://127.0.0.1:8080/redoc`

### 2. Test Basic Endpoints

```bash
# Health check (if implemented)
curl http://127.0.0.1:8080/

# List assets
curl http://127.0.0.1:8080/api/climate-indices/assets
```

### 3. View Demo Tiles

If the server is running, you can access the interactive demo:
- Open `app/demo/climate_tiles_viewer.html` in your browser
- Ensure it points to `http://127.0.0.1:8080/api/climate-indices`

---
## Development Workflow

### Running Tests

```bash
# Run specific test file
uv run python tests/test_climate_endpoints.py

# Run polygon query tests
uv run python tests/test_polygon_query.py
```

### Code Organisation

- `app/api/climate/endpoints/` - REST API endpoint handlers
- `app/climate_indices/` - Domain layer (service, repository, storage)
- `app/geotif_converter/` - Raster utilities and conversion tools
- `app/demo/` - Interactive Cesium demos
- `tests/` - Test files and test data

### Adding New Dependencies

```bash
# Add a new package
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade
```

## Troubleshooting

For common issues and solutions, see the [Troubleshooting Guide](troubleshooting.md).

**Quick Fixes:**

- **MongoDB connection fails**: Check `MONGO_URI` and network access in Atlas
- **GCS authentication errors**: Verify credentials file path and permissions
- **Port 8080 in use**: `lsof -ti:8080 | xargs kill -9`
- **Import errors**: Run `uv sync` to reinstall dependencies

## Additional Resources

**Project Documentation:**
- [GCS Credentials Setup](setup-gcs-credentials.md) - Detailed Google Cloud setup
- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions  
- [Pipeline Design](geotif-pipeline-brainstorm.md) - Architecture decisions

**External Documentation:**
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [rio-tiler Documentation](https://cogeotiff.github.io/rio-tiler/)
- [Rasterio Documentation](https://rasterio.readthedocs.io/)

## Git Workflow

### Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### Commit Changes

```bash
git add .
git commit -m "Brief description of changes"
```

### Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Notes

- All file paths in API calls should use absolute paths
- Asset uploads with duplicate filenames will **replace** existing records (upsert behaviour)
- GeoTIFF files are automatically converted to EPSG:4326 during ingestion
