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
import threading
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np

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
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS osm_cache (
                    query_hash TEXT PRIMARY KEY,
                    result_json TEXT,
                    created_at REAL
                )
            """)
            # Add expiration cleanup
            self._conn.execute("""
                DELETE FROM osm_cache
                WHERE created_at < ?
            """, (time.time() - 30 * 24 * 60 * 60,))  # 30 day expiration
            self._conn.commit()
    
    def _hash_query(self, lat: float, lon: float, radius: int) -> str:
        # Round to 4 decimal places (~10m) for cache key
        key = f"{lat:.4f},{lon:.4f},{radius}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, lat: float, lon: float, radius: int) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT result_json FROM osm_cache WHERE query_hash = ?",
                (self._hash_query(lat, lon, radius),)
            ).fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def set(self, lat: float, lon: float, radius: int, result: Dict):
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO osm_cache
                   (query_hash, result_json, created_at)
                   VALUES (?, ?, ?)""",
                (self._hash_query(lat, lon, radius), json.dumps(result), time.time())
            )
            self._conn.commit()

    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


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

    def _build_bbox_query(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
        """Build comprehensive Overpass query for a bounding box."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        return f"""
        [out:json][timeout:{self.timeout}];
        (
          // Roads and highways
          way["highway"]({bbox});

          // Water features
          way["waterway"]({bbox});
          way["natural"="water"]({bbox});
          node["natural"="water"]({bbox});

          // Land use
          way["landuse"]({bbox});
          relation["landuse"]({bbox});

          // Buildings
          way["building"]({bbox});

          // Amenities and commercial
          node["shop"]({bbox});
          node["amenity"]({bbox});
        );
        out center;
        """
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=15))
    def _make_request(self, query: str) -> Dict:
        """Make a rate-limited request with retry."""
        self._rate_limit()
        try:
            response = self.session.post(
                self.OVERPASS_URL,
                data={"data": query},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ReadTimeout:
            log.warning(f"OSM query timed out after {self.timeout}s")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                log.warning("OSM rate limit exceeded (429), backing off...")
            raise
    
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

    def fetch_raw_bbox(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> Dict:
        """
        Fetch raw OSM data for a bounding box.

        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude

        Returns:
            Raw Overpass API response
        """
        # We'll use the center of the bounding box and a large radius for caching just to reuse the cache logic,
        # but realistically, bounding box queries might not hit the cache perfectly unless we make a new cache mechanism.
        # For this optimization, we will hash the bbox as the cache key instead.
        lat = (min_lat + max_lat) / 2
        lon = (min_lon + max_lon) / 2
        # Use a radius representation for the cache key
        radius = int(self._haversine_distance(min_lat, min_lon, max_lat, max_lon) / 2)

        cached = self.cache.get(lat, lon, radius)
        if cached:
            log.debug(f"Cache hit for OSM bbox at ({lat}, {lon})")
            return cached

        query = self._build_bbox_query(min_lat, min_lon, max_lat, max_lon)
        try:
            data = self._make_request(query)
            self.cache.set(lat, lon, radius, data)
            log.info(f"OSM fetched {len(data.get('elements', []))} elements for bbox")
            return data
        except Exception as e:
            log.error(f"OSM request failed for bbox: {e}")
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
    
    def _batch_haversine_distances(self, lat1: float, lon1: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """Calculate distances between a point and multiple points in meters using vectorization."""
        R = 6371000  # Earth's radius in meters

        phi1 = np.radians(lat1)
        phi2 = np.radians(lats)
        delta_phi = np.radians(lats - lat1)
        delta_lambda = np.radians(lons - lon1)

        a = np.sin(delta_phi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda/2)**2

        # Clip 'a' to [0, 1] to avoid domain errors in sqrt/arcsin due to floating point noise
        a = np.clip(a, 0, 1)

        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

        return R * c

    def fetch_land_use(self, lat: float, lon: float, radius: int = 500) -> LandUseData:
        """
        Fetch and analyze land use data for a location.
        
        Returns structured land use information with distances and classifications.
        """
        raw_data = self.fetch_raw(lat, lon, radius)
        elements = raw_data.get("elements", [])
        return self._process_elements(elements, lat, lon, radius)

    def fetch_land_use_batch(self, points: List[Tuple[float, float]], radius: int = 500) -> List[LandUseData]:
        """
        Fetch and analyze land use data for a batch of locations.
        Calculates a bounding box for the entire batch to make a single OSM API query.
        """
        if not points:
            return []

        # Calculate bounding box with a buffer matching the radius
        # Roughly 1 degree of latitude is 111km. 1 meter is ~0.000009 degrees.
        buffer_deg = (radius / 111000.0) * 1.1 # 10% extra margin

        lats = [p[0] for p in points]
        lons = [p[1] for p in points]

        min_lat = min(lats) - buffer_deg
        max_lat = max(lats) + buffer_deg

        # Adjust longitude buffer based on latitude (longitude degrees shrink near poles)
        avg_lat = sum(lats) / len(lats)
        lon_buffer_deg = buffer_deg / max(0.1, math.cos(math.radians(avg_lat)))

        min_lon = min(lons) - lon_buffer_deg
        max_lon = max(lons) + lon_buffer_deg

        raw_data = self.fetch_raw_bbox(min_lat, min_lon, max_lat, max_lon)
        elements = raw_data.get("elements", [])
        
        results = []
        for lat, lon in points:
            results.append(self._process_elements(elements, lat, lon, radius))

        return results

    def _process_elements(self, elements: List[Dict], lat: float, lon: float, radius: int) -> LandUseData:
        """Process OSM elements and calculate features for a single point."""
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
        
        # Pre-process elements to separate coordinates and tags
        element_data = []
        lats = []
        lons = []

        for el in elements:
            # Get element position
            el_lat = el.get("lat") or el.get("center", {}).get("lat")
            el_lon = el.get("lon") or el.get("center", {}).get("lon")
            
            if el_lat is not None and el_lon is not None:
                element_data.append(el)
                lats.append(el_lat)
                lons.append(el_lon)

        # If no elements, return default
        if not element_data:
             return LandUseData(
                latitude=lat,
                longitude=lon,
                primary_land_use="unknown",
                land_use_confidence=0.0,
                nearest_road_meters=radius,
                road_type="none",
                nearest_water_meters=radius,
                water_type="none",
                has_road_access=False,
                has_water_nearby=False,
                has_buildings=False,
                building_count=0,
                is_industrial=False,
                is_residential=False,
                is_commercial=False,
                is_agricultural=False,
                is_natural=False,
            )

        # Vectorized distance calculation
        distances = self._batch_haversine_distances(
            lat, lon,
            np.array(lats, dtype=np.float64),
            np.array(lons, dtype=np.float64)
        )

        # Process each element with pre-calculated distance
        for i, el in enumerate(element_data):
            tags = el.get("tags", {})
            distance = distances[i]
            
            # Only consider elements within the radius for counts and primary land use
            # but we can record nearest items even slightly outside if needed
            is_within_radius = distance <= radius

            # Check for roads
            if "highway" in tags:
                if distance < nearest_road:
                    nearest_road = float(distance)
                    road_type = tags["highway"]
            
            # Check for water
            if "waterway" in tags or tags.get("natural") == "water":
                if distance < nearest_water:
                    nearest_water = float(distance)
                    water_type = tags.get("waterway") or "water"
            
            if is_within_radius:
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
            nearest_road = float(radius)
        if nearest_water == float('inf'):
            nearest_water = float(radius)
        
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
