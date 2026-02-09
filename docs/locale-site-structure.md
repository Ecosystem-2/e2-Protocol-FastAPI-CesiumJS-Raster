# LocaleData and SiteData Structure

## Overview

The polygon selection system now stores data in two MongoDB collections following the E2 project structure:

1. **`localeData`** - Parent collection aggregating sites
2. **`siteData`** - Individual site records with polygon geometry and statistics

## Data Models

### LocaleData

```json
{
  "_id": "MongoDB ObjectId",
  "localeID": "UUID (unique)",
  "siteID": ["UUID array"],
  "projectID": "UUID (optional)",
  "title": "String",
  "description": "String",
  "creationDate": "ISO8601 DateTime"
}
```

**Default Values:**
- Title: "Segama River"
- Description: "Humid Heat Stress and PPET selection"
- Only one localeData record per localeID

### SiteData

```json
{
  "siteID": "UUID (unique)",
  "localeID": "UUID (parent reference)",
  "userID": "UUID (optional)",
  "projectID": "UUID (optional)",
  "title": "String (required, unique)",
  "desc": "String (optional)",
  "creationDateTime": "ISO8601 DateTime",
  "location": {
    "coordinates": [lon, lat, height],
    "polygon": { "type": "Polygon", "coordinates": [[...]]] },
    "centroid": { "lon": float, "lat": float },
    "statistics": [
      {
        "asset_id": "...",
        "index_type": "ppet",
        "units": "ratio",
        "count": 536,
        "min": 0.0,
        "max": 1.0,
        "mean": 0.59,
        "std": 0.49
      }
    ]
  },
  "mediaID": ["UUID array (optional)"],
  "category": ["String array (optional)"],
  "tags": ["String array (optional)"]
}
```

## API Changes

### POST `/api/climate-indices/selections/save`

**New Parameters:**
- `locale_id` (Form, **required**): Parent locale UUID
- `user_id` (Form, optional): User UUID
- `project_id` (Form, optional): Project UUID
- `category` (Form, optional): Comma-separated categories

**Behaviour:**
1. Creates/updates siteData by title (case-insensitive)
2. Ensures localeData exists (creates if missing)
3. Adds siteID to localeData.siteID array
4. Stores polygon, centroid, and statistics in `location` field
5. Backward compatibility: Also saves to `polygon_selections` collection

**Response:**
```json
{
  "site_id": "UUID",
  "selection_id": "ObjectId (legacy)",
  "locale_id": "UUID",
  "title": "Site name",
  "replaced": true/false,
  "statistics_count": 3,
  "message": "Site created/updated"
}
```

### New Endpoints

#### GET `/api/climate-indices/sites`
List all sites with optional locale filtering.

Query params: `locale_id` (optional)

#### GET `/api/climate-indices/sites/by-title/{title}`
Fetch site by case-insensitive title.

#### GET `/api/climate-indices/locale/{locale_id}`
Retrieve localeData with all site references.

## Frontend Changes (Demo3)

### Automatic Locale ID Management

The `demo3-common.js` now:
1. Generates a UUID for `locale_id` on first save
2. Persists it in `WorkflowState` for the session
3. Automatically includes it in all save requests

```javascript
let localeId = WorkflowState.get('locale_id');
if (!localeId) {
  localeId = API.generateUUID();
  WorkflowState.set('locale_id', localeId);
}
formData.append('locale_id', localeId);
```

### Updated API Call

```javascript
API.saveSelection(name, description, tags, polygon, stats, assetIds)
// Now automatically includes locale_id in FormData
```

## Database Collections

### Indexes

**localeData:**
- `localeID` (unique)
- `title`

**siteData:**
- `siteID` (unique)
- `localeID`
- `title` (case-insensitive collation)

## Upsert Strategy

### SiteData
- Matches by **title** (case-insensitive)
- If exists: Replace entire record, preserve `siteID` and `creationDateTime`
- If new: Generate new `siteID` UUID, insert record

### LocaleData
- Created once per `localeID`
- Subsequent saves add to `siteID` array using `$addToSet`

## Backward Compatibility

The system maintains dual persistence:
1. **New structure**: `localeData` + `siteData`
2. **Legacy**: `polygon_selections` (original implementation)

All existing endpoints (`/selections`, `/selections/by-name`, etc.) continue to work with the legacy collection.

## Implementation Files

### New Files
- `app/climate_indices/locale_site_repository.py` - Repository for localeData/siteData
- `docs/locale-site-structure.md` - This document

### Modified Files
- `app/climate_indices/models.py` - Added `LocaleData`, `SiteData`, `SiteLocation`
- `app/api/climate/endpoints/selections.py` - Updated save logic, added site endpoints
- `app/demo/static/demo3-common.js` - Automatic locale_id generation

## Usage Example

### 1. Upload GeoTIFF (Step 1-2)
```javascript
// Upload climate asset and display tiles
```

### 2. Draw Polygon (Step 3)
```javascript
// Draw polygon and query statistics
```

### 3. Save Selection (Step 4)
```javascript
const response = await API.saveSelection(
  "Segama Delta Heat Stress",
  "High WBGT area analysis",
  "climate,heat,risk",
  polygonGeoJSON,
  queryResults,
  "asset-id-1,asset-id-2"
);

// Response:
// {
//   "site_id": "ca781d4c-7db0-405b-aaef-5ae3b3a71322",
//   "locale_id": "d35051c9-9444-4367-ae59-e77b9c58f91e",
//   "title": "Segama Delta Heat Stress",
//   "replaced": false,
//   "statistics_count": 2,
//   "message": "Site created"
// }
```

### 4. Retrieve Sites
```javascript
// List all sites
const sites = await fetch('/api/climate-indices/sites');

// Get specific locale
const locale = await fetch('/api/climate-indices/locale/d35051c9-...');
```

## Future Enhancements

1. **User Authentication**: Populate `userID` from session
2. **Project Management**: Link sites to projects via `projectID`
3. **Media Integration**: Store mediaID references for photos/videos
4. **Bulk Operations**: Import/export multiple sites
5. **CZML Export**: Export entire locale with all sites
