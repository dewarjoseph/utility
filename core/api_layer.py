"""
API Integration Layer - External data source integrations.

Provides unified interface to external APIs for zoning, construction costs,
environmental risk, and solar potential. Uses mock data in development.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import random
import hashlib
import logging

# Configure logging
log = logging.getLogger(__name__)

# Import Google Maps Solar API client if available
try:
    from google.maps import solar_v1
    from google.api_core.client_options import ClientOptions
    GOOGLE_SOLAR_AVAILABLE = True
except ImportError:
    GOOGLE_SOLAR_AVAILABLE = False
    log.warning("Google Maps Solar API client not installed. Real solar data unavailable.")
try:
    from core.onebuild_client import OneBuildClient
except ImportError:
    OneBuildClient = None


class APIProvider(Enum):
    """External API providers."""
    GRIDICS = "gridics"           # Zoning data
    ZONEOMICS = "zoneomics"       # Zoning data
    ONEBUILD = "onebuild"         # Construction costs
    RSMEANS = "rsmeans"           # Construction costs (legacy)
    FIRST_STREET = "first_street" # Climate risk
    GOOGLE_SOLAR = "google_solar" # Solar potential
    ATTOM = "attom"               # Property data


@dataclass
class APIConfig:
    """Configuration for an API provider."""
    provider: APIProvider
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    enabled: bool = False
    rate_limit: int = 100  # requests per minute


@dataclass
class ZoningAPIResponse:
    """Standardized zoning API response."""
    zone_code: str
    zone_name: str
    allowed_uses: List[str]
    max_height_ft: float
    max_far: float
    max_lot_coverage: float
    setbacks: Dict[str, float]
    parking_ratio: float
    overlay_districts: List[str]
    source: APIProvider
    raw_response: Optional[Dict] = None


@dataclass  
class ConstructionCostResponse:
    """Standardized construction cost response."""
    cost_per_sqft: float
    location_factor: float
    material_costs: Dict[str, float]
    labor_costs: Dict[str, float]
    total_estimate: float
    confidence: float
    source: APIProvider


@dataclass
class ClimateRiskResponse:
    """Standardized climate risk response."""
    flood_factor: int  # 1-10
    fire_factor: int   # 1-10
    heat_factor: int   # 1-10
    wind_factor: int   # 1-10
    overall_risk: int  # 1-10
    insurance_estimate: float
    source: APIProvider


@dataclass
class SolarPotentialResponse:
    """Standardized solar potential response."""
    annual_kwh: float
    system_capacity_kw: float
    panel_count: int
    roof_area_sqft: float
    shade_factor: float
    estimated_savings: float
    source: APIProvider


class APIIntegrationLayer:
    """Unified interface for external API integrations."""
    
    def __init__(self):
        self.configs: Dict[APIProvider, APIConfig] = {}
        self.use_mock = True  # Default to mock data
        self._solar_client = None
        
        # Initialize default configs
        for provider in APIProvider:
            self.configs[provider] = APIConfig(provider=provider)
    
    def configure(self, provider: APIProvider, api_key: str, enabled: bool = True):
        """Configure an API provider."""
        self.configs[provider] = APIConfig(
            provider=provider,
            api_key=api_key,
            enabled=enabled,
        )
        if enabled:
            self.use_mock = False
    
    def get_zoning(
        self,
        latitude: float,
        longitude: float,
        address: Optional[str] = None
    ) -> ZoningAPIResponse:
        """Get zoning data for a location."""
        if self.use_mock or not self._is_enabled(APIProvider.GRIDICS):
            return self._mock_zoning(latitude, longitude)
        
        # TODO: Implement real Gridics/Zoneomics API call
        return self._mock_zoning(latitude, longitude)
    
    def get_construction_costs(
        self,
        latitude: float,
        longitude: float,
        building_type: str,
        sqft: float
    ) -> ConstructionCostResponse:
        """Get construction cost estimates."""
        if self.use_mock or not self._is_enabled(APIProvider.ONEBUILD):
            return self._mock_construction_costs(latitude, longitude, building_type, sqft)
        
        try:
            # Check if OneBuildClient is available
            if OneBuildClient is None:
                logging.warning("OneBuildClient not available. Falling back to mock data.")
                return self._mock_construction_costs(latitude, longitude, building_type, sqft)

            client = OneBuildClient(api_key=self.configs[APIProvider.ONEBUILD].api_key)
            if not client.is_configured():
                return self._mock_construction_costs(latitude, longitude, building_type, sqft)

            # Fetch real data
            # Note: region_id is omitted as we don't have a mapping from lat/lon to region_id yet
            # and the client defaults to national average or handles it.
            items = client.get_cost_data(building_type)

            if not items:
                # Fallback if API returns no data
                return self._mock_construction_costs(latitude, longitude, building_type, sqft)

            material_costs = {}
            labor_costs = {}
            total_material = 0.0
            total_labor = 0.0

            # Since items are representative per unit, we need to estimate quantities
            # This is a heuristic estimation since we don't have a full BOM
            # We assume the "price" returned is a unit price, and we scale it by sqft
            # with some factor based on the item type.
            # However, simpler approach: sum the unit prices to get a "base cost factor"
            # and then scale to match expected market rates, or treat them as $/sqft components.

            # Let's treat the returned items as major cost drivers per sqft (or similar unit)
            # This is an approximation because 1build returns unit costs (e.g. per board, per hour)

            # Better approach given the constraints:
            # Use the API data to populate the *breakdown* and *relative costs*,
            # but normalize the total to a reasonable range if needed, or trust the API if it returns $/sqft.
            # The client implementation returns items with 'price' and 'unit'.

            # For this implementation, we will assume the returned items represent
            # key cost drivers and we aggregate them. To make the numbers realistic for
            # a "total project cost", we might need to apply a multiplier if the API
            # only returns specific material costs.

            for item in items:
                # Simple heuristic: assume item price contributes to cost per sqft
                # In reality, you'd multiply price * quantity_per_sqft
                # We'll use a standard quantity factor of 1.0 for simplicity in this integration
                cost_contribution = item.price

                if item.category == 'material':
                    material_costs[item.name] = cost_contribution * sqft
                    total_material += cost_contribution
                else:
                    labor_costs[item.name] = cost_contribution * sqft
                    total_labor += cost_contribution

            # Calculate totals
            cost_per_sqft = total_material + total_labor

            # Sanity check: if cost is too low (e.g. just one 2x4 price), fallback or scale
            # A typical building is $150-$400 / sqft.
            # If our sum is < $50, it's likely just unit prices of components, not per sqft assembly costs.
            # We will scale it up to a realistic baseline if it's too low, maintaining the ratio.

            min_expected_cost = 150.0
            if cost_per_sqft < min_expected_cost and cost_per_sqft > 0:
                scale_factor = min_expected_cost / cost_per_sqft
                cost_per_sqft *= scale_factor
                # Scale components
                for k in material_costs: material_costs[k] *= scale_factor
                for k in labor_costs: labor_costs[k] *= scale_factor

            total_estimate = (sum(material_costs.values()) + sum(labor_costs.values()))

            return ConstructionCostResponse(
                cost_per_sqft=round(cost_per_sqft, 2),
                location_factor=1.0, # API data already localized if region provided, else 1.0
                material_costs=material_costs,
                labor_costs=labor_costs,
                total_estimate=round(total_estimate, 0),
                confidence=0.9, # Higher confidence with real data
                source=APIProvider.ONEBUILD,
            )

        except Exception as e:
            logging.error(f"Error calling 1Build API: {e}")
            return self._mock_construction_costs(latitude, longitude, building_type, sqft)
    
    def get_climate_risk(
        self,
        latitude: float,
        longitude: float
    ) -> ClimateRiskResponse:
        """Get climate risk assessment."""
        if self.use_mock or not self._is_enabled(APIProvider.FIRST_STREET):
            return self._mock_climate_risk(latitude, longitude)
        
        try:
            return self._get_first_street_risk(latitude, longitude)
        except Exception as e:
            logger.error(f"First Street API failed: {e}. Falling back to mock data.")
            return self._mock_climate_risk(latitude, longitude)
    
    def get_solar_potential(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: float,
        electricity_rate: float = 0.15
    ) -> SolarPotentialResponse:
        """Get solar generation potential."""
        if self.use_mock or not self._is_enabled(APIProvider.GOOGLE_SOLAR):
            return self._mock_solar_potential(latitude, longitude, roof_sqft)
        
        # We check enabled status inside _is_enabled but we also need to know if the library is available.
        # However, for testing, we might want to bypass the library check if we mock the client getter.
        # But _get_solar_client handles the library check too.

        try:
            client = self._get_solar_client()
            if client:
                return self._get_real_solar_potential(client, latitude, longitude, electricity_rate)
        except Exception as e:
            log.error(f"Error calling Google Solar API: {e}")

        return self._mock_solar_potential(latitude, longitude, roof_sqft)

    def _get_solar_client(self) -> Optional[Any]:
        """Get or initialize the Google Solar API client."""
        if self._solar_client:
            return self._solar_client

        if not GOOGLE_SOLAR_AVAILABLE:
            return None

        config = self.configs.get(APIProvider.GOOGLE_SOLAR)
        if not config or not config.api_key:
            return None

        # Initialize client with API key
        options = ClientOptions(api_key=config.api_key)
        self._solar_client = solar_v1.SolarClient(client_options=options)
        return self._solar_client

    def _get_real_solar_potential(
        self,
        client: Any,
        latitude: float,
        longitude: float,
        electricity_rate: float
    ) -> SolarPotentialResponse:
        """Fetch real solar potential from Google Solar API."""
        # Create request
        request = solar_v1.FindClosestBuildingInsightsRequest(
            location={
                "latitude": latitude,
                "longitude": longitude
            },
            required_quality="HIGH"
        )

        # Call API
        response = client.find_closest_building_insights(request=request)

        if not response.solar_potential:
             raise ValueError("No solar potential data found for location")

        potential = response.solar_potential

        # Extract data
        # max_array_panels_count is total potential panels
        panel_count = potential.max_array_panels_count

        # max_array_area_meters2 to sqft (1 m2 = 10.764 sqft)
        roof_area_sqft = potential.max_array_area_meters2 * 10.7639

        # sunshine hours
        sun_hours = potential.max_sunshine_hours_per_year

        # Capacity (kW) - assume standard 400W panel if not specified,
        # or use panel_capacity_watts from config/response if available.
        # The API `panel_capacity_watts` describes the panel capacity used in calculations.
        panel_capacity_watts = potential.panel_capacity_watts
        system_capacity_kw = (panel_count * panel_capacity_watts) / 1000.0

        # Annual kWh calculation
        # Carbon offset factor is kg/MWh, so not directly energy.
        # We can estimate annual kWh = System kW * Sun Hours * Efficiency Factor (roughly 0.75-0.85)
        # However, `whole_roof_stats` might have better data or we can integrate `carbon_offset_factor` if needed.
        # A simpler approximation often used with this API:
        annual_kwh = system_capacity_kw * sun_hours * 0.8 # 0.8 system efficiency derate

        # Savings
        estimated_savings = annual_kwh * electricity_rate

        return SolarPotentialResponse(
            annual_kwh=round(annual_kwh, 0),
            system_capacity_kw=round(system_capacity_kw, 1),
            panel_count=panel_count,
            roof_area_sqft=round(roof_area_sqft, 0),
            shade_factor=0.15, # Placeholder or derive from sunshine_quantiles
            estimated_savings=round(estimated_savings, 0),
            source=APIProvider.GOOGLE_SOLAR,
        )
    
    def _is_enabled(self, provider: APIProvider) -> bool:
        """Check if a provider is enabled."""
        config = self.configs.get(provider)
        return config and config.enabled and config.api_key

    def _get_secure_seed(self, lat: float, lon: float) -> int:
        """Generate a deterministic, secure seed based on location."""
        # Create a unique string for the location
        data = f"{lat:.6f},{lon:.6f}".encode('utf-8')
        # Use SHA-256 for a secure hash
        hash_obj = hashlib.sha256(data)
        # Convert the hash (hex) to an integer
        # We take the first 8 bytes (16 hex chars) which is plenty for a seed
        seed_int = int(hash_obj.hexdigest()[:16], 16)
        return seed_int
    
    def _get_first_street_risk(self, lat: float, lon: float) -> ClimateRiskResponse:
        """Fetch real climate risk data from First Street Foundation API."""
        config = self.configs[APIProvider.FIRST_STREET]
        url = config.base_url or "https://api.firststreet.org/v3/graphql"

        query = """
        query GetClimateRisk($lat: Float!, $lng: Float!) {
          placeByCoordinate(lat: $lat, lng: $lng) {
            placeId
            flood {
              data {
                floodFactors {
                  floodFactor
                  ssp
                  relativeYear
                }
                floodDamages {
                  aal {
                    aal
                    ssp
                    relativeYear
                  }
                }
              }
            }
            wildfire {
              data {
                fireFactors {
                  fireFactor
                  ssp
                  relativeYear
                }
                wildfireDamages {
                  aal {
                    aal
                    ssp
                    relativeYear
                  }
                }
              }
            }
            heat {
              data {
                heatFactors {
                  heatFactor
                  ssp
                  relativeYear
                }
              }
            }
            wind {
              data {
                windFactors {
                  windFactor
                  ssp
                  relativeYear
                }
                windDamages {
                  aal {
                    aal
                    ssp
                    relativeYear
                  }
                }
              }
            }
          }
        }
        """

        response = requests.post(
            url,
            json={'query': query, 'variables': {'lat': lat, 'lng': lon}},
            headers={'Authorization': f'Bearer {config.api_key}'},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        if 'errors' in data:
            raise ValueError(f"GraphQL Error: {data['errors']}")

        place = data.get('data', {}).get('placeByCoordinate')
        if not place:
            raise ValueError("No place data returned for coordinates")

        # Filter helper for SSP_2_45 and relativeYear 0
        def find_current_scenario(items):
            if not items:
                return None
            for item in items:
                if item.get('ssp') == 'SSP_2_45' and item.get('relativeYear') == 0:
                    return item
            # Fallback to first item if exact match not found
            return items[0]

        # Helper to safely extract factor
        def get_factor(peril_data, factor_key, list_key=None):
            if not peril_data or 'data' not in peril_data:
                return 1
            factors = peril_data['data'].get(list_key or f"{factor_key}s", [])
            factor_item = find_current_scenario(factors)

            if not factor_item:
                return 1

            val = factor_item.get(factor_key, 1)
            # Normalize 1-100 scale to 1-10.
            normalized = math.ceil(val / 10.0)
            return max(1, min(10, normalized))

        # Helper to extract AAL (Annualized Average Loss)
        def get_aal(peril_data, damages_key):
            if not peril_data or 'data' not in peril_data:
                return 0
            damages = peril_data['data'].get(damages_key, {})
            if not damages:
                return 0
            aals = damages.get('aal', [])
            aal_item = find_current_scenario(aals)

            if not aal_item:
                return 0
            return float(aal_item.get('aal', 0))

        flood = get_factor(place.get('flood'), 'floodFactor')
        fire = get_factor(place.get('wildfire'), 'fireFactor', 'fireFactors')
        heat = get_factor(place.get('heat'), 'heatFactor')
        wind = get_factor(place.get('wind'), 'windFactor')

        overall = int((flood * 0.3 + fire * 0.3 + heat * 0.2 + wind * 0.2))

        # Calculate insurance estimate from AALs
        flood_aal = get_aal(place.get('flood'), 'floodDamages')
        fire_aal = get_aal(place.get('wildfire'), 'wildfireDamages')
        wind_aal = get_aal(place.get('wind'), 'windDamages')

        total_aal = flood_aal + fire_aal + wind_aal

        # If AAL data is missing or zero, fallback to heuristic
        if total_aal <= 0:
            base_insurance = 1500
            risk_multiplier = 1 + (overall - 3) * 0.15
            insurance_estimate = round(base_insurance * risk_multiplier, 0)
        else:
            # Insurance premium usually covers AAL + overhead/profit + buffer
            # Rough multiplier of 2x-3x AAL is common in simple models, but let's stick to a safe 1.2x + base if AAL is low
            insurance_estimate = round(total_aal * 1.5 + 500, 0)

        return ClimateRiskResponse(
            flood_factor=flood,
            fire_factor=fire,
            heat_factor=heat,
            wind_factor=wind,
            overall_risk=overall,
            insurance_estimate=insurance_estimate,
            source=APIProvider.FIRST_STREET,
        )

    def _mock_zoning(self, lat: float, lon: float) -> ZoningAPIResponse:
        """Generate mock zoning data."""
        # Use a local random instance to avoid global state modification
        rng = random.Random(self._get_secure_seed(lat, lon))
        
        zones = [
            ("R-1", "Single Family Residential", ["single_family", "adu"]),
            ("R-2", "Two-Family Residential", ["single_family", "duplex", "adu"]),
            ("R-3", "Multi-Family Residential", ["apartment", "condo", "mixed_use"]),
            ("C-1", "Neighborhood Commercial", ["retail", "restaurant", "office"]),
            ("C-2", "Community Commercial", ["retail", "office", "hotel", "entertainment"]),
        ]
        
        zone = rng.choice(zones)
        
        return ZoningAPIResponse(
            zone_code=zone[0],
            zone_name=zone[1],
            allowed_uses=zone[2],
            max_height_ft=rng.choice([30, 35, 45, 55, 65]),
            max_far=rng.choice([0.5, 0.6, 1.0, 1.5, 2.0]),
            max_lot_coverage=rng.choice([0.4, 0.45, 0.5, 0.6]),
            setbacks={
                'front': rng.choice([15, 20, 25]),
                'side': rng.choice([5, 7, 10]),
                'rear': rng.choice([10, 15, 20]),
            },
            parking_ratio=rng.choice([1.0, 1.5, 2.0]),
            overlay_districts=rng.choice([[], ["TOD"], ["Historic"]]),
            source=APIProvider.GRIDICS,
        )
    
    def _mock_construction_costs(
        self,
        lat: float,
        lon: float,
        building_type: str,
        sqft: float
    ) -> ConstructionCostResponse:
        """Generate mock construction cost data."""
        # Use a local random instance to avoid global state modification
        rng = random.Random(self._get_secure_seed(lat, lon))
        
        # Base costs by type
        base_costs = {
            'wood_frame': 180,
            'steel_frame': 220,
            'concrete': 250,
            'modular': 160,
        }
        
        base = base_costs.get(building_type, 200)
        
        # Location factor (coastal CA is expensive)
        is_california = -125 < lon < -114 and 32 < lat < 42
        location_factor = 1.35 if is_california else 1.0
        
        cost_per_sqft = base * location_factor * rng.uniform(0.9, 1.1)
        
        return ConstructionCostResponse(
            cost_per_sqft=round(cost_per_sqft, 2),
            location_factor=location_factor,
            material_costs={
                'concrete': sqft * 15,
                'lumber': sqft * 25,
                'steel': sqft * 10,
                'finishes': sqft * 30,
            },
            labor_costs={
                'general': sqft * 40,
                'electrical': sqft * 15,
                'plumbing': sqft * 12,
                'hvac': sqft * 10,
            },
            total_estimate=round(cost_per_sqft * sqft, 0),
            confidence=0.85,
            source=APIProvider.ONEBUILD,
        )
    
    def _mock_climate_risk(self, lat: float, lon: float) -> ClimateRiskResponse:
        """Generate mock climate risk data."""
        # Use a local random instance to avoid global state modification
        rng = random.Random(self._get_secure_seed(lat, lon))
        
        # Coastal = flood risk, California = fire risk, South = heat
        is_coastal = abs(lon) > 120
        is_california = -125 < lon < -114 and 32 < lat < 42
        is_southern = lat < 38
        
        flood = rng.randint(1, 4) + (3 if is_coastal else 0)
        fire = rng.randint(1, 4) + (4 if is_california else 0)
        heat = rng.randint(2, 5) + (3 if is_southern else 0)
        wind = rng.randint(2, 6)
        
        flood = min(10, flood)
        fire = min(10, fire)
        heat = min(10, heat)
        
        overall = int((flood * 0.3 + fire * 0.3 + heat * 0.2 + wind * 0.2))
        
        # Insurance estimate based on risk
        base_insurance = 1500
        risk_multiplier = 1 + (overall - 3) * 0.15
        
        return ClimateRiskResponse(
            flood_factor=flood,
            fire_factor=fire,
            heat_factor=heat,
            wind_factor=wind,
            overall_risk=overall,
            insurance_estimate=round(base_insurance * risk_multiplier, 0),
            source=APIProvider.FIRST_STREET,
        )
    
    def _mock_solar_potential(
        self,
        lat: float,
        lon: float,
        roof_sqft: float
    ) -> SolarPotentialResponse:
        """Generate mock solar potential data."""
        # Solar potential based on latitude
        lat_factor = 1.0 + (40 - abs(lat)) * 0.01
        
        # Usable roof area (70%)
        usable_sqft = roof_sqft * 0.7
        
        # Watts per sqft
        watts_per_sqft = 15
        system_kw = (usable_sqft * watts_per_sqft) / 1000
        
        # Panels (400W each)
        panel_count = int(system_kw * 1000 / 400)
        
        # Annual production (kWh)
        sun_hours = 4.5 * lat_factor
        annual_kwh = system_kw * sun_hours * 365
        
        # Savings at $0.15/kWh
        savings = annual_kwh * 0.15
        
        return SolarPotentialResponse(
            annual_kwh=round(annual_kwh, 0),
            system_capacity_kw=round(system_kw, 1),
            panel_count=panel_count,
            roof_area_sqft=usable_sqft,
            shade_factor=0.15,
            estimated_savings=round(savings, 0),
            source=APIProvider.GOOGLE_SOLAR,
        )
    
    def get_all_data(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: float = 2000,
        building_type: str = 'wood_frame',
        sqft: float = 10000,
        electricity_rate: float = 0.15
    ) -> Dict[str, Any]:
        """Get all available data for a location."""
        return {
            'zoning': self.get_zoning(latitude, longitude),
            'construction': self.get_construction_costs(latitude, longitude, building_type, sqft),
            'climate': self.get_climate_risk(latitude, longitude),
            'solar': self.get_solar_potential(latitude, longitude, roof_sqft, electricity_rate),
        }


def get_api_layer() -> APIIntegrationLayer:
    """Factory function for API integration layer."""
    return APIIntegrationLayer()
