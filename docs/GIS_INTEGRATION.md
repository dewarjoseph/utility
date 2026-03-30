# Santa Cruz County GIS Data Integration Guide

## Overview
This guide explains how to connect the Land Utility Engine to real Santa Cruz County GIS datasets.

## Data Sources

### 1. Santa Cruz County GISWeb
**URL**: https://gis.santacruzcountyca.gov/arcgis/rest/services

**Available Layers:**
- Assessor's Parcels (APN, acreage, zoning)
- Zoning History
- Sanitation As-Built Drawings
- Well Locations
- Recorded Surveys

**Access**: Public, no API key required for most layers

**Integration Steps:**
1. Identify layer endpoint (e.g., `/Parcels/MapServer/0`)
2. Use ArcGIS REST API query format
3. Example query:
```python
url = "https://gis.santacruzcountyca.gov/arcgis/rest/services/Parcels/MapServer/0/query"
params = {
    "geometry": f"{lon},{lat}",
    "geometryType": "esriGeometryPoint",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "*",
    "returnGeometry": "false",
    "f": "json"
}
response = requests.get(url, params=params)
```

### 2. LiDAR Terrain Models (2020)
**Source**: Santa Cruz County Open Data Portal

**Datasets:**
- Digital Terrain Model (DTM) - 3ft resolution bare earth
- Digital Surface Model (DSM) - First returns with vegetation

**Format**: GeoTIFF raster

**Usage:**
- Download tiles covering your area of interest
- Use `rasterio` or `gdal` to query elevation at specific coordinates
- Extract slope, aspect, and drainage patterns

**Example:**
```python
import rasterio
from rasterio.transform import rowcol

with rasterio.open('santa_cruz_dtm.tif') as src:
    row, col = rowcol(src.transform, lon, lat)
    elevation = src.read(1)[row, col]
```

### 3. First Street Foundation Climate Risk
**URL**: https://api.firststreet.org/

**Data**: Wildfire, flood, heat risk scores

**Authentication**: Requires API key (free tier available)

**Setup:**
```bash
export FIRST_STREET_API_KEY="your_key_here"
```

**Example Query:**
```python
headers = {"Authorization": f"Bearer {api_key}"}
url = f"https://api.firststreet.org/v1/location/{lat},{lon}/risk"
response = requests.get(url, headers=headers)
```

### 4. California Open Data
**URL**: https://data.ca.gov/

**Relevant Datasets:**
- County Land Use Surveys
- LUCAS-W Land Use/Water Demand Model
- State Parcel Database

**Format**: Shapefiles, CSV, GeoJSON

## Feature Engineering from GIS Data

### Terrain Features
```python
# From LiDAR DTM
elevation_ft = query_dtm(lat, lon)
slope_percent = calculate_slope(dtm_tile, lat, lon)
aspect_degrees = calculate_aspect(dtm_tile, lat, lon)
```

### Risk Features
```python
# Inverted for ML (higher = better)
wildfire_safety = 1.0 - (wildfire_risk_score / 10.0)
flood_safety = 1.0 - (flood_risk_score / 10.0)
```

### Accessibility Features
```python
# Distance-based accessibility scores
sewer_accessibility = 1.0 / (1.0 + distance_to_sewer / 500.0)
water_accessibility = 1.0 / (1.0 + distance_to_water / 500.0)
```

## Current Implementation Status

✅ **Mock Data Mode**: `gis_loader.py` currently returns realistic mock data
🔄 **Production Mode**: To enable real API calls:
1. Uncomment API query code in `gis_loader.py`
2. Set environment variables for API keys
3. Download LiDAR tiles to `gis_cache/` directory

## Next Steps

1. **Download LiDAR Data**: Get DTM tiles for Santa Cruz from County portal
2. **API Keys**: Register for First Street Foundation API
3. **Test Queries**: Verify ArcGIS REST endpoints with sample coordinates
4. **Cache Strategy**: Implement local caching to avoid repeated API calls
