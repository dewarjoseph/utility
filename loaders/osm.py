"""
OpenStreetMap Data Loader via Overpass API.

Enhanced with:
- Rate limiting (per Overpass API guidelines)
- Caching to avoid redundant requests
- Retry with exponential backoff
- Better land use classification
"""

import time
import sqlite3
import json
import hashlib
import math
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

# Rate limiter - Overpass is generous but we should be respectful
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 2.0  # 2 seconds between requests


@dataclass
class LandUseData:
    """Land use and infrastructure data for a location."""
    latitude: float
    longitude: float
    
    # Land use classification
    primary_land_use: str       # "industrial", "residential", "commercial", etc.
    land_use_confidence: float  # 0-1 confidence score
    
    # Infrastructure proximity (in meters)
    nearest_road_meters: float
    road_type: str              # "highway", "primary", "secondary", "residential"
    nearest_water_meters: float
    water_type: str             # "river", "stream", "lake", "coastline"
    
    # Features present
    has_road_access: bool
    has_water_nearby: bool
    has_buildings: bool
    building_count: int
    
    # Zoning indicators
    is_industrial: bool
    is_residential: bool
    is_commercial: bool
    is_agricultural: bool
    is_natural: bool
    
    def to_dict(self) -> Dict:
        return asdict(self)


class OSMCache:
    """SQLite cache for Overpass API results."""
    
    def __init__(self, db_path: str = "osm_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS osm_cache (
                query_hash TEXT PRIMARY KEY,
                result_json TEXT,
                created_at REAL
            )
        """)
        # Add expiration cleanup
        conn.execute("""
            DELETE FROM osm_cache 
            WHERE created_at < ?
        """, (time.time() - 30 * 24 * 60 * 60,))  # 30 day expiration
        conn.commit()
        conn.close()
    
    def _hash_query(self, lat: float, lon: float, radius: int) -> str:
        # Round to 4 decimal places (~10m) for cache key
        key = f"{lat:.4f},{lon:.4f},{radius}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, lat: float, lon: float, radius: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT result_json FROM osm_cache WHERE query_hash = ?",
            (self._hash_query(lat, lon, radius),)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    
    def set(self, lat: float, lon: float, radius: int, result: Dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO osm_cache 
               (query_hash, result_json, created_at) 
               VALUES (?, ?, ?)""",
            (self._hash_query(lat, lon, radius), json.dumps(result), time.time())
        )
        conn.commit()
        conn.close()


class OSMLoader:
    """
    Enhanced OpenStreetMap data loader via Overpass API.
    
    Fetches:
    - Roads and highways
    - Water features (rivers, streams, lakes)
    - Land use zones (industrial, residential, commercial)
    - Buildings
    """
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    def __init__(self, cache_path: str = "osm_cache.db", timeout: int = 30):
        self.cache = OSMCache(cache_path)
        self.timeout = timeout
        self.session = requests.Session()
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()
    
    def _build_query(self, lat: float, lon: float, radius: int) -> str:
        """Build comprehensive Overpass query."""
        return f"""
        [out:json][timeout:{self.timeout}];
        (
          // Roads and highways
          way["highway"](around:{radius},{lat},{lon});
          
          // Water features
          way["waterway"](around:{radius},{lat},{lon});
          way["natural"="water"](around:{radius},{lat},{lon});
          node["natural"="water"](around:{radius},{lat},{lon});
          
          // Land use
          way["landuse"](around:{radius},{lat},{lon});
          relation["landuse"](around:{radius},{lat},{lon});
          
          // Buildings
          way["building"](around:{radius},{lat},{lon});
          
          // Amenities and commercial
          node["shop"](around:{radius},{lat},{lon});
          node["amenity"](around:{radius},{lat},{lon});
        );
        out center;
        """
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=15))
    def _make_request(self, query: str) -> Dict:
        """Make a rate-limited request with retry."""
        self._rate_limit()
        response = self.session.post(
            self.OVERPASS_URL,
            data={"data": query},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def fetch_raw(self, lat: float, lon: float, radius: int = 500) -> Dict:
        """
        Fetch raw OSM data for a location.
        
        Args:
            lat: Center latitude
            lon: Center longitude
            radius: Search radius in meters
            
        Returns:
            Raw Overpass API response
        """
        # Check cache
        cached = self.cache.get(lat, lon, radius)
        if cached:
            log.debug(f"Cache hit for OSM at ({lat}, {lon})")
            return cached
        
        # Build and execute query
        query = self._build_query(lat, lon, radius)
        
        try:
            data = self._make_request(query)
            self.cache.set(lat, lon, radius, data)
            log.info(f"OSM fetched {len(data.get('elements', []))} elements at ({lat:.4f}, {lon:.4f})")
            return data
            
        except Exception as e:
            log.error(f"OSM request failed: {e}")
            return {"elements": []}
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def fetch_land_use(self, lat: float, lon: float, radius: int = 500) -> LandUseData:
        """
        Fetch and analyze land use data for a location.
        
        Returns structured land use information with distances and classifications.
        """
        raw_data = self.fetch_raw(lat, lon, radius)
        elements = raw_data.get("elements", [])
        
        # Initialize tracking variables
        nearest_road = float('inf')
        road_type = "none"
        nearest_water = float('inf')
        water_type = "none"
        building_count = 0
        land_uses = {
            "industrial": 0,
            "residential": 0,
            "commercial": 0,
            "agricultural": 0,
            "natural": 0,
        }
        
        # Process each element
        for el in elements:
            tags = el.get("tags", {})
            
            # Get element position
            el_lat = el.get("lat") or el.get("center", {}).get("lat")
            el_lon = el.get("lon") or el.get("center", {}).get("lon")
            
            if el_lat is None or el_lon is None:
                continue
            
            distance = self._haversine_distance(lat, lon, el_lat, el_lon)
            
            # Check for roads
            if "highway" in tags:
                if distance < nearest_road:
                    nearest_road = distance
                    road_type = tags["highway"]
            
            # Check for water
            if "waterway" in tags or tags.get("natural") == "water":
                if distance < nearest_water:
                    nearest_water = distance
                    water_type = tags.get("waterway") or "water"
            
            # Check for buildings
            if "building" in tags:
                building_count += 1
            
            # Check land use
            landuse = tags.get("landuse", "")
            if landuse in ["industrial", "quarry", "port"]:
                land_uses["industrial"] += 1
            elif landuse in ["residential"]:
                land_uses["residential"] += 1
            elif landuse in ["commercial", "retail"]:
                land_uses["commercial"] += 1
            elif landuse in ["farmland", "farm", "orchard", "vineyard"]:
                land_uses["agricultural"] += 1
            elif landuse in ["forest", "meadow", "grass", "nature_reserve"]:
                land_uses["natural"] += 1
            
            # Commercial indicators
            if "shop" in tags or tags.get("amenity") in ["restaurant", "cafe", "bank"]:
                land_uses["commercial"] += 1
        
        # Determine primary land use
        if sum(land_uses.values()) > 0:
            primary_use = max(land_uses, key=land_uses.get)
            confidence = land_uses[primary_use] / max(sum(land_uses.values()), 1)
        else:
            primary_use = "unknown"
            confidence = 0.0
        
        # Cap distances at radius if nothing found
        if nearest_road == float('inf'):
            nearest_road = radius
        if nearest_water == float('inf'):
            nearest_water = radius
        
        return LandUseData(
            latitude=lat,
            longitude=lon,
            primary_land_use=primary_use,
            land_use_confidence=confidence,
            nearest_road_meters=nearest_road,
            road_type=road_type,
            nearest_water_meters=nearest_water,
            water_type=water_type,
            has_road_access=nearest_road < 100,  # Within 100m
            has_water_nearby=nearest_water < 500,  # Within 500m
            has_buildings=building_count > 0,
            building_count=building_count,
            is_industrial=land_uses["industrial"] > 0,
            is_residential=land_uses["residential"] > 0,
            is_commercial=land_uses["commercial"] > 0,
            is_agricultural=land_uses["agricultural"] > 0,
            is_natural=land_uses["natural"] > 0,
        )


# Singleton
_loader: Optional[OSMLoader] = None

def get_osm_loader() -> OSMLoader:
    """Get singleton OSM loader."""
    global _loader
    if _loader is None:
        _loader = OSMLoader()
    return _loader


# Legacy compatibility
def fetch_santa_cruz_data(lat: float, lon: float, radius_meters: int = 1000) -> Dict:
    """Legacy function for backward compatibility."""
    return get_osm_loader().fetch_raw(lat, lon, radius_meters)


def parse_osm_data(data: Dict) -> List[Dict]:
    """Legacy function for backward compatibility."""
    features = []
    for el in data.get("elements", []):
        if "lat" in el and "lon" in el:
            tags = el.get("tags", {})
            ftype = None
            if "highway" in tags:
                ftype = "highway"
            elif "waterway" in tags or tags.get("natural") == "water":
                ftype = "water"
            elif tags.get("landuse") == "industrial":
                ftype = "industrial"
            elif tags.get("landuse") == "residential":
                ftype = "residential"
            if ftype:
                features.append({"type": ftype, "lat": el["lat"], "lon": el["lon"]})
    return features
