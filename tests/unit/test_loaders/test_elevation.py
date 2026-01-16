import pytest
from unittest.mock import MagicMock, patch
from loaders.elevation import ElevationLoader, ElevationResult

@pytest.fixture
def mock_loader(tmp_path):
    cache_path = str(tmp_path / "test_elev.db")
    with patch('requests.Session') as mock_session:
        loader = ElevationLoader(cache_path=cache_path)
        loader.session = mock_session.return_value
        yield loader

def test_get_elevation_success(mock_loader):
    """Verify successful elevation fetch."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": 123.4}
    mock_loader.session.get.return_value = mock_response
    
    result = mock_loader.get_elevation(37.0, -122.0)
    assert result.elevation_meters == 123.4
    assert result.resolution_meters == 10.0

def test_get_elevation_invalid(mock_loader):
    """Verify handling of invalid/ocean data."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": -9999}
    mock_loader.session.get.return_value = mock_response
    
    result = mock_loader.get_elevation(37.0, -122.0)
    assert result is None

def test_batch_processing(mock_loader):
    """Verify batch processing logic."""
    mock_response = MagicMock()
    mock_response.json.side_effect = [{"value": 10}, {"value": 20}]
    mock_loader.session.get.return_value = mock_response
    
    points = [(37.0, -122.0), (37.1, -122.1)]
    results = mock_loader.get_elevations_batch(points)
    
    assert len(results) == 2
    assert results[0].elevation_meters == 10
    assert results[1].elevation_meters == 20
