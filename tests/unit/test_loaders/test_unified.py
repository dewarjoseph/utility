import pytest
from unittest.mock import MagicMock, patch
from loaders.unified import UnifiedDataFetcher, LocationData
from loaders.osm import LandUseData
from loaders.elevation import ElevationResult

@pytest.fixture
def mock_fetcher():
    with patch('loaders.unified.get_osm_loader') as mock_osm, \
         patch('loaders.unified.get_elevation_loader') as mock_elev, \
         patch('loaders.unified.get_flood_loader') as mock_flood, \
         patch('loaders.unified.get_geocoder') as mock_geo:
        
        fetcher = UnifiedDataFetcher()
        fetcher.osm = mock_osm.return_value
        fetcher.elevation = mock_elev.return_value
        fetcher.flood = mock_flood.return_value
        fetcher.geocoder = mock_geo.return_value
        yield fetcher

def test_fetch_all_sequential(mock_fetcher):
    """Verify sequential fetching logic."""
    # Setup mocks
    mock_fetcher.osm.fetch_land_use.return_value = LandUseData(
        latitude=37.0, longitude=-122.0,
        primary_land_use="industrial", land_use_confidence=1.0,
        nearest_road_meters=10, road_type="primary",
        nearest_water_meters=1000, water_type="",
        has_road_access=True, has_water_nearby=False,
        has_buildings=True, building_count=5,
        is_industrial=True, is_residential=False, is_commercial=False, is_agricultural=False, is_natural=False
    )
    
    mock_fetcher.elevation.get_elevation.return_value = ElevationResult(
        latitude=37.0, longitude=-122.0,
        elevation_meters=100.0, data_source="test", resolution_meters=10
    )
    
    # Run
    data = mock_fetcher.fetch_all(37.0, -122.0, parallel=False)
    
    assert data.latitude == 37.0
    assert data.is_industrial
    assert data.elevation_meters == 100.0
    assert "OSM" in data.data_sources
    assert "USGS" in data.data_sources

def test_to_features_dict():
    """Verify feature conversion."""
    data = LocationData(
        latitude=37.0, longitude=-122.0,
        is_industrial=True,
        has_road_access=True,
        road_distance_meters=10.0,
        elevation_meters=50.0,
        flood_risk_level="low"
    )
    
    features = data.to_features_dict()
    assert features["is_industrial"]
    assert features["has_road"]
    assert features["near_road"]  # < 50m
    assert not features["flood_risk"]
