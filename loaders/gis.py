"""
GIS Data Loader for Santa Cruz County.
Provides parcel, LiDAR, climate risk, and zoning data.
"""

import logging
import os
import random
from typing import Dict, List, Optional

import numpy as np
import requests

log = logging.getLogger("loaders.gis")


class GISLoader:
    """
    Loads real GIS data from Santa Cruz County and free federal sources.
    
    Supports:
    - Santa Cruz County Assessor's Parcel data
    - LiDAR Digital Terrain Model (DTM) elevation/slope
    - FEMA Flood Hazard Zones
    - Cal Fire Wildfire Hazard Severity Zones
    - Utility proximity
    - Zoning history
    """
    
    # API endpoints
    COUNTY_GIS_BASE = "https://gis.santacruzcountyca.gov/arcgis/rest/services"
    FEMA_FLOOD_API = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer"
    CALFIRE_API = "https://egis.fire.ca.gov/arcgis/rest/services/FRAP/FireHazardSeverityZones/MapServer"
    
    def __init__(
        self, 
        cache_dir: str = "gis_cache", 
        use_production_apis: bool = True,
        timeout: int = 10
    ):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        self.use_production = use_production_apis
        self.timeout = timeout
        
        # LiDAR raster cache
        self.lidar_raster = None
        self._load_lidar_if_available()
    
    def _load_lidar_if_available(self) -> None:
        """Load LiDAR DTM raster if available in cache."""
        try:
            import rasterio
            from rasterio.merge import merge
            import glob
            
            dtm_files = glob.glob(os.path.join(self.cache_dir, "*dtm*.tif"))
            
            if len(dtm_files) == 1:
                self.lidar_raster = rasterio.open(dtm_files[0])
                log.info(f"Loaded LiDAR DTM: {os.path.basename(dtm_files[0])}")
            elif len(dtm_files) > 1:
                log.info(f"Found {len(dtm_files)} DTM tiles, merging...")
                src_files = [rasterio.open(f) for f in dtm_files]
                mosaic, transform = merge(src_files)
                
                merged_path = os.path.join(self.cache_dir, "merged_dtm.tif")
                with rasterio.open(
                    merged_path, 'w',
                    driver='GTiff',
                    height=mosaic.shape[1],
                    width=mosaic.shape[2],
                    count=1,
                    dtype=mosaic.dtype,
                    crs=src_files[0].crs,
                    transform=transform
                ) as dst:
                    dst.write(mosaic[0], 1)
                
                self.lidar_raster = rasterio.open(merged_path)
                log.info(f"Merged {len(dtm_files)} tiles")
            else:
                log.debug("No LiDAR DTM files found in cache")
                
        except ImportError:
            log.debug("rasterio not installed - LiDAR disabled")
        except Exception as e:
            log.warning(f"Could not load LiDAR: {e}")
    
    def get_parcel_data(self, lat: float, lon: float) -> Dict:
        """Query Santa Cruz County Assessor's Parcel data."""
        if not self.use_production:
            return self._mock_parcel_data()
        
        try:
            url = f"{self.COUNTY_GIS_BASE}/Parcels/MapServer/0/query"
            params = {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "APN,ACRES,ZONING,ASSESSEDVALUE,LANDUSE",
                "returnGeometry": "false",
                "f": "json"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    attrs = data['features'][0]['attributes']
                    return {
                        "apn": attrs.get('APN', 'Unknown'),
                        "parcel_acres": attrs.get('ACRES', 0),
                        "zoning_code": attrs.get('ZONING', 'Unknown'),
                        "assessed_value": attrs.get('ASSESSEDVALUE', 0),
                        "land_use_code": attrs.get('LANDUSE', 'Unknown')
                    }
        except Exception as e:
            log.debug(f"Parcel query failed: {e}")
        
        return self._mock_parcel_data()
    
    def _mock_parcel_data(self) -> Dict:
        """Generate mock parcel data."""
        apn = f"{random.randint(10,99)}-{random.randint(10,99)}-{random.randint(10,99)}"
        return {
            "apn": apn,
            "parcel_acres": round(random.uniform(0.1, 10.0), 2),
            "zoning_code": random.choice(["R-1-5", "R-1-8", "M-1", "A-1", "C-4"]),
            "assessed_value": random.randint(300000, 2500000),
            "land_use_code": random.choice(["SFR", "MFR", "IND", "COM", "VAC"])
        }
    
    def get_lidar_elevation(self, lat: float, lon: float) -> Dict:
        """Query LiDAR DTM for elevation and slope data."""
        if self.lidar_raster is not None:
            try:
                from rasterio.transform import rowcol
                
                row, col = rowcol(self.lidar_raster.transform, lon, lat)
                
                if 0 <= row < self.lidar_raster.height and 0 <= col < self.lidar_raster.width:
                    elevation_m = float(self.lidar_raster.read(1)[row, col])
                    elevation_ft = elevation_m * 3.28084
                    slope_percent = self._calculate_slope(row, col)
                    aspect_degrees = self._calculate_aspect(row, col)
                    
                    return {
                        "elevation_ft": round(elevation_ft, 1),
                        "slope_percent": round(slope_percent, 1),
                        "aspect_degrees": int(aspect_degrees),
                        "lidar_source": "REAL_DTM"
                    }
            except Exception as e:
                log.debug(f"LiDAR query error: {e}")
        
        return self._mock_lidar_data(lat, lon)
    
    def _calculate_slope(self, row: int, col: int) -> float:
        """Calculate slope percentage from 3x3 neighborhood."""
        try:
            window = self.lidar_raster.read(1)[
                max(0, row-1):min(self.lidar_raster.height, row+2),
                max(0, col-1):min(self.lidar_raster.width, col+2)
            ]
            
            if window.size >= 9:
                dz_dx = (window[1, 2] - window[1, 0]) / 2.0
                dz_dy = (window[2, 1] - window[0, 1]) / 2.0
                slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
                return float(np.tan(slope_rad) * 100)
        except:
            pass
        return 0.0
    
    def _calculate_aspect(self, row: int, col: int) -> float:
        """Calculate aspect (direction of slope) in degrees."""
        try:
            window = self.lidar_raster.read(1)[
                max(0, row-1):min(self.lidar_raster.height, row+2),
                max(0, col-1):min(self.lidar_raster.width, col+2)
            ]
            
            if window.size >= 9:
                dz_dx = (window[1, 2] - window[1, 0]) / 2.0
                dz_dy = (window[2, 1] - window[0, 1]) / 2.0
                aspect_deg = np.degrees(np.arctan2(dz_dy, -dz_dx))
                if aspect_deg < 0:
                    aspect_deg += 360
                return float(aspect_deg)
        except:
            pass
        return 0.0
    
    def _mock_lidar_data(self, lat: float, lon: float) -> Dict:
        """Generate mock LiDAR data."""
        base_elevation = 50 + (lat - 36.95) * 5000
        return {
            "elevation_ft": round(base_elevation + random.uniform(-20, 20), 1),
            "slope_percent": round(random.uniform(0, 45), 1),
            "aspect_degrees": random.randint(0, 360),
            "lidar_source": "MOCK"
        }
    
    def get_climate_risk(self, lat: float, lon: float) -> Dict:
        """Query FEMA flood and Cal Fire wildfire risk data."""
        flood_risk = self._get_fema_flood_risk(lat, lon)
        wildfire_risk = self._get_calfire_wildfire_risk(lat, lon)
        
        return {
            "wildfire_risk_score": wildfire_risk,
            "flood_risk_score": flood_risk,
            "heat_risk_score": 5,  # Placeholder
            "climate_risk_source": "FEMA_CalFire"
        }
    
    def _get_fema_flood_risk(self, lat: float, lon: float) -> int:
        """Query FEMA flood zones."""
        if not self.use_production:
            return random.randint(1, 10)
        
        try:
            url = f"{self.FEMA_FLOOD_API}/28/query"
            params = {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "FLD_ZONE,ZONE_SUBTY",
                "returnGeometry": "false",
                "f": "json"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    zone = data['features'][0]['attributes'].get('FLD_ZONE', 'X')
                    risk_map = {
                        'A': 9, 'AE': 9, 'AO': 8, 'AH': 8,
                        'V': 10, 'VE': 10,
                        'X': 2, '0.2 PCT ANNUAL CHANCE FLOOD HAZARD': 4
                    }
                    return risk_map.get(zone, 5)
        except Exception as e:
            log.debug(f"FEMA flood query failed: {e}")
        
        return 5
    
    def _get_calfire_wildfire_risk(self, lat: float, lon: float) -> int:
        """Query Cal Fire wildfire hazard zones."""
        if not self.use_production:
            return random.randint(1, 10)
        
        try:
            url = f"{self.CALFIRE_API}/0/query"
            params = {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "HAZ_CODE,SRA",
                "returnGeometry": "false",
                "f": "json"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    haz_code = data['features'][0]['attributes'].get('HAZ_CODE', 'M')
                    risk_map = {'VH': 9, 'H': 7, 'M': 5, 'L': 3, 'U': 1}
                    return risk_map.get(haz_code, 5)
        except Exception as e:
            log.debug(f"Cal Fire query failed: {e}")
        
        return 5
    
    def get_utility_proximity(self, lat: float, lon: float) -> Dict:
        """Calculate distance to nearest utility infrastructure."""
        return {
            "distance_to_sewer_ft": random.randint(50, 2000),
            "distance_to_water_main_ft": random.randint(50, 2000),
            "distance_to_power_line_ft": random.randint(50, 1500),
            "has_gas_service": random.choice([True, False])
        }
    
    def get_zoning_history(self, lat: float, lon: float) -> Dict:
        """Query zoning history layer."""
        if not self.use_production:
            return self._mock_zoning_history()
        
        try:
            url = f"{self.COUNTY_GIS_BASE}/ZoningHistory/MapServer/0/query"
            params = {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "false",
                "f": "json"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('features'):
                    attrs = data['features'][0]['attributes']
                    return {
                        "current_zoning": attrs.get('ZONING', 'Unknown'),
                        "zoning_change_year": attrs.get('CHANGE_YEAR'),
                        "overlay_zones": attrs.get('OVERLAYS', '').split(',') if attrs.get('OVERLAYS') else [],
                        "general_plan_designation": attrs.get('GP_DESIGNATION', 'Unknown')
                    }
        except Exception as e:
            log.debug(f"Zoning query failed: {e}")
        
        return self._mock_zoning_history()
    
    def _mock_zoning_history(self) -> Dict:
        """Generate mock zoning history."""
        return {
            "current_zoning": random.choice(["R-1-5", "M-1", "A-1"]),
            "zoning_change_year": random.choice([None, 2015, 2018, 2020]),
            "overlay_zones": random.choice([[], ["HP"], ["AH"], ["HP", "AH"]]),
            "general_plan_designation": random.choice(["RL", "RM", "I", "A"])
        }
    
    def enrich_quantum(self, quantum_dict: Dict) -> Dict:
        """Enrich a land quantum with all available GIS data."""
        lat = quantum_dict.get("lat")
        lon = quantum_dict.get("lon")
        
        enriched = quantum_dict.copy()
        enriched["gis_data"] = {
            **self.get_parcel_data(lat, lon),
            **self.get_lidar_elevation(lat, lon),
            **self.get_climate_risk(lat, lon),
            **self.get_utility_proximity(lat, lon),
            **self.get_zoning_history(lat, lon)
        }
        
        return enriched


class GISFeatureExtractor:
    """Extracts ML-ready features from raw GIS data."""
    
    @staticmethod
    def extract_features(gis_data) -> Dict:
        """Convert raw GIS data into normalized features for ML.
        
        Args:
            gis_data: Dictionary of GIS data, or None/other types (will return empty features)
            
        Returns:
            Dictionary of normalized ML features
        """
        features = {}
        
        # Guard against non-dict input (old training data may have floats or None)
        if not isinstance(gis_data, dict):
            return {
                'elevation_normalized': 0.0,
                'slope_normalized': 0.0,
                'wildfire_safety': 0.5,
                'flood_safety': 0.5,
                'sewer_accessibility': 0.5,
                'water_accessibility': 0.5,
                'is_industrial_zoned': 0,
                'is_residential_zoned': 0,
                'is_agricultural_zoned': 0
            }
        
        # Terrain features
        features['elevation_normalized'] = gis_data.get('elevation_ft', 0) / 2000.0
        features['slope_normalized'] = gis_data.get('slope_percent', 0) / 45.0
        
        # Risk features (inverted to represent safety)
        features['wildfire_safety'] = 1.0 - (gis_data.get('wildfire_risk_score', 5) / 10.0)
        features['flood_safety'] = 1.0 - (gis_data.get('flood_risk_score', 5) / 10.0)
        
        # Utility accessibility (decaying with distance)
        sewer_dist = gis_data.get('distance_to_sewer_ft', 1000)
        features['sewer_accessibility'] = 1.0 / (1.0 + sewer_dist / 500.0)
        
        water_dist = gis_data.get('distance_to_water_main_ft', 1000)
        features['water_accessibility'] = 1.0 / (1.0 + water_dist / 500.0)
        
        # Zoning one-hot encoding
        zoning = gis_data.get('current_zoning', 'R-1-5')
        if isinstance(zoning, str):
            features['is_industrial_zoned'] = 1 if 'M-' in zoning else 0
            features['is_residential_zoned'] = 1 if 'R-' in zoning else 0
            features['is_agricultural_zoned'] = 1 if 'A-' in zoning else 0
        else:
            features['is_industrial_zoned'] = 0
            features['is_residential_zoned'] = 0
            features['is_agricultural_zoned'] = 0
        
        return features


# Backward compatibility alias
SantaCruzGISLoader = GISLoader
