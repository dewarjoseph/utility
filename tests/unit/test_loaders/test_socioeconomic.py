import pytest
from loaders.socioeconomic import SocioeconomicLoader

@pytest.fixture
def loader():
    return SocioeconomicLoader()

def test_get_census_data(loader):
    """Verify mock census data generation."""
    data = loader.get_census_data(37.0, -122.0)
    assert "median_income" in data
    assert data["median_income"] >= 45000

def test_get_tax_data(loader):
    """Verify mock tax data."""
    data = loader.get_tax_data(37.0, -122.0)
    assert "assessed_value" in data

def test_get_political_data(loader):
    """Verify mock political data."""
    data = loader.get_political_data(37.0, -122.0)
    assert -1.0 <= data["political_leaning"] <= 1.0

def test_enrich_quantum(loader):
    """Verify quantum enrichment."""
    q = {"lat": 37.0, "lon": -122.0}
    enriched = loader.enrich_quantum(q)
    assert "socioeconomic" in enriched
    assert "median_income" in enriched["socioeconomic"]
