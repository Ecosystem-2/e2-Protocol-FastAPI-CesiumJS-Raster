# Troubleshooting Guide

Common issues and solutions when developing with HOB FastAPI.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Database Connection Issues](#database-connection-issues)
- [Google Cloud Storage Issues](#google-cloud-storage-issues)
- [Runtime Errors](#runtime-errors)
- [API Issues](#api-issues)

---

## Installation Issues

### Python Version Mismatch

**Error**: `Python 3.13 or higher required`

**Solution**:
```bash
# Check your Python version
python --version

# Install Python 3.13 using pyenv (recommended)
pyenv install 3.13
pyenv local 3.13

# Or download from python.org
```

### uv Sync Fails

**Error**: `Failed to resolve dependencies`

**Solution**:
```bash
# Clear uv cache
uv cache clean

# Try sync again
uv sync

# If still failing, update uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Import Errors After Installation

**Error**: `ModuleNotFoundError: No module named 'X'`

**Solution**:
```bash
# Ensure dependencies are installed
uv sync

# Verify virtual environment is activated (if running manually)
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Check which Python is being used
which python
python -c "import sys; print(sys.path)"
```

---

## Database Connection Issues

### MongoDB Connection Fails

**Error**: `ServerSelectionTimeoutError: connection timeout`

**Causes and Solutions**:

1. **Incorrect connection string**
   ```bash
   # Verify MONGO_URI in .env
   cat .env | grep MONGO_URI
   
   # Format should be:
   # MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
   ```

2. **Network access not configured**
   - Log into MongoDB Atlas
   - Go to **Network Access**
   - Click **Add IP Address**
   - Add your current IP or `0.0.0.0/0` (for development only)

3. **Database user not created**
   - Go to **Database Access** in MongoDB Atlas
   - Create a user with read/write permissions
   - Use these credentials in `MONGO_URI`

4. **Firewall blocking connection**
   ```bash
   # Test connection using mongosh
   mongosh "mongodb+srv://cluster.mongodb.net/" --username your-user
   ```

### Authentication Failed

**Error**: `Authentication failed`

**Solution**:
```bash
# Verify credentials in MONGO_URI
# Ensure password is URL-encoded if it contains special characters

# Example: if password is "p@ssw0rd!", encode it as "p%40ssw0rd%21"
python -c "from urllib.parse import quote_plus; print(quote_plus('p@ssw0rd!'))"
```

### Database/Collection Not Found

**Error**: `Database or collection doesn't exist`

**Solution**:
- MongoDB creates databases/collections automatically when first document is inserted
- Verify `MONGO_DB` and `MONGO_ASSETS_COLLECTION` in `.env`
- Default values: `climate_indices` (database), `assets` (collection)

---

## Google Cloud Storage Issues

### Authentication Errors

**Error**: `Could not automatically determine credentials`

**Solution**:
```bash
# Verify environment variable is set
echo $GOOGLE_APPLICATION_CREDENTIALS

# Check file exists
ls -la ./data/gcs_credentials.json

# Verify file is valid JSON
cat ./data/gcs_credentials.json | jq .

# Ensure .env is properly configured
grep GOOGLE_APPLICATION_CREDENTIALS .env
```

### Permission Denied

**Error**: `403 Forbidden` or `Permission denied`

**Causes and Solutions**:

1. **Service account lacks permissions**
   - Go to Google Cloud Console → IAM & Admin → Service Accounts
   - Verify service account has **Storage Admin** or **Storage Object Admin** role

2. **Bucket-level permissions**
   - Go to Cloud Storage → Your Bucket → Permissions
   - Add service account email with appropriate role

3. **Bucket doesn't exist**
   ```bash
   # List buckets
   gcloud storage buckets list
   
   # Create bucket if missing
   gcloud storage buckets create gs://climate-tiles-cluster --location=us-central1
   ```

### Invalid Credentials File

**Error**: `Invalid JSON` or `Credentials file is malformed`

**Solution**:
1. Re-download credentials from Google Cloud Console
2. Ensure no extra characters were added
3. Validate JSON:
   ```bash
   python -c "import json; json.load(open('./data/gcs_credentials.json'))"
   ```

For more details, see [GCS Credentials Setup Guide](setup-gcs-credentials.md).

---

## Runtime Errors

### Port Already in Use

**Error**: `Address already in use` or `Port 8080 is already allocated`

**Solution**:
```bash
# Find process using port 8080
lsof -ti:8080

# Kill the process
lsof -ti:8080 | xargs kill -9

# Or use a different port
uv run uvicorn app.main:app --port 8081
```

### File Upload Errors

**Error**: `File too large` or `Upload failed`

**Solution**:
1. Check file size limits (FastAPI default is 100MB)
2. Verify GeoTIFF file is valid:
   ```bash
   gdalinfo your-file.tif
   ```
3. Check disk space:
   ```bash
   df -h
   ```

### GeoTIFF Processing Errors

**Error**: `Failed to read GeoTIFF` or `Invalid raster format`

**Solution**:
```bash
# Verify file with GDAL
gdalinfo -stats your-file.tif

# Check file format
file your-file.tif

# Test reading with rasterio
python -c "import rasterio; rasterio.open('your-file.tif')"
```

---

## API Issues

### Tiles Not Displaying

**Problem**: Tiles show blank or don't load in Cesium

**Debugging Steps**:

1. **Check asset exists in database**
   ```bash
   curl http://127.0.0.1:8080/api/climate-indices/assets
   ```

2. **Test tile endpoint directly**
   ```bash
   # Get a tile at zoom 5, x=10, y=10
   curl "http://127.0.0.1:8080/api/climate-indices/tiles/ASSET_ID/5/10/10.png" \
     --output test-tile.png
   
   # Verify it's a valid PNG
   file test-tile.png
   ```

3. **Check COG URI in database**
   - Ensure asset has valid `storage.cog.uri`
   - URI format: `gs://bucket-name/path/to/file.cog.tif`

4. **Verify colormap name**
   ```bash
   # Valid colormap names (211 total)
   curl "http://127.0.0.1:8080/api/climate-indices/tiles/ASSET_ID/5/10/10.png?colormap_name=viridis"
   ```

### Polygon Query Returns Empty Results

**Problem**: `/query/polygon` returns zero statistics

**Debugging Steps**:

1. **Verify polygon is valid GeoJSON**
   ```bash
   # Validate GeoJSON
   echo '{"type":"Polygon","coordinates":[...]}' | jq .
   ```

2. **Check polygon overlaps raster bounds**
   - Get asset bounds from `/assets/{asset_id}`
   - Ensure polygon intersects with bounds

3. **Verify request format**
   - Must use `FormData`, not JSON
   - `asset_id`: string
   - `polygon_geojson`: stringified GeoJSON

4. **Test with known polygon**
   ```bash
   curl -X POST "http://127.0.0.1:8080/api/climate-indices/query/polygon" \
     -F "asset_id=YOUR_ASSET_ID" \
     -F 'polygon_geojson={"type":"Polygon","coordinates":[[[116.0,4.0],[117.0,4.0],[117.0,5.0],[116.0,5.0],[116.0,4.0]]]}'
   ```

### Form Data vs JSON Issues

**Error**: `422 Unprocessable Entity` or `Field required`

**Solution**:
- Endpoints like `/ingest` and `/query/polygon` expect `FormData`, not JSON
- Use `multipart/form-data` content type
- In JavaScript:
  ```javascript
  const formData = new FormData();
  formData.append('asset_id', assetId);
  formData.append('polygon_geojson', JSON.stringify(polygon));
  
  fetch('/api/climate-indices/query/polygon', {
    method: 'POST',
    body: formData  // Not JSON.stringify()
  });
  ```

### CORS Errors

**Error**: `Access to fetch blocked by CORS policy`

**Solution**:
- Check CORS middleware configuration in `app/main.py`
- Verify allowed origins include your frontend URL
- For development, ensure `http://localhost` or `http://127.0.0.1` is allowed

---

## Getting Help

If you can't resolve an issue:

1. **Check server logs**
   ```bash
   # Run server with debug logging
   LOG_LEVEL=DEBUG uv run python -m app.main
   ```

2. **Review documentation**
   - [Development Setup](dev_instruction.md)
   - [GCS Credentials](setup-gcs-credentials.md)
   - [Architecture Overview](../.github/copilot-instructions.md)

3. **Search existing issues**
   - Check GitHub issues for similar problems

4. **Create a new issue**
   - Include error messages
   - Provide steps to reproduce
   - Share relevant logs (redact sensitive information)

---

## Quick Diagnostic Commands

```bash
# Check Python version
python --version

# Verify dependencies
uv sync

# Test MongoDB connection
python -c "from pymongo import MongoClient; print(MongoClient('YOUR_MONGO_URI').server_info())"

# Test GCS credentials
gcloud auth activate-service-account --key-file=./data/gcs_credentials.json
gcloud storage buckets list

# Check server is running
curl http://127.0.0.1:8080/docs

# View all assets
curl http://127.0.0.1:8080/api/climate-indices/assets | jq .
```
