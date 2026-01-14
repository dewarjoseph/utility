# Automated GIS Data Bulk Download Guide

## Quick Start

### List Available Datasets (No Download)
```powershell
python bulk_download_gis.py --list
```

This shows all 162 datasets with ⭐ marking priority layers.

### Download Priority Datasets Only (Recommended First Run)
```powershell
python bulk_download_gis.py --priority-only
```

**Priority datasets include:**
- Parcels
- Zoning
- LiDAR/DTM/DEM
- Flood zones
- Fire hazard zones
- Utility infrastructure

### Download ALL 162 Datasets
```powershell
python bulk_download_gis.py
```

⚠️ **Warning**: This downloads ~5-10 GB of data. Ensure you have sufficient disk space.

### Test Mode (Download First 5 Only)
```powershell
python bulk_download_gis.py --limit 5
```

## How It Works

### 1. Catalog Fetch
- Connects to Santa Cruz County DCAT-US 1.1 feed
- Parses JSON catalog of all 162 datasets
- Extracts download URLs for Shapefiles, GeoTIFFs, CSVs

### 2. Smart Prioritization
- Priority datasets download first
- Alphabetical ordering within each category
- Rate-limited to 1 request/second (respectful to server)

### 3. Organization
Files are saved to:
```
gis_cache/
├── priority/
│   ├── Assessor_Parcels.zip
│   ├── Zoning_Current.zip
│   ├── LiDAR_DTM_2020.tif
│   └── ...
└── general/
    ├── Bus_Stops.zip
    ├── Historic_Districts.zip
    └── ...
```

### 4. Resume Support
- Skips already-downloaded files
- Can be interrupted and restarted safely

## Data Formats

**Shapefiles** (.zip):
- Vector data (parcels, roads, zones)
- Unzip to use in QGIS/ArcGIS

**GeoTIFF** (.tif):
- Raster data (LiDAR, elevation)
- Used directly by `gis_loader.py`

**CSV** (.csv):
- Tabular data
- Can be joined to spatial layers

## Integration with Land Utility Engine

### Automatic LiDAR Detection
Once downloaded, LiDAR files are auto-detected:
```powershell
# After download
streamlit run app.py
```

Console will show:
```
[GIS] ✓ Loaded LiDAR DTM: LiDAR_DTM_2020.tif
```

### Shapefile Processing
To use shapefiles (parcels, zoning, etc.), you'll need to:
1. Unzip the downloaded files
2. Use `geopandas` to query them spatially
3. Integrate into `gis_loader.py`

Example:
```python
import geopandas as gpd

# Load parcel shapefile
parcels = gpd.read_file("gis_cache/priority/Assessor_Parcels.zip")

# Query parcel at specific location
point = gpd.GeoDataFrame(
    geometry=gpd.points_from_xy([lon], [lat]),
    crs="EPSG:4326"
)
result = gpd.sjoin(point, parcels, how="left")
```

## Bandwidth & Time Estimates

**Priority datasets (~20 layers):**
- Size: ~500 MB - 1 GB
- Time: 10-15 minutes

**All datasets (162 layers):**
- Size: ~5-10 GB
- Time: 1-2 hours

## Troubleshooting

**"Connection timeout"**
- County servers may be slow
- Script auto-retries
- Can safely restart - skips completed downloads

**"Disk space error"**
- Check available space: `Get-PSDrive C`
- Download priority-only first
- Delete unnecessary files

**"Invalid JSON"**
- Catalog feed may be temporarily down
- Wait 5 minutes and retry

## Advanced Usage

### Custom Cache Directory
```powershell
python bulk_download_gis.py --cache-dir "D:\GIS_Data"
```

### Download Specific Count
```powershell
python bulk_download_gis.py --limit 50
```

## Next Steps After Download

1. **Verify Downloads**:
```powershell
dir gis_cache\priority
```

2. **Run Daemon**:
```powershell
streamlit run app.py
```

3. **Check Integration**:
Look for `[GIS] ✓ Loaded` messages in console

4. **Train Models**:
```powershell
python train_models.py
```

With full GIS data, expect R² scores of 0.85-0.90+
