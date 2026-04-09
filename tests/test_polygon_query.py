"""Test polygon queries against climate assets.

Usage:
    # Stats endpoint (renamed)
    python test_polygon_query.py --asset-id YOUR_ASSET_ID --polygon small_center
    python test_polygon_query.py --asset-id YOUR_ASSET_ID --polygon kampung_dagat
    
    # Pixels endpoint (new - CSV/JSON)
    python test_polygon_query.py --asset-id YOUR_ASSET_ID --polygon small_center --pixels
    python test_polygon_query.py --asset-id YOUR_ASSET_ID --polygon small_center --pixels --format json
    
    # Multiple assets and polygons
    python test_polygon_query.py --asset-ids ID1,ID2 --polygons small_center,kampung_dagat
    
    # List available test polygons
    python test_polygon_query.py --list-polygons
"""

import argparse
import json
import requests
from pathlib import Path


def load_test_polygons():
    """Load test polygons from JSON file."""
    polygon_file = Path(__file__).parent / "test_polygons.json"
    with open(polygon_file) as f:
        return json.load(f)


def list_available_polygons():
    """List all available test polygons."""
    data = load_test_polygons()
    print("\n📍 Available Test Polygons:\n")
    print(f"Asset bounds: {data['asset_bounds']}\n")
    
    for name, polygon_data in data["polygons"].items():
        print(f"  {name:20} - {polygon_data['description']}")
        print(f"  {'':20}   Area: ~{polygon_data['area_approx_km2']} km²")
        print(f"  {'':20}   Use: {polygon_data['use_case']}\n")


def query_polygons_stats(asset_ids: list[str], polygon_names: list[str], base_url: str = "http://localhost:8080"):
    """Query multiple assets with multiple polygons for statistics."""
    data = load_test_polygons()
    
    # Validate all polygon names
    invalid_polygons = [name for name in polygon_names if name not in data["polygons"]]
    if invalid_polygons:
        print(f"❌ Polygons not found: {', '.join(invalid_polygons)}")
        list_available_polygons()
        return
    
    # Build polygons array
    polygons = [data["polygons"][name]["geometry"] for name in polygon_names]
    
    print(f"\n🔍 Querying {len(asset_ids)} asset(s) with {len(polygon_names)} polygon(s)")
    for name in polygon_names:
        print(f"   - {name}: {data['polygons'][name]['description']}")
    print()
    
    # Make the API request (UPDATED ENDPOINT)
    url = f"{base_url}/api/climate-indices/query/polygons/stats"
    payload = {
        "asset_ids": ",".join(asset_ids),
        "polygons_geojson": json.dumps(polygons)
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        
        result = response.json()
        print("✅ Query successful!\n")
        print(f"📊 Results: {result['assetCount']} assets × {result['polygonCount']} polygons\n")

        # Display results
        for asset_id, asset_data in result["results"].items():
            print(f"Asset ID: {asset_id}")
            print(f"  Type: {asset_data['indexType']}, Units: {asset_data['units']}")
            print(f"  Filename: {asset_data['metadata']['filename']}")

            for poly_result in asset_data["polygons"]:
                poly_idx = poly_result["polygonIndex"]
                poly_name = polygon_names[poly_idx]

                if poly_result.get("error"):
                    print(f"    ❌ {poly_name}: {poly_result['error']}")
                else:
                    stats = poly_result["stats"]
                    print(f"    ✅ {poly_name}:")
                    print(f"       Count: {stats['count']:,} pixels")
                    if stats['count'] > 0:
                        print(f"       Min:   {stats['min']:.4f}")
                        print(f"       Max:   {stats['max']:.4f}")
                        print(f"       Mean:  {stats['mean']:.4f}")
                        print(f"       Std:   {stats['std']:.4f}")
            print()
        
        return result
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Could not connect to {base_url}")
        print("   Make sure your FastAPI server is running.")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        try:
            error_detail = response.json()
            print(f"   Detail: {error_detail.get('detail', 'No details')}")
        except:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def query_polygons_pixels(
    asset_ids: list[str], 
    polygon_names: list[str], 
    format: str = "csv",
    base_url: str = "http://localhost:8080"
):
    """Query multiple assets with multiple polygons for raw pixel values."""
    data = load_test_polygons()
    
    # Validate all polygon names
    invalid_polygons = [name for name in polygon_names if name not in data["polygons"]]
    if invalid_polygons:
        print(f"❌ Polygons not found: {', '.join(invalid_polygons)}")
        list_available_polygons()
        return
    
    # Build polygons array
    polygons = [data["polygons"][name]["geometry"] for name in polygon_names]
    
    print(f"\n🔍 Extracting pixels from {len(asset_ids)} asset(s) × {len(polygon_names)} polygon(s)")
    print(f"   Format: {format.upper()}")
    for name in polygon_names:
        print(f"   - {name}: {data['polygons'][name]['description']}")
    print()
    
    # Make the API request (NEW ENDPOINT)
    url = f"{base_url}/api/climate-indices/query/polygons/pixels"
    payload = {
        "asset_ids": ",".join(asset_ids),
        "polygons_geojson": json.dumps(polygons),
        "format": format
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        
        if format.lower() == "csv":
            # Save CSV to file
            output_file = Path(__file__).parent / "output_pixels.csv"
            with open(output_file, 'w') as f:
                f.write(response.text)
            
            # Show preview
            lines = response.text.split('\n')
            print("✅ CSV generated!\n")
            print(f"📄 Saved to: {output_file}")
            print(f"   Total lines: {len(lines):,}")
            print(f"\n   Preview (first 10 rows):")
            for i, line in enumerate(lines[:10]):
                print(f"   {line}")
            
            return response.text
        else:
            # JSON format
            result = response.json()
            print("✅ Pixels extracted!\n")
            print(f"📊 Results: {result['assetCount']} assets × {result['polygonCount']} polygons\n")

            # Display summary
            for asset_id, asset_data in result["results"].items():
                print(f"Asset ID: {asset_id}")
                print(f"  Type: {asset_data['indexType']}, Units: {asset_data['units']}")

                for poly_result in asset_data["polygons"]:
                    poly_idx = poly_result["polygonIndex"]
                    poly_name = polygon_names[poly_idx]

                    if poly_result.get("error"):
                        print(f"    ❌ {poly_name}: {poly_result['error']}")
                    else:
                        pixel_count = poly_result["pixelCount"]
                        print(f"    ✅ {poly_name}: {pixel_count:,} pixels")
                        if pixel_count > 0 and pixel_count <= 5:
                            print(f"       Sample pixels: {poly_result['pixels']}")
                print()
            
            # Save JSON to file
            output_file = Path(__file__).parent / "output_pixels.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"📄 Full JSON saved to: {output_file}")
            
            return result
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Could not connect to {base_url}")
        print("   Make sure your FastAPI server is running.")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        try:
            error_detail = response.json()
            print(f"   Detail: {error_detail.get('detail', 'No details')}")
        except:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Test polygon queries for climate assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stats for single asset and polygon
  python test_polygon_query.py --asset-id 67890abc --polygon small_center
  
  # Stats for multiple assets and polygons
  python test_polygon_query.py --asset-ids ID1,ID2 --polygons small_center,kampung_dagat
  
  # Extract pixels as CSV
  python test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels
  
  # Extract pixels as JSON
  python test_polygon_query.py --asset-id 67890abc --polygon small_center --pixels --format json
        """
    )
    parser.add_argument("--asset-id", help="Single MongoDB asset ID to query (deprecated: use --asset-ids)")
    parser.add_argument("--asset-ids", help="Comma-separated MongoDB asset IDs to query")
    parser.add_argument("--polygon", help="Single test polygon name (deprecated: use --polygons)")
    parser.add_argument("--polygons", help="Comma-separated test polygon names")
    parser.add_argument("--pixels", action="store_true", help="Extract raw pixel values instead of statistics")
    parser.add_argument("--format", default="csv", choices=["csv", "json"], help="Output format for pixels (default: csv)")
    parser.add_argument("--list-polygons", action="store_true", help="List available test polygons")
    parser.add_argument("--base-url", default="http://localhost:8080", help="FastAPI base URL")
    
    args = parser.parse_args()
    
    if args.list_polygons:
        list_available_polygons()
        return
    
    # Handle backward compatibility
    asset_ids = []
    if args.asset_ids:
        asset_ids = [aid.strip() for aid in args.asset_ids.split(",")]
    elif args.asset_id:
        asset_ids = [args.asset_id]
    
    polygon_names = []
    if args.polygons:
        polygon_names = [p.strip() for p in args.polygons.split(",")]
    elif args.polygon:
        polygon_names = [args.polygon]
    
    if not asset_ids or not polygon_names:
        parser.print_help()
        print("\n" + "="*60)
        list_available_polygons()
        return
    
    # Choose endpoint based on --pixels flag
    if args.pixels:
        query_polygons_pixels(asset_ids, polygon_names, args.format, args.base_url)
    else:
        query_polygons_stats(asset_ids, polygon_names, args.base_url)


if __name__ == "__main__":
    main()
