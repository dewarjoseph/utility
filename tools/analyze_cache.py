"""
Analyze downloaded GIS data and identify what's available.
"""

import os
from pathlib import Path
import zipfile

def analyze_gis_cache(cache_dir="gis_cache"):
    """Analyze what was downloaded."""
    cache_path = Path(cache_dir)
    
    print("="*60)
    print("GIS CACHE ANALYSIS")
    print("="*60)
    
    # Count files by type
    stats = {
        "shapefiles": [],
        "csvs": [],
        "geotiffs": [],
        "other": []
    }
    
    for root, dirs, files in os.walk(cache_path):
        for file in files:
            filepath = Path(root) / file
            
            if file.endswith('.zip'):
                # Check if it's a shapefile
                try:
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        names = zf.namelist()
                        if any(n.endswith('.shp') for n in names):
                            stats["shapefiles"].append(filepath)
                        else:
                            stats["other"].append(filepath)
                except:
                    stats["other"].append(filepath)
            elif file.endswith('.csv'):
                stats["csvs"].append(filepath)
            elif file.endswith(('.tif', '.tiff')):
                stats["geotiffs"].append(filepath)
            else:
                stats["other"].append(filepath)
    
    # Print summary
    print(f"\nShapefiles (ZIP): {len(stats['shapefiles'])}")
    print(f"CSV files: {len(stats['csvs'])}")
    print(f"GeoTIFF files: {len(stats['geotiffs'])}")
    print(f"Other files: {len(stats['other'])}")
    
    # Show priority shapefiles
    print("\n" + "="*60)
    print("PRIORITY SHAPEFILES FOUND:")
    print("="*60)
    
    priority_keywords = ["parcel", "zoning", "flood", "fire", "hazard", "utility"]
    priority_files = []
    
    for shp in stats["shapefiles"]:
        name_lower = shp.name.lower()
        if any(kw in name_lower for kw in priority_keywords):
            priority_files.append(shp)
            print(f"  * {shp.relative_to(cache_path)}")
    
    # Check for LiDAR
    print("\n" + "="*60)
    print("LIDAR/ELEVATION DATA:")
    print("="*60)
    
    lidar_keywords = ["lidar", "dtm", "dem", "elevation"]
    lidar_files = []
    
    for shp in stats["shapefiles"]:
        name_lower = shp.name.lower()
        if any(kw in name_lower for kw in lidar_keywords):
            lidar_files.append(shp)
    
    for tif in stats["geotiffs"]:
        lidar_files.append(tif)
    
    if lidar_files:
        for f in lidar_files:
            print(f"  * {f.relative_to(cache_path)}")
    else:
        print("  ! NO LIDAR DATA FOUND")
        print("\n  LiDAR data is typically NOT in the DCAT catalog.")
        print("  You need to download it separately from:")
        print("  - USGS National Map: https://apps.nationalmap.gov/downloader/")
        print("  - OpenTopography: https://opentopography.org/")
        print("  - Santa Cruz County direct download (if available)")
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    
    if len(stats["shapefiles"]) > 0:
        print(f"  OK You have {len(stats['shapefiles'])} shapefiles ready to use")
        print("  -> These contain vector GIS data (parcels, roads, zones)")
        print("  -> Extract with: unzip filename.zip")
    
    if len(stats["geotiffs"]) == 0:
        print("\n  ! Missing LiDAR/elevation raster data")
        print("  -> Download from USGS National Map")
        print("  -> Search for 'Santa Cruz County California 1m DEM'")
        print("  -> Place .tif files in gis_cache/priority/")
    
    print("\n" + "="*60)
    print(f"Total files: {sum(len(v) for v in stats.values())}")
    print("="*60)

if __name__ == "__main__":
    analyze_gis_cache()
