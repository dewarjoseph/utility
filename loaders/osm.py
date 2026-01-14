"""
OpenStreetMap data loader via Overpass API.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Optional

log = logging.getLogger("loaders.osm")

OVERPASS_URL = "http://overpass-api.de/api/interpreter"


class OSMLoader:
    """
    Loads geographic features from OpenStreetMap via the Overpass API.
    Provides fallback mock data for offline development.
    """
    
    def __init__(self, timeout: int = 10, use_mock_on_error: bool = True):
        self.timeout = timeout
        self.use_mock_on_error = use_mock_on_error
    
    def fetch_data(
        self, 
        lat: float, 
        lon: float, 
        radius_meters: int = 1000
    ) -> Dict:
        """
        Query Overpass API for features around a point.
        
        Fetches:
        - Roads (highway=*)
        - Water features (natural=water, waterway=*)
        - Industrial zones (landuse=industrial)
        - Residential zones (landuse=residential)
        
        Args:
            lat: Center latitude
            lon: Center longitude
            radius_meters: Search radius in meters
            
        Returns:
            Raw OSM data dict with 'elements' key
        """
        query = f"""
        [out:json];
        (
          way["highway"](around:{radius_meters},{lat},{lon});
          node["natural"="water"](around:{radius_meters},{lat},{lon});
          way["waterway"](around:{radius_meters},{lat},{lon});
          way["landuse"="industrial"](around:{radius_meters},{lat},{lon});
          way["landuse"="residential"](around:{radius_meters},{lat},{lon});
        );
        (._;>;);
        out body;
        """
        
        try:
            log.info(f"Requesting OSM data for {lat}, {lon} (radius={radius_meters}m)")
            req = urllib.request.Request(OVERPASS_URL, data=query.encode('utf-8'))
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                log.info(f"Received {len(data.get('elements', []))} elements")
                return data
        except Exception as e:
            log.warning(f"OSM API error: {e}")
            if self.use_mock_on_error:
                log.info("Falling back to mock data")
                return self._get_mock_data(lat, lon)
            raise
    
    def parse_features(self, data: Dict) -> List[Dict]:
        """
        Parse raw OSM data into simplified feature list.
        
        Returns:
            List of dicts with 'type', 'lat', 'lon' keys
        """
        features = []
        
        for el in data.get("elements", []):
            if "lat" in el and "lon" in el:
                tags = el.get("tags", {})
                
                ftype = None
                if "highway" in tags:
                    ftype = "highway"
                if "waterway" in tags or tags.get("natural") == "water":
                    ftype = "water"
                if tags.get("landuse") == "industrial":
                    ftype = "industrial"
                if tags.get("landuse") == "residential":
                    ftype = "residential"
                
                if ftype:
                    features.append({
                        "type": ftype,
                        "lat": el["lat"],
                        "lon": el["lon"]
                    })
        
        return features
    
    def fetch_and_parse(
        self, 
        lat: float, 
        lon: float, 
        radius_meters: int = 1000
    ) -> List[Dict]:
        """Convenience method: fetch data and parse in one call."""
        raw_data = self.fetch_data(lat, lon, radius_meters)
        return self.parse_features(raw_data)
    
    def _get_mock_data(self, lat: float, lon: float) -> Dict:
        """Generate mock OSM data for testing."""
        mock_elements = []
        
        # A road running East-West
        for i in range(20):
            mock_elements.append({
                "type": "node",
                "lat": lat, 
                "lon": lon + (i * 0.0005),
                "tags": {"highway": "primary"}
            })
        
        # A waterway running North-South
        for i in range(10):
            mock_elements.append({
                "type": "node",
                "lat": lat + (i * 0.0005), 
                "lon": lon + 0.002,
                "tags": {"waterway": "stream"}
            })
            
        # An industrial zone
        mock_elements.append({
            "type": "node",
            "lat": lat + 0.002,
            "lon": lon + 0.002,
            "tags": {"landuse": "industrial"}
        })
        
        return {"elements": mock_elements}


# Backward compatibility functions
def fetch_santa_cruz_data(lat: float, lon: float, radius_meters: int = 1000) -> Dict:
    """Legacy function for backward compatibility."""
    loader = OSMLoader()
    return loader.fetch_data(lat, lon, radius_meters)


def parse_osm_data(data: Dict) -> List[Dict]:
    """Legacy function for backward compatibility."""
    loader = OSMLoader()
    return loader.parse_features(data)
