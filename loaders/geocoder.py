"""
Geocoder - Convert addresses to coordinates using Nominatim.

Features:
- Rate limiting (1 request/second per Nominatim policy)
- Caching to avoid repeated lookups
- Retry with exponential backoff
"""

import time
import sqlite3
import json
import hashlib
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

# Rate limiter - tracks last request time
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 1.1  # 1.1 seconds between requests (slightly over 1/sec)


@dataclass
class GeocodedLocation:
    """Result from geocoding an address."""
    address_query: str
    latitude: float
    longitude: float
    display_name: str
    place_type: str
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    raw_response: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "address_query": self.address_query,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "display_name": self.display_name,
            "place_type": self.place_type,
            "bounding_box": self.bounding_box,
        }


class GeocodingCache:
    """SQLite cache for geocoding results."""
    
    def __init__(self, db_path: str = "geocode_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                query_hash TEXT PRIMARY KEY,
                query_text TEXT,
                result_json TEXT,
                created_at REAL
            )
        """)
        conn.commit()
        conn.close()
    
    def _hash_query(self, query: str) -> str:
        return hashlib.md5(query.lower().strip().encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT result_json FROM geocode_cache WHERE query_hash = ?",
            (self._hash_query(query),)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    
    def set(self, query: str, result: Dict):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO geocode_cache 
               (query_hash, query_text, result_json, created_at) 
               VALUES (?, ?, ?, ?)""",
            (self._hash_query(query), query, json.dumps(result), time.time())
        )
        conn.commit()
        conn.close()


class Geocoder:
    """
    Geocoder using OpenStreetMap Nominatim API.
    
    Respects rate limits: max 1 request per second.
    Uses caching to avoid redundant API calls.
    """
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "LandUtilityEngine/1.0 (https://github.com/land-utility)"
    
    def __init__(self, cache_path: str = "geocode_cache.db"):
        self.cache = GeocodingCache(cache_path)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
    
    def _rate_limit(self):
        """Ensure we don't exceed 1 request per second."""
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=10))
    def _make_request(self, params: Dict) -> Dict:
        """Make a rate-limited request with retry."""
        self._rate_limit()
        response = self.session.get(self.NOMINATIM_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def geocode(self, address: str) -> Optional[GeocodedLocation]:
        """
        Convert an address to coordinates.
        
        Args:
            address: Free-form address string, e.g. "123 Main St, Santa Cruz, CA"
            
        Returns:
            GeocodedLocation with lat/lon, or None if not found
        """
        # Check cache first
        cached = self.cache.get(address)
        if cached:
            log.debug(f"Cache hit for: {address}")
            return GeocodedLocation(**cached)
        
        # Make API request
        params = {
            "q": address,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
        }
        
        try:
            results = self._make_request(params)
        except Exception as e:
            log.error(f"Geocoding failed for '{address}': {e}")
            return None
        
        if not results:
            log.warning(f"No results for: {address}")
            return None
        
        result = results[0]
        
        # Parse bounding box if present
        bbox = None
        if "boundingbox" in result:
            bb = result["boundingbox"]
            bbox = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
        
        location = GeocodedLocation(
            address_query=address,
            latitude=float(result["lat"]),
            longitude=float(result["lon"]),
            display_name=result.get("display_name", ""),
            place_type=result.get("type", "unknown"),
            bounding_box=bbox,
            raw_response=result,
        )
        
        # Cache the result
        self.cache.set(address, location.to_dict())
        log.info(f"Geocoded: {address} -> ({location.latitude}, {location.longitude})")
        
        return location
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Convert coordinates to an address.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Display name string, or None if not found
        """
        cache_key = f"reverse:{lat:.6f},{lon:.6f}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached.get("display_name")
        
        params = {
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
        }
        
        url = "https://nominatim.openstreetmap.org/reverse"
        
        try:
            self._rate_limit()
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            log.error(f"Reverse geocoding failed: {e}")
            return None
        
        display_name = result.get("display_name", "")
        self.cache.set(cache_key, {"display_name": display_name})
        
        return display_name


# Singleton instance
_geocoder: Optional[Geocoder] = None

def get_geocoder() -> Geocoder:
    """Get the singleton geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Geocoder()
    return _geocoder
