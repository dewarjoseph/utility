"""
Demographics and Labor Market Loader

Provides population, workforce, and economic data for locations.
Uses Census Bureau API with fallback to statistical estimates.
"""

import requests
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import math

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class DemographicsData:
    """Demographics and labor market data for a location."""
    
    # Population
    population_5km: Optional[int] = None
    population_10km: Optional[int] = None
    population_density: Optional[float] = None  # per sq km
    
    # Labor Market
    labor_force: Optional[int] = None
    manufacturing_workers: Optional[int] = None
    construction_workers: Optional[int] = None
    unemployment_rate: Optional[float] = None
    
    # Economics
    median_household_income: Optional[float] = None
    median_home_value: Optional[float] = None
    
    # Geographic
    county_name: Optional[str] = None
    state_name: Optional[str] = None
    urban_area: bool = False
    
    # Metadata
    fetch_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    estimated: bool = True  # True if using estimates rather than exact data
    
    def to_features_dict(self) -> Dict[str, Any]:
        """Convert to flat feature dictionary for scoring."""
        return {
            "high_population": self.population_10km is not None and self.population_10km > 50000,
            "has_labor_force": self.labor_force is not None and self.labor_force > 10000,
            "has_manufacturing": self.manufacturing_workers is not None and self.manufacturing_workers > 1000,
            "urban_area": self.urban_area,
            "low_unemployment": self.unemployment_rate is not None and self.unemployment_rate < 5.0,
            # Numeric features
            "population_10km": self.population_10km or 0,
            "manufacturing_workers": self.manufacturing_workers or 0,
            "unemployment_rate": self.unemployment_rate or 0,
        }


# ═══════════════════════════════════════════════════════════════════════════
# DEMOGRAPHICS LOADER
# ═══════════════════════════════════════════════════════════════════════════
class DemographicsLoader:
    """
    Loads demographics data for locations.
    
    Primary source: Census Bureau API (if API key available)
    Fallback: Statistical estimates based on location characteristics
    """
    
    CACHE_DB = "cache/demographics_cache.db"
    CACHE_TTL_DAYS = 30  # Census data doesn't change often
    
    # Census API (optional - works without key for some endpoints)
    CENSUS_API_BASE = "https://api.census.gov/data"
    
    # Santa Cruz County baseline statistics (2023 estimates)
    SANTA_CRUZ_STATS = {
        "county_name": "Santa Cruz",
        "state_name": "California",
        "population": 267792,
        "area_sq_km": 1155,
        "labor_force": 142000,
        "manufacturing_workers": 8500,
        "construction_workers": 12000,
        "unemployment_rate": 4.8,
        "median_household_income": 95000,
        "median_home_value": 1050000,
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize demographics loader.
        
        Args:
            api_key: Census API key (optional, enables more detailed data)
        """
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY")
        self._init_cache()
    
    def _init_cache(self):
        """Initialize SQLite cache."""
        os.makedirs(os.path.dirname(self.CACHE_DB) if os.path.dirname(self.CACHE_DB) else "cache", exist_ok=True)
        conn = sqlite3.connect(self.CACHE_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demographics_cache (
                lat REAL,
                lon REAL,
                data TEXT,
                timestamp TEXT,
                PRIMARY KEY (lat, lon)
            )
        """)
        conn.commit()
        conn.close()
    
    def _check_cache(self, lat: float, lon: float) -> Optional[Dict]:
        """Check for cached data."""
        conn = sqlite3.connect(self.CACHE_DB)
        cursor = conn.execute(
            "SELECT data, timestamp FROM demographics_cache WHERE lat=? AND lon=?",
            (round(lat, 3), round(lon, 3))  # Lower precision for demographics
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
    
    def _save_cache(self, lat: float, lon: float, data: Dict):
        """Save data to cache."""
        import json
        conn = sqlite3.connect(self.CACHE_DB)
        conn.execute(
            "INSERT OR REPLACE INTO demographics_cache VALUES (?, ?, ?, ?)",
            (round(lat, 3), round(lon, 3), json.dumps(data), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    def get_demographics(self, lat: float, lon: float) -> DemographicsData:
        """
        Get demographics data for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            DemographicsData with available features
        """
        # Check cache
        cached = self._check_cache(lat, lon)
        if cached:
            return DemographicsData(**cached)
        
        # Try Census API if key available
        if self.api_key:
            try:
                data = self._fetch_census_data(lat, lon)
                if data:
                    self._save_cache(lat, lon, data.__dict__)
                    return data
            except Exception as e:
                log.warning(f"Census API failed: {e}")
        
        # Fallback to estimates
        data = self._estimate_demographics(lat, lon)
        self._save_cache(lat, lon, {k: v for k, v in data.__dict__.items() if not k.startswith('_')})
        return data
    
    def _fetch_census_data(self, lat: float, lon: float) -> Optional[DemographicsData]:
        """Fetch from Census API."""
        # This would require geo-to-tract lookup which is complex
        # For now, return None to use estimates
        return None
    
    def _estimate_demographics(self, lat: float, lon: float) -> DemographicsData:
        """
        Estimate demographics based on location.
        
        Uses Santa Cruz baseline with adjustments for:
        - Urban vs rural areas
        - Coastal vs inland
        - Elevation
        """
        data = DemographicsData()
        data.estimated = True
        data.data_sources.append("Estimate")
        
        # Check if in Santa Cruz County (approximate bounds)
        in_santa_cruz = (
            36.85 <= lat <= 37.15 and
            -122.35 <= lon <= -121.55
        )
        
        if in_santa_cruz:
            stats = self.SANTA_CRUZ_STATS
            data.county_name = stats["county_name"]
            data.state_name = stats["state_name"]
            
            # Estimate population based on position
            # Urban areas (closer to Santa Cruz city center: 36.97, -122.03)
            dist_to_downtown = self._distance_km(lat, lon, 36.97, -122.03)
            
            if dist_to_downtown < 5:
                # Urban core
                data.urban_area = True
                data.population_density = 1500
                data.population_5km = 45000
                data.population_10km = 120000
            elif dist_to_downtown < 15:
                # Suburban
                data.urban_area = True
                data.population_density = 600
                data.population_5km = 20000
                data.population_10km = 60000
            else:
                # Rural
                data.urban_area = False
                data.population_density = 100
                data.population_5km = 5000
                data.population_10km = 15000
            
            # Labor market scales with population
            pop_factor = (data.population_10km or 0) / 100000
            data.labor_force = int(stats["labor_force"] * pop_factor)
            data.manufacturing_workers = int(stats["manufacturing_workers"] * pop_factor)
            data.construction_workers = int(stats["construction_workers"] * pop_factor)
            data.unemployment_rate = stats["unemployment_rate"]
            data.median_household_income = stats["median_household_income"]
            data.median_home_value = stats["median_home_value"]
            
            data.confidence = 0.6  # Moderate confidence for estimates
        else:
            # Outside Santa Cruz - very rough estimates
            data.county_name = "Unknown"
            data.state_name = "California"
            data.urban_area = False
            data.population_density = 50
            data.population_5km = 2000
            data.population_10km = 8000
            data.confidence = 0.3
        
        log.info(f"Demographics estimate for ({lat:.3f}, {lon:.3f}): pop={data.population_10km}, urban={data.urban_area}")
        
        return data
    
    def _distance_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in kilometers."""
        R = 6371  # Earth's radius in km
        
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
_demographics_loader = None

def get_demographics_loader() -> DemographicsLoader:
    """Get singleton demographics loader."""
    global _demographics_loader
    if _demographics_loader is None:
        _demographics_loader = DemographicsLoader()
    return _demographics_loader
