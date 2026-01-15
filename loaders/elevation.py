"""
Elevation Loader - Fetch elevation data from USGS.

Uses the USGS Elevation Point Query Service.
"""

import time
import sqlite3
import json
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

# Rate limiter
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 0.2  # 5 requests per second max


@dataclass 
class ElevationResult:
    """Elevation data for a point."""
    latitude: float
    longitude: float
    elevation_meters: float
    data_source: str
    resolution_meters: float


class ElevationCache:
    """SQLite cache for elevation data."""
    
    def __init__(self, db_path: str = "elevation_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS elevation_cache (
                lat_lon_key TEXT PRIMARY KEY,
                elevation_m REAL,
                data_source TEXT,
                resolution_m REAL,
                created_at REAL
            )
        """)
        conn.commit()
        conn.close()
    
    def _make_key(self, lat: float, lon: float) -> str:
        # Round to 5 decimal places (~1m precision)
        return f"{lat:.5f},{lon:.5f}"
    
    def get(self, lat: float, lon: float) -> Optional[ElevationResult]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT elevation_m, data_source, resolution_m FROM elevation_cache WHERE lat_lon_key = ?",
            (self._make_key(lat, lon),)
        ).fetchone()
        conn.close()
        if row:
            return ElevationResult(lat, lon, row[0], row[1], row[2])
        return None
    
    def set(self, result: ElevationResult):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO elevation_cache 
               (lat_lon_key, elevation_m, data_source, resolution_m, created_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (self._make_key(result.latitude, result.longitude),
             result.elevation_meters, result.data_source, 
             result.resolution_meters, time.time())
        )
        conn.commit()
        conn.close()
    
    def get_batch(self, points: List[Tuple[float, float]]) -> Dict[str, ElevationResult]:
        """Get cached elevations for multiple points."""
        conn = sqlite3.connect(self.db_path)
        results = {}
        for lat, lon in points:
            key = self._make_key(lat, lon)
            row = conn.execute(
                "SELECT elevation_m, data_source, resolution_m FROM elevation_cache WHERE lat_lon_key = ?",
                (key,)
            ).fetchone()
            if row:
                results[key] = ElevationResult(lat, lon, row[0], row[1], row[2])
        conn.close()
        return results


class ElevationLoader:
    """
    Fetch elevation data from USGS National Map.
    
    API Documentation:
    https://apps.nationalmap.gov/epqs/
    """
    
    USGS_URL = "https://epqs.nationalmap.gov/v1/json"
    
    def __init__(self, cache_path: str = "elevation_cache.db"):
        self.cache = ElevationCache(cache_path)
        self.session = requests.Session()
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    def get_elevation(self, lat: float, lon: float) -> Optional[ElevationResult]:
        """
        Get elevation for a single point.
        
        Args:
            lat: Latitude (must be in continental US)
            lon: Longitude (must be in continental US)
            
        Returns:
            ElevationResult or None if not available
        """
        # Check cache
        cached = self.cache.get(lat, lon)
        if cached:
            return cached
        
        # Make request
        params = {
            "x": lon,
            "y": lat,
            "units": "Meters",
            "output": "json",
        }
        
        try:
            self._rate_limit()
            response = self.session.get(self.USGS_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log.error(f"Elevation request failed for ({lat}, {lon}): {e}")
            return None
        
        # Parse response
        try:
            elevation = float(data.get("value", -9999))
            if elevation == -9999 or elevation < -1000:
                # USGS returns -9999 or similar for invalid/ocean points
                log.debug(f"No elevation data for ({lat}, {lon})")
                return None
            
            result = ElevationResult(
                latitude=lat,
                longitude=lon,
                elevation_meters=elevation,
                data_source="USGS_3DEP",
                resolution_meters=10.0,  # 3DEP is typically 1/3 arc-second (~10m)
            )
            
            # Cache result
            self.cache.set(result)
            log.debug(f"Elevation at ({lat:.4f}, {lon:.4f}): {elevation:.1f}m")
            
            return result
            
        except (KeyError, ValueError, TypeError) as e:
            log.error(f"Failed to parse elevation response: {e}")
            return None
    
    def get_elevations_batch(self, points: List[Tuple[float, float]]) -> List[Optional[ElevationResult]]:
        """
        Get elevations for multiple points.
        
        Uses caching to minimize API calls.
        """
        # Check cache first
        cached = self.cache.get_batch(points)
        
        results = []
        for lat, lon in points:
            key = f"{lat:.5f},{lon:.5f}"
            if key in cached:
                results.append(cached[key])
            else:
                # Fetch from API
                result = self.get_elevation(lat, lon)
                results.append(result)
        
        return results


# Singleton
_loader: Optional[ElevationLoader] = None

def get_elevation_loader() -> ElevationLoader:
    """Get singleton elevation loader."""
    global _loader
    if _loader is None:
        _loader = ElevationLoader()
    return _loader
