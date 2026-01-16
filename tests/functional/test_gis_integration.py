import pytest
from unittest.mock import patch, MagicMock
from loaders.gis import GISLoader, GISFeatureExtractor

@pytest.fixture
def gis_loader():
    return GISLoader(cache_dir="test_gis_cache", use_production_apis=True)

def test_gis_enrichment_flow(gis_loader):
    """Verify the full enrichment pipeline combines data sources."""
    # Mock specific calls to avoid real network requests
    with patch.object(gis_loader, 'get_parcel_data') as mock_parcel, \
         patch.object(gis_loader, 'get_lidar_elevation') as mock_lidar:
        
        mock_parcel.return_value = {"apn": "TEST-123"}
        mock_lidar.return_value = {"elevation_ft": 100}
        
        raw_quantum = {"lat": 36.97, "lon": -122.02}
        result = gis_loader.enrich_quantum(raw_quantum)
        
        assert "gis_data" in result
        assert result["gis_data"]["apn"] == "TEST-123"
        assert result["gis_data"]["elevation_ft"] == 100
        # Check that other "live" methods (using mocks or defaults) are called or exist
        assert "wildfire_risk_score" in result["gis_data"]

def test_api_degradation(gis_loader):
    """Verify expected behavior when APIs fail."""
    with patch('requests.get') as mock_get:
        # Simulate a 500 error
        mock_get.return_value.status_code = 500
        
        # Should fall back to safe default/random mocks
        data = gis_loader.get_parcel_data(36.97, -122.02)
        assert isinstance(data, dict)
        # Assuming mock data generation happens on failure
        assert "apn" in data

def test_feature_extraction():
    """Verify feature normalization logic."""
    raw_gis_data = {
        'elevation_ft': 1000,       # expects / 2000 -> 0.5
        'slope_percent': 22.5,     # expects / 45 -> 0.5
        'wildfire_risk_score': 0,  # safety -> 1.0
        'flood_risk_score': 10,    # safety -> 0.0
        'distance_to_sewer_ft': 0, # accessibility -> 1.0
        'current_zoning': 'M-1'    # industrial -> 1
    }
    
    features = GISFeatureExtractor.extract_features(raw_gis_data)
    
    assert features['elevation_normalized'] == 0.5
    assert features['slope_normalized'] == 0.5
    assert features['wildfire_safety'] == 1.0
    assert features['flood_safety'] == 0.0
    assert features['sewer_accessibility'] == 1.0
    assert features['is_industrial_zoned'] == 1
    assert features['is_residential_zoned'] == 0
