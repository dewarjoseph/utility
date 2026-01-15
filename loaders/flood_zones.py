"""
Flood Zones Loader - Fetch FEMA flood hazard data.

Uses FEMA's National Flood Hazard Layer (NFHL) via ArcGIS REST API.
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
_MIN_REQUEST_INTERVAL = 0.5  # 2 requests per second


@dataclass
class FloodZoneResult:
    """FEMA flood zone information for a point."""
    latitude: float
    longitude: float
    flood_zone: str            # Zone designation: A, AE, AH, AO, VE, X, D
    zone_description: str      # Human-readable description
    flood_risk_level: str      # "high", "moderate", "low", "undetermined"
    base_flood_elevation: Optional[float] = None  # BFE in feet if available
    panel_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "flood_zone": self.flood_zone,
            "zone_description": self.zone_description,
            "flood_risk_level": self.flood_risk_level,
            "base_flood_elevation": self.base_flood_elevation,
            "panel_id": self.panel_id,
        }


# FEMA Zone descriptions and risk levels
ZONE_INFO = {
    "A": ("High-risk area, no BFE determined", "high"),
    "AE": ("High-risk area with BFE", "high"),
    "AH": ("High-risk shallow flooding area", "high"),
    "AO": ("High-risk sheet flow area", "high"),
    "AR": ("Area with temporary increased flood risk", "high"),
    "A99": ("High-risk area protected by levee under construction", "high"),
    "V": ("Coastal high-risk area, no BFE", "high"),
    "VE": ("Coastal high-risk area with BFE", "high"),
    "X": ("Moderate to low risk area", "low"),
    "B": ("Moderate flood risk (older designation)", "moderate"),
    "C": ("Minimal flood risk (older designation)", "low"),
    "D": ("Undetermined risk - possible flooding", "undetermined"),
}


class FloodZoneCache:
    """SQLite cache for flood zone data."""
    
    def __init__(self, db_path: str = "flood_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flood_cache (
                lat_lon_key TEXT PRIMARY KEY,
                result_json TEXT,
                created_at REAL
            )
        """)
        conn.commit()
        conn.close()
    
    def _make_key(self, lat: float, lon: float) -> str:
        return f"{lat:.5f},{lon:.5f}"
    
    def get(self, lat: float, lon: float) -> Optional[FloodZoneResult]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT result_json FROM flood_cache WHERE lat_lon_key = ?",
            (self._make_key(lat, lon),)
        ).fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            return FloodZoneResult(**data)
        return None
    
    def set(self, result: FloodZoneResult):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO flood_cache 
               (lat_lon_key, result_json, created_at) 
               VALUES (?, ?, ?)""",
            (self._make_key(result.latitude, result.longitude),
             json.dumps(result.to_dict()), time.time())
        )
        conn.commit()
        conn.close()


class FloodZoneLoader:
    """
    Fetch FEMA flood zone data from the National Flood Hazard Layer.
    
    API: FEMA Map Service Center / NFHL ArcGIS REST
    Coverage: United States only
    """
    
    # FEMA NFHL MapServer endpoint - Layer 0 is Flood Hazard Zones
    # See: https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer
    NFHL_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/0/query"
    
    def __init__(self, cache_path: str = "flood_cache.db"):
        self.cache = FloodZoneCache(cache_path)
        self.session = requests.Session()
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    def get_flood_zone(self, lat: float, lon: float) -> Optional[FloodZoneResult]:
        """
        Get flood zone for a point.
        
        Args:
            lat: Latitude (must be in United States)
            lon: Longitude (must be in United States)
            
        Returns:
            FloodZoneResult or None if not in FEMA coverage
        """
        # Check cache
        cached = self.cache.get(lat, lon)
        if cached:
            return cached
        
        # Query FEMA service
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE,DFIRM_ID",
            "returnGeometry": "false",
            "f": "json",
        }
        
        try:
            self._rate_limit()
            response = self.session.get(self.NFHL_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log.error(f"FEMA request failed for ({lat}, {lon}): {e}")
            return None
        
        # Parse response
        features = data.get("features", [])
        
        if not features:
            # No flood zone data - might be outside coverage or in Zone X
            result = FloodZoneResult(
                latitude=lat,
                longitude=lon,
                flood_zone="X",
                zone_description="Minimal flood risk area (or outside FEMA coverage)",
                flood_risk_level="low",
            )
            self.cache.set(result)
            return result
        
        # Get first matching zone
        attrs = features[0].get("attributes", {})
        zone = attrs.get("FLD_ZONE", "X")
        
        # Look up zone info
        zone_desc, risk_level = ZONE_INFO.get(zone, ("Unknown zone", "undetermined"))
        
        # Get BFE if available
        bfe = attrs.get("STATIC_BFE")
        if bfe and bfe != -9999:
            bfe = float(bfe)
        else:
            bfe = None
        
        result = FloodZoneResult(
            latitude=lat,
            longitude=lon,
            flood_zone=zone,
            zone_description=zone_desc,
            flood_risk_level=risk_level,
            base_flood_elevation=bfe,
            panel_id=attrs.get("DFIRM_ID"),
        )
        
        self.cache.set(result)
        log.debug(f"Flood zone at ({lat:.4f}, {lon:.4f}): {zone} ({risk_level} risk)")
        
        return result


# Singleton
_loader: Optional[FloodZoneLoader] = None

def get_flood_loader() -> FloodZoneLoader:
    """Get singleton flood zone loader."""
    global _loader
    if _loader is None:
        _loader = FloodZoneLoader()
    return _loader
