"""
Infrastructure Data Loader

Fetches power grid, transportation, and industrial infrastructure data from OSM.
Uses the same Overpass API as the main OSM loader with additional specialized queries.
"""

import requests
import logging
import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import sqlite3
import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class InfrastructureData:
    """Infrastructure features for a location."""
    
    # Power Grid
    power_line_distance_m: Optional[float] = None
    power_line_voltage_kv: Optional[float] = None
    substation_distance_m: Optional[float] = None
    has_power_nearby: bool = False
    
    # Transportation
    rail_distance_m: Optional[float] = None
    rail_type: Optional[str] = None  # main, spur, industrial
    port_distance_km: Optional[float] = None
    port_name: Optional[str] = None
    highway_distance_m: Optional[float] = None
    highway_type: Optional[str] = None  # motorway, trunk, primary
    
    # Industrial
    industrial_area_distance_m: Optional[float] = None
    industrial_type: Optional[str] = None
    
    # Coastal
    coastline_distance_m: Optional[float] = None
    coastal_access: bool = False
    
    # Metadata
    fetch_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, based on data completeness
    
    def to_features_dict(self) -> Dict[str, Any]:
        """Convert to flat feature dictionary for scoring."""
        features = {
            "has_power_nearby": self.has_power_nearby,
            "rail_nearby": self.rail_distance_m is not None and self.rail_distance_m < 2000,
            "port_nearby": self.port_distance_km is not None and self.port_distance_km < 20,
            "highway_nearby": self.highway_distance_m is not None and self.highway_distance_m < 500,
            "coastal_access": self.coastal_access,
            "industrial_adjacent": self.industrial_area_distance_m is not None and self.industrial_area_distance_m < 500,
        }
        
        # Add numeric features for advanced scoring
        if self.power_line_distance_m is not None:
            features["power_line_distance_m"] = self.power_line_distance_m
        if self.rail_distance_m is not None:
            features["rail_distance_m"] = self.rail_distance_m
        if self.coastline_distance_m is not None:
            features["coastline_distance_m"] = self.coastline_distance_m
        if self.port_distance_km is not None:
            features["port_distance_km"] = self.port_distance_km
            
        return features


# ═══════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE LOADER
# ═══════════════════════════════════════════════════════════════════════════
class InfrastructureLoader:
    """
    Fetches infrastructure data from OpenStreetMap.
    
    Uses broader search radius than land use (infrastructure is sparse).
    """
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    CACHE_DB = "cache/infrastructure_cache.db"
    CACHE_TTL_DAYS = 7
    
    def __init__(self):
        self._init_cache()
        self._last_request_time = 0
        self._min_request_interval = 1.5  # seconds between requests
    
    def _init_cache(self):
        """Initialize SQLite cache."""
        os.makedirs(os.path.dirname(self.CACHE_DB), exist_ok=True)
        conn = sqlite3.connect(self.CACHE_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure_cache (
                lat REAL,
                lon REAL,
                radius INTEGER,
                data TEXT,
                timestamp TEXT,
                PRIMARY KEY (lat, lon, radius)
            )
        """)
        conn.commit()
        conn.close()
    
    def _check_cache(self, lat: float, lon: float, radius: int) -> Optional[Dict]:
        """Check for cached data."""
        conn = sqlite3.connect(self.CACHE_DB)
        cursor = conn.execute(
            "SELECT data, timestamp FROM infrastructure_cache WHERE lat=? AND lon=? AND radius=?",
            (round(lat, 4), round(lon, 4), radius)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data, timestamp = row
            cache_time = datetime.fromisoformat(timestamp)
            if datetime.now() - cache_time < timedelta(days=self.CACHE_TTL_DAYS):
                import json
                return json.loads(data)
        return None
    
    def _save_cache(self, lat: float, lon: float, radius: int, data: Dict):
        """Save data to cache."""
        import json
        conn = sqlite3.connect(self.CACHE_DB)
        conn.execute(
            "INSERT OR REPLACE INTO infrastructure_cache VALUES (?, ?, ?, ?, ?)",
            (round(lat, 4), round(lon, 4), radius, json.dumps(data), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _query_overpass(self, query: str) -> Dict:
        """Execute Overpass query with retry."""
        self._rate_limit()
        
        try:
            response = requests.post(
                self.OVERPASS_URL,
                data={"data": query},
                # Increased timeout for complex queries
                timeout=90,
                headers={"User-Agent": "LandUtilityEngine/1.0"}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ReadTimeout:
            log.warning("Overpass query timed out (server side)")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                log.warning("Overpass rate limit exceeded, backing off...")
            raise
    
    def fetch_infrastructure(
        self, 
        lat: float, 
        lon: float, 
        radius: int = 5000  # 5km default - infrastructure is sparse
    ) -> InfrastructureData:
        """
        Fetch all infrastructure data for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters (default 5km)
            
        Returns:
            InfrastructureData with all available features
        """
        # Check cache first
        cached = self._check_cache(lat, lon, radius)
        if cached:
            log.debug(f"Infrastructure cache hit for ({lat}, {lon})")
            return self._parse_cached(cached)
        
        # Build comprehensive query
        query = self._build_query(lat, lon, radius)
        
        try:
            result = self._query_overpass(query)
            self._save_cache(lat, lon, radius, result)
            return self._parse_result(lat, lon, result)
        except Exception as e:
            log.error(f"Infrastructure fetch failed: {e}")
            return InfrastructureData()
    
    def _build_query(self, lat: float, lon: float, radius: int) -> str:
        """Build Overpass query for infrastructure."""
        return f"""
        [out:json][timeout:45];
        (
          // Power infrastructure
          way["power"="line"](around:{radius},{lat},{lon});
          node["power"="substation"](around:{radius},{lat},{lon});
          way["power"="substation"](around:{radius},{lat},{lon});
          
          // Rail
          way["railway"="rail"](around:{radius},{lat},{lon});
          way["railway"="industrial"](around:{radius},{lat},{lon});
          
          // Ports and harbors (larger radius)
          node["harbour"="yes"](around:{radius*3},{lat},{lon});
          way["harbour"="yes"](around:{radius*3},{lat},{lon});
          node["industrial"="port"](around:{radius*3},{lat},{lon});
          
          // Major highways
          way["highway"="motorway"](around:{radius},{lat},{lon});
          way["highway"="trunk"](around:{radius},{lat},{lon});
          way["highway"="primary"](around:{radius},{lat},{lon});
          
          // Industrial areas
          way["landuse"="industrial"](around:{radius},{lat},{lon});
          relation["landuse"="industrial"](around:{radius},{lat},{lon});
          
          // Coastline
          way["natural"="coastline"](around:{radius},{lat},{lon});
        );
        out center;
        """
    
    def _parse_cached(self, cached: Dict) -> InfrastructureData:
        """Parse cached result."""
        # If cached is already parsed, return directly
        if isinstance(cached, dict) and "elements" in cached:
            return self._parse_result(0, 0, cached)  # lat/lon not needed for distance recalc
        return InfrastructureData()
    
    def _parse_result(self, lat: float, lon: float, result: Dict) -> InfrastructureData:
        """Parse Overpass API result into InfrastructureData."""
        data = InfrastructureData()
        elements = result.get("elements", [])
        
        if not elements:
            return data
        
        data.data_sources.append("OSM")
        
        power_lines = []
        substations = []
        rails = []
        ports = []
        highways = []
        industrial = []
        coastlines = []
        
        for el in elements:
            tags = el.get("tags", {})
            el_lat, el_lon = self._get_element_center(el)
            
            if el_lat is None:
                continue
            
            dist = self._haversine(lat, lon, el_lat, el_lon)
            
            if tags.get("power") == "line":
                voltage = self._parse_voltage(tags.get("voltage", ""))
                power_lines.append((dist, voltage))
            elif tags.get("power") == "substation":
                substations.append(dist)
            elif tags.get("railway") in ["rail", "industrial"]:
                rails.append((dist, tags.get("railway")))
            elif tags.get("harbour") == "yes" or tags.get("industrial") == "port":
                ports.append((dist, tags.get("name", "Unknown Port")))
            elif tags.get("highway") in ["motorway", "trunk", "primary"]:
                highways.append((dist, tags.get("highway")))
            elif tags.get("landuse") == "industrial":
                industrial.append((dist, tags.get("industrial", "general")))
            elif tags.get("natural") == "coastline":
                coastlines.append(dist)
        
        # Find nearest of each type
        if power_lines:
            nearest = min(power_lines, key=lambda x: x[0])
            data.power_line_distance_m = nearest[0]
            data.power_line_voltage_kv = nearest[1]
            data.has_power_nearby = nearest[0] < 2000
        
        if substations:
            data.substation_distance_m = min(substations)
        
        if rails:
            nearest = min(rails, key=lambda x: x[0])
            data.rail_distance_m = nearest[0]
            data.rail_type = nearest[1]
        
        if ports:
            nearest = min(ports, key=lambda x: x[0])
            data.port_distance_km = nearest[0] / 1000
            data.port_name = nearest[1]
        
        if highways:
            nearest = min(highways, key=lambda x: x[0])
            data.highway_distance_m = nearest[0]
            data.highway_type = nearest[1]
        
        if industrial:
            nearest = min(industrial, key=lambda x: x[0])
            data.industrial_area_distance_m = nearest[0]
            data.industrial_type = nearest[1]
        
        if coastlines:
            data.coastline_distance_m = min(coastlines)
            data.coastal_access = data.coastline_distance_m < 5000
        
        # Calculate confidence based on data completeness
        filled_fields = sum([
            data.power_line_distance_m is not None,
            data.rail_distance_m is not None,
            data.highway_distance_m is not None,
            data.coastline_distance_m is not None,
        ])
        data.confidence = filled_fields / 4.0
        
        log.info(f"Infrastructure: power={data.power_line_distance_m}m, rail={data.rail_distance_m}m, coast={data.coastline_distance_m}m")
        
        return data
    
    def _get_element_center(self, el: Dict) -> Tuple[Optional[float], Optional[float]]:
        """Get center coordinates of an OSM element."""
        if el.get("type") == "node":
            return el.get("lat"), el.get("lon")
        elif "center" in el:
            return el["center"].get("lat"), el["center"].get("lon")
        return None, None
    
    def _parse_voltage(self, voltage_str: str) -> Optional[float]:
        """Parse voltage string to kV float."""
        if not voltage_str:
            return None
        try:
            # Handle "115000" or "115 kV" formats
            v = voltage_str.replace(" ", "").lower().replace("kv", "").replace("v", "")
            val = float(v)
            if val > 1000:  # Assume volts, convert to kV
                return val / 1000
            return val
        except:
            return None
    
    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════
_infrastructure_loader = None

def get_infrastructure_loader() -> InfrastructureLoader:
    """Get singleton infrastructure loader."""
    global _infrastructure_loader
    if _infrastructure_loader is None:
        _infrastructure_loader = InfrastructureLoader()
    return _infrastructure_loader
