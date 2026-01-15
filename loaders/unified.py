"""
Unified Data Fetcher - Combines all data sources into one interface.

Fetches:
- Land use from OpenStreetMap
- Elevation from USGS
- Flood zones from FEMA
- Geocoding from Nominatim
- Infrastructure (power, rail, ports, coast) from OSM
- Demographics (population, labor) from Census/estimates

All with proper rate limiting, caching, and error handling.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from loaders.osm import get_osm_loader, LandUseData
from loaders.elevation import get_elevation_loader, ElevationResult
from loaders.flood_zones import get_flood_loader, FloodZoneResult
from loaders.geocoder import get_geocoder, GeocodedLocation

log = logging.getLogger(__name__)


@dataclass
class LocationData:
    """
    Complete data for a geographic location.
    
    Combines data from multiple sources into a single structure
    for use in utility scoring.
    """
    latitude: float
    longitude: float
    
    # Land use (from OSM)
    primary_land_use: str = "unknown"
    is_industrial: bool = False
    is_residential: bool = False
    is_commercial: bool = False
    is_agricultural: bool = False
    is_natural: bool = False
    
    # Basic Infrastructure (from OSM)
    has_road_access: bool = False
    road_distance_meters: float = 1000.0
    road_type: str = "none"
    has_water_nearby: bool = False
    water_distance_meters: float = 1000.0
    water_type: str = "none"
    building_count: int = 0
    
    # Power Grid (from infrastructure loader)
    has_power_nearby: bool = False
    power_line_distance_m: Optional[float] = None
    substation_distance_m: Optional[float] = None
    
    # Transportation (from infrastructure loader)
    rail_nearby: bool = False
    rail_distance_m: Optional[float] = None
    port_nearby: bool = False
    port_distance_km: Optional[float] = None
    highway_nearby: bool = False
    highway_distance_m: Optional[float] = None
    
    # Coastal (from infrastructure loader)
    coastal_access: bool = False
    coastline_distance_m: Optional[float] = None
    
    # Elevation (from USGS)
    elevation_meters: Optional[float] = None
    is_high_elevation: bool = False  # Above 500m
    is_low_elevation: bool = False   # Below 10m (flood risk)
    
    # Flood risk (from FEMA)
    flood_zone: str = "X"
    flood_risk_level: str = "low"  # "high", "moderate", "low", "undetermined"
    is_flood_risk: bool = False
    
    # Demographics (from demographics loader)
    population_10km: Optional[int] = None
    urban_area: bool = False
    has_manufacturing: bool = False
    manufacturing_workers: Optional[int] = None
    unemployment_rate: Optional[float] = None
    
    # Environmental (future)
    protected_habitat: bool = False
    
    # Metadata
    data_complete: bool = False
    data_sources: List[str] = field(default_factory=list)
    fetch_errors: list = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        return result
    
    def to_features_dict(self) -> Dict[str, Any]:
        """Convert to feature dictionary for scoring."""
        return {
            # Basic infrastructure
            "has_water": self.has_water_nearby,
            "has_road": self.has_road_access,
            
            # Land use
            "is_industrial": self.is_industrial,
            "is_residential": self.is_residential,
            "is_commercial": self.is_commercial,
            "is_agricultural": self.is_agricultural,
            
            # Elevation
            "high_elevation": self.is_high_elevation,
            "low_elevation": self.is_low_elevation,
            "flood_risk": self.is_flood_risk,
            
            # Power & Transportation
            "has_power_nearby": self.has_power_nearby,
            "rail_nearby": self.rail_nearby,
            "port_nearby": self.port_nearby,
            "highway_nearby": self.highway_nearby,
            "coastal_access": self.coastal_access,
            
            # Demographics
            "urban_area": self.urban_area,
            "has_manufacturing": self.has_manufacturing,
            "low_unemployment": self.unemployment_rate is not None and self.unemployment_rate < 5.0,
            
            # Environmental
            "protected_habitat": self.protected_habitat,
            
            # Computed / distances for advanced scoring
            "near_water": self.water_distance_meters < 200,
            "near_road": self.road_distance_meters < 50,
            "has_buildings": self.building_count > 0,
            "building_density": min(self.building_count / 10, 1.0),
            "power_line_distance_m": self.power_line_distance_m,
            "rail_distance_m": self.rail_distance_m,
            "coastline_distance_m": self.coastline_distance_m,
            "port_distance_km": self.port_distance_km,
            "manufacturing_workers": self.manufacturing_workers or 0,
            "population_10km": self.population_10km or 0,
        }


class UnifiedDataFetcher:
    """
    Combines all data sources into a single interface.
    
    Usage:
        fetcher = UnifiedDataFetcher()
        data = fetcher.fetch_all(36.9741, -122.0308)
        features = data.to_features_dict()
    """
    
    def __init__(self):
        self.osm = get_osm_loader()
        self.elevation = get_elevation_loader()
        self.flood = get_flood_loader()
        self.geocoder = get_geocoder()
        
        # Lazy-loaded advanced loaders (may not be available)
        self._infrastructure = None
        self._demographics = None
    
    @property
    def infrastructure(self):
        """Lazy-load infrastructure loader."""
        if self._infrastructure is None:
            try:
                from loaders.infrastructure import get_infrastructure_loader
                self._infrastructure = get_infrastructure_loader()
            except ImportError:
                log.warning("Infrastructure loader not available")
        return self._infrastructure
    
    @property
    def demographics(self):
        """Lazy-load demographics loader."""
        if self._demographics is None:
            try:
                from loaders.demographics import get_demographics_loader
                self._demographics = get_demographics_loader()
            except ImportError:
                log.warning("Demographics loader not available")
        return self._demographics
    
    def fetch_all(
        self, 
        lat: float, 
        lon: float, 
        osm_radius: int = 500,
        parallel: bool = True
    ) -> LocationData:
        """
        Fetch data from all sources for a location.
        
        Args:
            lat: Latitude
            lon: Longitude
            osm_radius: Radius for OSM queries in meters
            parallel: If True, fetch from sources in parallel
            
        Returns:
            LocationData with all available information
        """
        result = LocationData(latitude=lat, longitude=lon)
        errors = []
        
        if parallel:
            result = self._fetch_parallel(lat, lon, osm_radius, result, errors)
        else:
            result = self._fetch_sequential(lat, lon, osm_radius, result, errors)
        
        result.fetch_errors = errors
        result.data_complete = len(errors) == 0
        
        return result
    
    def _fetch_parallel(
        self, 
        lat: float, 
        lon: float, 
        osm_radius: int,
        result: LocationData,
        errors: list
    ) -> LocationData:
        """Fetch from all sources in parallel."""
        
        def fetch_osm():
            return self.osm.fetch_land_use(lat, lon, osm_radius)
        
        def fetch_elevation():
            return self.elevation.get_elevation(lat, lon)
        
        def fetch_flood():
            return self.flood.get_flood_zone(lat, lon)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(fetch_osm): "osm",
                executor.submit(fetch_elevation): "elevation",
                executor.submit(fetch_flood): "flood",
            }
            
            for future in as_completed(futures, timeout=60):
                source = futures[future]
                try:
                    data = future.result()
                    result = self._apply_data(result, source, data)
                except Exception as e:
                    log.error(f"Error fetching {source}: {e}")
                    errors.append(f"{source}: {str(e)}")
        
        return result
    
    def _fetch_sequential(
        self, 
        lat: float, 
        lon: float, 
        osm_radius: int,
        result: LocationData,
        errors: list
    ) -> LocationData:
        """Fetch from sources sequentially (OSM + USGS only, FEMA disabled)."""
        
        # OSM - primary source for land use, roads, water
        try:
            osm_data = self.osm.fetch_land_use(lat, lon, osm_radius)
            result = self._apply_data(result, "osm", osm_data)
        except Exception as e:
            errors.append(f"osm: {str(e)}")
        
        # Elevation - USGS
        try:
            elev_data = self.elevation.get_elevation(lat, lon)
            result = self._apply_data(result, "elevation", elev_data)
            
            # Infer flood risk from elevation if FEMA unavailable
            if elev_data and elev_data.elevation_meters < 5:
                result.flood_risk_level = "high"
                result.is_flood_risk = True
            elif elev_data and elev_data.elevation_meters < 15:
                result.flood_risk_level = "moderate"
        except Exception as e:
            errors.append(f"elevation: {str(e)}")
        
        # FEMA - DISABLED due to unreliable API (404 errors)
        # Flood risk is inferred from elevation instead
        
        # Infrastructure - power, rail, ports, coast
        if self.infrastructure:
            try:
                infra_data = self.infrastructure.fetch_infrastructure(lat, lon)
                result = self._apply_data(result, "infrastructure", infra_data)
                result.data_sources.append("OSM-Infra")
            except Exception as e:
                log.warning(f"Infrastructure fetch failed: {e}")
                errors.append(f"infrastructure: {str(e)}")
        
        # Demographics - population, labor market
        if self.demographics:
            try:
                demo_data = self.demographics.get_demographics(lat, lon)
                result = self._apply_data(result, "demographics", demo_data)
                if demo_data.estimated:
                    result.data_sources.append("Demographics-Est")
                else:
                    result.data_sources.append("Census")
            except Exception as e:
                log.warning(f"Demographics fetch failed: {e}")
                errors.append(f"demographics: {str(e)}")
        
        return result
    
    def _apply_data(self, result: LocationData, source: str, data: Any) -> LocationData:
        """Apply data from a source to the result."""
        
        if source == "osm" and isinstance(data, LandUseData):
            result.primary_land_use = data.primary_land_use
            result.is_industrial = data.is_industrial
            result.is_residential = data.is_residential
            result.is_commercial = data.is_commercial
            result.is_agricultural = data.is_agricultural
            result.is_natural = data.is_natural
            result.has_road_access = data.has_road_access
            result.road_distance_meters = data.nearest_road_meters
            result.road_type = data.road_type
            result.has_water_nearby = data.has_water_nearby
            result.water_distance_meters = data.nearest_water_meters
            result.water_type = data.water_type
            result.building_count = data.building_count
            result.data_sources.append("OSM")
            
        elif source == "elevation" and isinstance(data, ElevationResult):
            result.elevation_meters = data.elevation_meters
            result.is_high_elevation = data.elevation_meters > 500
            result.is_low_elevation = data.elevation_meters < 10
            result.data_sources.append("USGS")
            
        elif source == "flood" and isinstance(data, FloodZoneResult):
            result.flood_zone = data.flood_zone
            result.flood_risk_level = data.flood_risk_level
            result.is_flood_risk = data.flood_risk_level == "high"
            result.data_sources.append("FEMA")
        
        elif source == "infrastructure" and data is not None:
            # From InfrastructureData
            result.has_power_nearby = data.has_power_nearby
            result.power_line_distance_m = data.power_line_distance_m
            result.substation_distance_m = data.substation_distance_m
            
            result.rail_nearby = data.rail_distance_m is not None and data.rail_distance_m < 2000
            result.rail_distance_m = data.rail_distance_m
            
            result.port_nearby = data.port_distance_km is not None and data.port_distance_km < 20
            result.port_distance_km = data.port_distance_km
            
            result.highway_nearby = data.highway_distance_m is not None and data.highway_distance_m < 500
            result.highway_distance_m = data.highway_distance_m
            
            result.coastal_access = data.coastal_access
            result.coastline_distance_m = data.coastline_distance_m
        
        elif source == "demographics" and data is not None:
            # From DemographicsData
            result.population_10km = data.population_10km
            result.urban_area = data.urban_area
            result.has_manufacturing = data.manufacturing_workers is not None and data.manufacturing_workers > 1000
            result.manufacturing_workers = data.manufacturing_workers
            result.unemployment_rate = data.unemployment_rate
        
        return result
    
    def geocode(self, address: str) -> Optional[GeocodedLocation]:
        """Geocode an address to coordinates."""
        return self.geocoder.geocode(address)
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Get address from coordinates."""
        return self.geocoder.reverse_geocode(lat, lon)


# Singleton
_fetcher: Optional[UnifiedDataFetcher] = None

def get_data_fetcher() -> UnifiedDataFetcher:
    """Get singleton data fetcher."""
    global _fetcher
    if _fetcher is None:
        _fetcher = UnifiedDataFetcher()
    return _fetcher
