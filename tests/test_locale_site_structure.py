"""Test script for localeData and siteData collections.

Run this after starting the server to verify the new structure.
"""

import requests
import json
import uuid

API_BASE = "http://127.0.0.1:8080/api/climate-indices"


def test_save_site():
    """Test saving a site with locale structure."""
    print("\n=== Testing Site Save ===")
    
    # Generate UUIDs
    locale_id = str(uuid.uuid4())
    
    # Sample polygon (simplified)
    polygon = {
        "type": "Polygon",
        "coordinates": [[
            [117.5, 5.0],
            [117.6, 5.0],
            [117.6, 5.1],
            [117.5, 5.1],
            [117.5, 5.0]
        ]]
    }
    
    # Test data (requires an actual asset_id from your database)
    # You'll need to replace this with a real asset ID
    data = {
        "name": "Test Site - Segama Delta",
        "description": "Test polygon for locale/site structure",
        "tags": "test,climate,demo",
        "polygon_geojson": json.dumps(polygon),
        "asset_ids": "REPLACE_WITH_REAL_ASSET_ID",  # <-- Update this
        "locale_id": locale_id,
        "category": "test,analysis"
    }
    
    response = requests.post(f"{API_BASE}/selections/save", data=data)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code in [200, 201]:
        result = response.json()
        print(f"\n✓ Site saved successfully!")
        print(f"  Site ID: {result['site_id']}")
        print(f"  Locale ID: {result['locale_id']}")
        print(f"  Replaced: {result['replaced']}")
        return result['site_id'], locale_id
    else:
        print(f"\n✗ Save failed: {response.text}")
        return None, None


def test_list_sites():
    """Test listing sites."""
    print("\n=== Testing Site List ===")
    
    response = requests.get(f"{API_BASE}/sites")
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total sites: {data['total']}")
    
    if data['total'] > 0:
        print(f"\nFirst site:")
        print(json.dumps(data['sites'][0], indent=2))
    
    return data


def test_get_site_by_title(title="Test Site - Segama Delta"):
    """Test fetching site by title."""
    print(f"\n=== Testing Get Site by Title: {title} ===")
    
    response = requests.get(f"{API_BASE}/sites/by-title/{title}")
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Found site:")
        print(f"  Site ID: {data['siteID']}")
        print(f"  Title: {data['title']}")
        print(f"  Location: {data['location']['coordinates']}")
        print(f"  Statistics count: {len(data['location'].get('statistics', []))}")
        return data
    else:
        print(f"Not found: {response.text}")
        return None


def test_get_locale(locale_id):
    """Test fetching locale data."""
    print(f"\n=== Testing Get Locale: {locale_id} ===")
    
    response = requests.get(f"{API_BASE}/locale/{locale_id}")
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Locale data:")
        print(f"  Locale ID: {data['localeID']}")
        print(f"  Title: {data['title']}")
        print(f"  Description: {data['description']}")
        print(f"  Site IDs: {data['siteID']}")
        return data
    else:
        print(f"Not found: {response.text}")
        return None


def main():
    """Run all tests."""
    print("=" * 60)
    print("LocaleData and SiteData Structure Tests")
    print("=" * 60)
    
    print("\n⚠️  NOTE: Update REPLACE_WITH_REAL_ASSET_ID with an actual asset ID")
    print("    You can get one from: http://127.0.0.1:8080/api/climate-indices/assets")
    
    # Test 1: Save site
    site_id, locale_id = test_save_site()
    
    if not site_id:
        print("\n✗ Cannot proceed - site save failed")
        print("   Make sure to:")
        print("   1. Start the server: python -m app.main")
        print("   2. Update REPLACE_WITH_REAL_ASSET_ID in this script")
        return
    
    # Test 2: List sites
    test_list_sites()
    
    # Test 3: Get site by title
    test_get_site_by_title()
    
    # Test 4: Get locale
    test_get_locale(locale_id)
    
    print("\n" + "=" * 60)
    print("✓ All tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
