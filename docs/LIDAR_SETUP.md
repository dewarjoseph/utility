# LiDAR DTM Setup Guide for Santa Cruz County

## Where to Get LiDAR Data (FREE)

### Option 1: Santa Cruz County Open Data Portal (Recommended)
**URL**: https://gis.santacruzcountyca.gov/

**Steps:**
1. Navigate to "Open Data" or "Downloads"
2. Look for "LiDAR 2020" or "Digital Terrain Model"
3. Download tiles covering your area of interest
4. Files are typically in GeoTIFF (.tif) format

### Option 2: USGS National Map (Covers all of USA)
**URL**: https://apps.nationalmap.gov/downloader/

**Steps:**
1. Click "Find Products"
2. Set extent to Santa Cruz County (use map or coordinates)
3. Select "Elevation Products (3DEP)"
4. Filter by "1 meter DEM" or "LiDAR Point Cloud"
5. Download tiles as GeoTIFF

### Option 3: OpenTopography (Research-grade)
**URL**: https://opentopography.org/

**Steps:**
1. Search for "Santa Cruz California"
2. Select available LiDAR datasets
3. Download as GeoTIFF raster

## File Placement

Once downloaded, place files in the `gis_cache/` directory:

```
utility/
├── gis_cache/
│   ├── santa_cruz_dtm_tile1.tif
│   ├── santa_cruz_dtm_tile2.tif
│   └── santa_cruz_dtm_tile3.tif  (system auto-merges multiple tiles)
```

**Naming**: Files must contain "dtm" in the filename (case-insensitive)

## File Specifications

**Recommended Format:**
- Format: GeoTIFF (.tif)
- Resolution: 1-3 meter (3-10 feet)
- Coordinate System: WGS84 or NAD83
- Data Type: Float32 (elevation in meters)

**Typical File Size:**
- 1 sq mile at 3ft resolution: ~50-100 MB
- Santa Cruz County (full): ~2-5 GB total

## Verification

After placing files, restart the daemon:

```powershell
streamlit run app.py
```

Look for console output:
```
[GIS] ✓ Loaded LiDAR DTM: santa_cruz_dtm_tile1.tif
```

Or if multiple tiles:
```
[GIS] Found 3 DTM tiles, merging...
[GIS] ✓ Merged 3 tiles into merged_dtm.tif
```

## Testing LiDAR Data

Check `training_dataset.jsonl` for real elevation data:

```json
{
  "gis_data": {
    "elevation_ft": 245.3,
    "slope_percent": 8.2,
    "aspect_degrees": 135,
    "lidar_source": "REAL_DTM"  // ← Confirms real data
  }
}
```

## Troubleshooting

**"No LiDAR DTM files found"**
- Ensure files have "dtm" in filename
- Check files are in `gis_cache/` directory
- Verify .tif extension

**"rasterio not installed"**
```powershell
pip install rasterio
```

**Coordinate mismatch errors**
- Ensure DTM covers Santa Cruz County (36.9°N, 122.0°W)
- Check CRS matches WGS84 or NAD83

**Out of memory errors**
- Download smaller tiles (1-2 sq miles each)
- System will auto-merge them efficiently
