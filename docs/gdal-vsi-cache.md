# GDAL VSI Cache — Tile "File Not Found" After Upload

## Background

HOB-FastAPI serves map tiles from Cloud-Optimized GeoTIFFs (COGs) stored in Google Cloud
Storage. The tile endpoint uses [rio-tiler](https://github.com/cogeotiff/rio-tiler)'s
`COGReader`, which opens GCS files via GDAL's `/vsigs/` virtual filesystem driver.

GDAL caches the results of GCS HTTP requests — including negative "file not found" responses —
in an in-memory VSI curl cache. This cache is per-process and persists for the lifetime of
the container. Files uploaded to GCS after the process started can remain invisible to GDAL
until the cache is cleared or the container restarts.

---

## Symptom

After uploading a new raster via `/ingest`, tile requests return:

```
Tile render failed: '/vsigs/unstable-e2-insight/uploads/<uuid>.cog.tif' does not exist
in the file system, and is not recognized as a supported dataset name.
```

Files uploaded in previous container sessions (i.e. before the current process started)
load correctly. Only files uploaded during the current process lifetime are affected.

Restarting the container (`docker compose restart`) resolves it temporarily — until the
next upload.

---

## Root Cause

### Original fix (commit `c5f98da`, merged April 2026)

`blob_storage.py` added `_clear_gdal_vsi_cache()`, called after every `blob.upload_from_string()`.
The function uses ctypes to call GDAL's `VSICurlClearCache()` C function, which flushes the
in-memory cache.

### Regression — early return on system GDAL

The function had two lookup strategies:

1. System GDAL — found via `ctypes.util.find_library("gdal")`
2. rasterio's bundled GDAL — found by inspecting `rasterio.__file__` and searching the `.libs/` directory

The original code returned early after successfully clearing the system GDAL:

```python
lib.VSICurlClearCache()
logger.debug("Cleared GDAL VSI cache via system library: %s", lib_name)
return  # <-- BUG: exits before clearing rasterio's GDAL
```

### Why this matters in Docker

The Dockerfile installs **system GDAL** (`libgdal-dev` via apt) in the runtime image, AND the
rasterio binary wheel ships with its **own bundled libgdal** (in `.libs/` inside the wheel).
These are two separate shared library instances loaded into the same process with independent
in-memory caches.

```
Process memory
├── /usr/lib/x86_64-linux-gnu/libgdal.so.XX   ← system GDAL
│   └── VSI curl cache (empty after clear)
└── /app/.venv/.../rasterio/.libs/libgdal-XX.so ← rasterio's bundled GDAL
    └── VSI curl cache (NOT cleared — COGReader uses this one)
```

`COGReader` (and all rasterio file access) uses rasterio's **own** libgdal instance. Calling
`VSICurlClearCache()` on the system GDAL instance has no effect on rasterio's cache.

The early `return` meant strategy 2 (rasterio's bundled GDAL) was never reached, so the cache
that actually blocks tile access was never cleared.

---

## Fix (applied 2026-06-29)

`app/climate_indices/blob_storage.py` — `_clear_gdal_vsi_cache()`

Removed the early `return`. Both strategies are now always attempted unconditionally. A
`cleared` flag tracks whether either succeeded, replacing the early-return pattern.

```python
# Before
lib.VSICurlClearCache()
logger.debug("Cleared GDAL VSI cache via system library: %s", lib_name)
return   # never reaches rasterio's GDAL

# After
lib.VSICurlClearCache()
logger.debug("Cleared GDAL VSI cache via system library: %s", lib_name)
cleared = True   # continues to strategy 2
```

Strategy 2 then loads rasterio's bundled libgdal by path via `ctypes.CDLL()`. Because
the dynamic linker deduplicates by inode, this returns the same in-process handle that
rasterio already loaded — calling `VSICurlClearCache()` on it clears the same cache that
`COGReader` reads from.

The fix is safe regardless of environment:
- **Docker (system GDAL + rasterio bundled GDAL):** both caches cleared
- **Environment where rasterio uses system GDAL (no `.libs/`):** strategy 2 finds nothing, strategy 1 clears the shared cache — correct outcome
- **Neither found:** `logger.warning` emitted — observable in logs

---

## Deployment

To pick up the fix, rebuild and restart the container:

```bash
docker compose up --build -d
```

### Immediate relief without redeploy

If you need to unblock uploads before the fix is deployed, restart the container to flush
the in-memory cache:

```bash
docker compose restart
```

This clears all GDAL VSI cache state. Files already in GCS will be immediately accessible.
The underlying bug persists until the code fix is deployed — subsequent uploads will
re-trigger the issue.

---

## Files Changed

| File | Change |
|---|---|
| `app/climate_indices/blob_storage.py` | Removed early `return` from `_clear_gdal_vsi_cache()`; added `cleared` flag; strategy 2 now always runs |

---

## Architecture Note

The `persist_climate_index` function in `asset_service.py` calls `blob_store.save_bytes()`
twice per ingest — once for the raw `.tif` and once for the `.cog.tif`. Each call now
clears both GDAL caches. The tile endpoint uses the `.cog.tif` URI stored in MongoDB, so
the second call is the critical one.

---

## If the Issue Recurs

If "file not found" errors return after this fix is deployed, check the logs for:

```
Could not clear GDAL VSI cache: no suitable GDAL library found
```

This warning means neither strategy found a loadable GDAL library. Possible causes:
- rasterio was installed without a bundled GDAL and the system GDAL shared object name
  changed (e.g. major version bump from `libgdal.so.34` to `libgdal.so.35`)
- A non-standard rasterio build that embeds GDAL under a different name

In that case, adding `CPL_VSIL_CURL_CACHE_SIZE=0` to `docker-compose.yml` disables the
VSI cache entirely as a fallback (at some performance cost for repeated reads of the same
files):

```yaml
environment:
  CPL_VSIL_CURL_CACHE_SIZE: "0"
```
