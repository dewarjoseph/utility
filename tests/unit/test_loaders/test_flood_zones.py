import pytest
from unittest.mock import MagicMock, patch
from loaders.flood_zones import FloodZoneLoader

@pytest.fixture
def mock_loader(tmp_path):
    cache_path = str(tmp_path / "test_flood.db")
    with patch('requests.Session') as mock_session:
        loader = FloodZoneLoader(cache_path=cache_path)
        loader.session = mock_session.return_value
        yield loader

def test_get_flood_zone_found(mock_loader):
    """Verify finding a flood zone."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [{
            "attributes": {
                "FLD_ZONE": "AE",
                "STATIC_BFE": "12.5",
                "DFIRM_ID": "12345"
            }
        }]
    }
    mock_loader.session.get.return_value = mock_response
    
    result = mock_loader.get_flood_zone(37.0, -122.0)
    assert result.flood_zone == "AE"
    assert result.flood_risk_level == "high"
    assert result.base_flood_elevation == 12.5

def test_get_flood_zone_none(mock_loader):
    """Verify no flood zone found (Zone X)."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"features": []}
    mock_loader.session.get.return_value = mock_response
    
    result = mock_loader.get_flood_zone(37.0, -122.0)
    assert result.flood_zone == "X"
    assert result.flood_risk_level == "low"
