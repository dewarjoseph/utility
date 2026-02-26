import pytest
from unittest.mock import patch, MagicMock
from loaders.socioeconomic import SocioeconomicLoader

@pytest.fixture
def loader():
    return SocioeconomicLoader()

@pytest.fixture
def mock_geocoder_response():
    return {
        "result": {
            "geographies": {
                "Census Tracts": [{
                    "STATE": "06",
                    "COUNTY": "087",
                    "TRACT": "120400"
                }]
            }
        }
    }

@pytest.fixture
def mock_acs_response():
    return [
        ["B19013_001E", "B01003_001E", "B23025_004E", "B23025_002E",
         "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E", "B15003_001E", "B01002_001E"],
        ["85000", "5000", "2500", "2600", "500", "200", "100", "50", "3000", "38.5"]
    ]

@pytest.fixture
def mock_tigerweb_response():
    return {
        "features": [{
            "attributes": {
                "AREALAND": "2589988"  # 1 square mile in sq meters (approx)
            }
        }]
    }

def test_get_census_data_mock_fallback(loader):
    """Verify mock census data generation when API key is missing."""
    loader.census_api_key = ""
    data = loader.get_census_data(37.0, -122.0)
    assert "median_income" in data
    assert data["median_income"] >= 45000
    assert "population_density" in data

@patch('loaders.socioeconomic.requests.get')
def test_get_census_data_real_success(mock_get, loader, mock_geocoder_response, mock_acs_response, mock_tigerweb_response):
    """Verify real census data flow with mocked API responses."""
    loader.census_api_key = "test_key"

    # Setup mock side effects for different URLs
    def side_effect(url, params=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        if "geocoder" in url:
            mock_resp.json.return_value = mock_geocoder_response
        elif "api.census.gov" in url:
            mock_resp.json.return_value = mock_acs_response
        elif "tigerweb" in url:
            mock_resp.json.return_value = mock_tigerweb_response
        return mock_resp

    mock_get.side_effect = side_effect

    data = loader.get_census_data(37.0, -122.0)

    # Assertions based on mock data
    # Income: 85000
    assert data["median_income"] == 85000

    # Density: Pop 5000 / 1 sq mile = 5000
    # Note: 2589988.11 sq meters is exactly 1 sq mile
    assert 4900 <= data["population_density"] <= 5100

    # Employment: 2500 / 2600 = 0.96
    assert data["employment_rate"] == 0.96

    # Education: (500+200+100+50) / 3000 = 850 / 3000 = 0.2833... -> 0.28
    assert data["education_bachelor_plus"] == 0.28

    # Age: 38.5 -> 38
    assert data["age_median"] == 38

@patch('loaders.socioeconomic.requests.get')
def test_get_census_data_geocoding_failure(mock_get, loader):
    """Verify fallback when geocoding fails."""
    loader.census_api_key = "test_key"

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("Geocoding failed")
    mock_get.return_value = mock_resp

    data = loader.get_census_data(37.0, -122.0)

    # Should fall back to mock data
    assert "median_income" in data
    assert data["median_income"] >= 45000 # Mock range

@patch('loaders.socioeconomic.requests.get')
def test_get_census_data_acs_failure(mock_get, loader, mock_geocoder_response):
    """Verify fallback when ACS data fetch fails."""
    loader.census_api_key = "test_key"

    def side_effect(url, params=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        if "geocoder" in url:
            mock_resp.json.return_value = mock_geocoder_response
        elif "api.census.gov" in url:
            raise Exception("ACS failed")
        return mock_resp

    mock_get.side_effect = side_effect

    data = loader.get_census_data(37.0, -122.0)

    # Should fall back to mock data
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
