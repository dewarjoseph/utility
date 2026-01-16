import pytest
from unittest.mock import MagicMock, patch
from loaders.geocoder import Geocoder

@pytest.fixture
def mock_loader(tmp_path):
    cache_path = str(tmp_path / "test_geo.db")
    with patch('requests.Session') as mock_session:
        loader = Geocoder(cache_path=cache_path)
        loader.session = mock_session.return_value
        yield loader

def test_geocode_success(mock_loader):
    """Verify geocoding success."""
    mock_response = MagicMock()
    mock_response.json.return_value = [{
        "lat": "37.0",
        "lon": "-122.0",
        "display_name": "Test Place",
        "type": "city",
        "boundingbox": ["36", "38", "-123", "-121"]
    }]
    mock_loader.session.get.return_value = mock_response
    
    result = mock_loader.geocode("Santa Cruz")
    assert result.latitude == 37.0
    assert result.longitude == -122.0
    assert result.display_name == "Test Place"

def test_reverse_geocode_success(mock_loader):
    """Verify reverse geocoding success."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"display_name": "123 Main St"}
    mock_loader.session.get.return_value = mock_response
    
    name = mock_loader.reverse_geocode(37.0, -122.0)
    assert name == "123 Main St"
