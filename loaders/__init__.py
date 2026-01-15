"""
Data loaders for Land Utility Engine.

Includes:
- Geocoding (Nominatim)
- Land use (OpenStreetMap Overpass)
- Elevation (USGS)
- Flood zones (FEMA)
- Unified fetcher (combines all sources)
"""

from loaders.osm import OSMLoader, get_osm_loader, LandUseData
from loaders.gis import GISLoader, GISFeatureExtractor
from loaders.socioeconomic import SocioeconomicLoader
from loaders.geocoder import Geocoder, get_geocoder, GeocodedLocation
from loaders.elevation import ElevationLoader, get_elevation_loader, ElevationResult
from loaders.flood_zones import FloodZoneLoader, get_flood_loader, FloodZoneResult
from loaders.unified import UnifiedDataFetcher, get_data_fetcher, LocationData

__all__ = [
    # Legacy
    "OSMLoader",
    "GISLoader",
    "GISFeatureExtractor",
    "SocioeconomicLoader",
    # New loaders
    "Geocoder",
    "get_geocoder",
    "GeocodedLocation",
    "get_osm_loader",
    "LandUseData",
    "ElevationLoader",
    "get_elevation_loader",
    "ElevationResult",
    "FloodZoneLoader",
    "get_flood_loader",
    "FloodZoneResult",
    # Unified
    "UnifiedDataFetcher",
    "get_data_fetcher",
    "LocationData",
]
