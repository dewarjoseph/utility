import pytest
from unittest.mock import MagicMock, patch
from loaders.demographics import DemographicsLoader, DemographicsData

@pytest.fixture
def loader():
    with patch('sqlite3.connect') as mock_conn:
        loader = DemographicsLoader()
        yield loader

def test_estimate_urban(loader):
    """Verify urban demographic estimation."""
    # Downtown Santa Cruz coordinates
    data = loader._estimate_demographics(36.97, -122.03)
    assert data.urban_area
    assert data.population_10km > 50000

def test_estimate_rural(loader):
    """Verify rural demographic estimation."""
    # Far away
    data = loader._estimate_demographics(40.0, -120.0)
    assert not data.urban_area
    assert data.county_name == "Unknown"

def test_get_demographics_cache_hit(loader):
    """Verify cache usage."""
    with patch.object(loader, '_check_cache', return_value={'population_10km': 100}):
        data = loader.get_demographics(0, 0)
        assert data.population_10km == 100

def test_to_features(loader):
    """Verify feature dictionary conversion."""
    data = DemographicsData(population_10km=100000, labor_force=20000, urban_area=True)
    feats = data.to_features_dict()
    assert feats['high_population']
    assert feats['has_labor_force']
    assert feats['urban_area']
