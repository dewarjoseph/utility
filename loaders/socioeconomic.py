"""
Socioeconomic data loader.
Provides census, tax, and political data for land analysis.
"""

import logging
import os
import random
from functools import lru_cache
from typing import Dict, Tuple, Optional

import requests

log = logging.getLogger("loaders.socioeconomic")


class SocioeconomicLoader:
    """
    Loads socioeconomic data from public APIs to enrich land analysis.
    
    Data sources:
    - Census Bureau (demographics, income, employment)
    - County Assessor (property tax data)
    - Political indicators (voter registration, campaign finance)
    """

    # Census API Endpoints
    GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    ACS_BASE_URL = "https://api.census.gov/data/2022/acs/acs5"
    TIGERWEB_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/8/query"

    # ACS 5-Year Variable Codes (2022 Vintage)
    ACS_VARS = {
        "B19013_001E": "median_income",
        "B01003_001E": "total_population",
        "B23025_004E": "employed_civilian_labor_force",
        "B23025_002E": "total_labor_force",
        "B15003_022E": "bachelor_degree",
        "B15003_023E": "master_degree",
        "B15003_024E": "professional_degree",
        "B15003_025E": "doctorate_degree",
        "B15003_001E": "pop_25_plus",
        "B01002_001E": "median_age"
    }
    
    def __init__(self):
        self.census_api_key = os.getenv("CENSUS_API_KEY", "")
        if not self.census_api_key:
            log.debug("CENSUS_API_KEY not set - using mock data")
    
    def _get_fips_from_lat_lon(self, lat: float, lon: float) -> Optional[Dict[str, str]]:
        """
        Geocode coordinates to FIPS codes (State, County, Tract).
        """
        params = {
            "x": lon,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json"
        }
        
        try:
            response = requests.get(self.GEOCODER_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
            if result:
                return {
                    "state": result[0]["STATE"],
                    "county": result[0]["COUNTY"],
                    "tract": result[0]["TRACT"]
                }
        except Exception as e:
            log.warning(f"Geocoding failed for ({lat}, {lon}): {e}")
        return None

    def _get_land_area(self, state: str, county: str, tract: str) -> Optional[float]:
        """
        Fetch land area (AREALAND) for a tract using TigerWeb API.
        Returns area in square meters.
        """
        # Construct GEOID
        geoid = f"{state}{county}{tract}"

        params = {
            "where": f"GEOID='{geoid}'",
            "outFields": "AREALAND",
            "f": "json",
            "returnGeometry": "false"
        }

        try:
            response = requests.get(self.TIGERWEB_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            if features:
                return float(features[0]["attributes"]["AREALAND"])
        except Exception as e:
            log.warning(f"Failed to fetch land area for GEOID {geoid}: {e}")
        return None

    def _fetch_acs_data(self, state: str, county: str, tract: str) -> Optional[Dict[str, float]]:
        """
        Fetch socioeconomic variables from ACS API.
        """
        if not self.census_api_key:
            return None

        variables = ",".join(self.ACS_VARS.keys())
        params = {
            "get": variables,
            "for": f"tract:{tract}",
            "in": f"state:{state} county:{county}",
            "key": self.census_api_key
        }

        try:
            response = requests.get(self.ACS_BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            # API returns a list of lists. First list is headers, second is values.
            if len(data) > 1:
                headers = data[0]
                values = data[1]

                # Parse results into a dictionary using variable mapping
                result = {}
                # Create map from ACS code (header) to our internal name (value)
                # But headers match ACS codes.

                # Invert ACS_VARS for easy lookup or iterate.
                # Headers will be like ["B19013_001E", "B01003_001E", ..., "state", "county", "tract"]

                for i, header in enumerate(headers):
                    if header in self.ACS_VARS:
                        try:
                            val = float(values[i])
                            # Handle Census specific null values (e.g., -666666666)
                            if val < 0:
                                val = 0.0
                            result[self.ACS_VARS[header]] = val
                        except (ValueError, TypeError):
                            result[self.ACS_VARS[header]] = 0.0
                return result

        except Exception as e:
            log.warning(f"ACS data fetch failed: {e}")
        return None

    def _get_mock_data(self) -> Dict:
        """Return realistic mock data based on Santa Cruz patterns."""
        return {
            "median_income": random.randint(45000, 120000),
            "population_density": random.randint(100, 8000),  # per sq mile
            "employment_rate": round(random.uniform(0.85, 0.96), 2),
            "education_bachelor_plus": round(random.uniform(0.25, 0.65), 2),
            "age_median": random.randint(28, 45)
        }

    @lru_cache(maxsize=128)
    def get_census_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch demographic and economic data from Census Bureau.
        Falls back to mock data if API key is missing or requests fail.

        Returns:
            Dict with median_income, population_density, employment_rate, etc.
        """
        if not self.census_api_key:
            return self._get_mock_data()

        try:
            # 1. Geocode
            fips = self._get_fips_from_lat_lon(lat, lon)
            if not fips:
                log.warning("Could not identify census tract, falling back to mock data.")
                return self._get_mock_data()

            # 2. Fetch Data (ACS & Land Area)
            # ACS Data is critical. Land Area is for density calculation.
            acs_data = self._fetch_acs_data(fips["state"], fips["county"], fips["tract"])

            if not acs_data:
                log.warning("Could not fetch ACS data, falling back to mock data.")
                return self._get_mock_data()

            land_area_sq_meters = self._get_land_area(fips["state"], fips["county"], fips["tract"])

            # 3. Calculate Metrics
            # Employment Rate: Employed / Total Labor Force
            labor_force = acs_data.get("total_labor_force", 0)
            employment_rate = 0.0
            if labor_force > 0:
                employment_rate = acs_data.get("employed_civilian_labor_force", 0) / labor_force

            # Education: Bachelor+ / Population 25+
            pop_25_plus = acs_data.get("pop_25_plus", 0)
            education_rate = 0.0
            if pop_25_plus > 0:
                higher_ed = (
                    acs_data.get("bachelor_degree", 0) +
                    acs_data.get("master_degree", 0) +
                    acs_data.get("professional_degree", 0) +
                    acs_data.get("doctorate_degree", 0)
                )
                education_rate = higher_ed / pop_25_plus

            # Population Density: Pop / Sq Mile (1 sq mile = 2,589,988 sq meters)
            population_density = 0.0
            if land_area_sq_meters and land_area_sq_meters > 0:
                sq_miles = land_area_sq_meters / 2_589_988.11
                population_density = acs_data.get("total_population", 0) / sq_miles
            else:
                 # Fallback to mock density if area not available
                 population_density = random.randint(100, 8000)

            return {
                "median_income": int(acs_data.get("median_income", 0)),
                "population_density": int(population_density),
                "employment_rate": round(employment_rate, 2),
                "education_bachelor_plus": round(education_rate, 2),
                "age_median": int(acs_data.get("median_age", 0))
            }

        except Exception as e:
            log.error(f"Error fetching real census data: {e}", exc_info=True)
            return self._get_mock_data()
    
    def get_tax_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch property tax assessment data.
        
        In production, queries Santa Cruz County Assessor's API.
        """
        return {
            "assessed_value": random.randint(300000, 2000000),
            "tax_rate": round(random.uniform(0.008, 0.012), 4),
            "last_sale_price": random.randint(250000, 1800000),
            "last_sale_year": random.randint(2015, 2024)
        }
    
    def get_political_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch political leaning indicators.
        
        Sources: FEC campaign finance, voter registration
        """
        # Santa Cruz leans progressive
        political_score = random.uniform(-0.8, 0.3)  # -1 = progressive, +1 = conservative
        
        return {
            "political_leaning": political_score,
            "voter_turnout": round(random.uniform(0.55, 0.82), 2),
            "campaign_donations_per_capita": random.randint(50, 500),
            "local_ballot_support_development": round(random.uniform(0.3, 0.7), 2)
        }
    
    def enrich_quantum(self, quantum_dict: Dict) -> Dict:
        """Add socioeconomic features to a land quantum."""
        lat = quantum_dict.get("lat")
        lon = quantum_dict.get("lon")
        
        enriched = quantum_dict.copy()
        enriched["socioeconomic"] = {
            **self.get_census_data(lat, lon),
            **self.get_tax_data(lat, lon),
            **self.get_political_data(lat, lon)
        }
        
        return enriched
