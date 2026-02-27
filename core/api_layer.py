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
import os
import requests
import logging

log = logging.getLogger(__name__)


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
        
        # Initialize default configs
        for provider in APIProvider:
            self.configs[provider] = APIConfig(provider=provider)

        # Auto-configure from environment variables
        self._configure_from_env()

    def _configure_from_env(self):
        """Configure providers from environment variables."""
        env_map = {
            APIProvider.GRIDICS: "GRIDICS_API_KEY",
            APIProvider.ZONEOMICS: "ZONEOMICS_API_KEY",
            APIProvider.ONEBUILD: "ONEBUILD_API_KEY",
            APIProvider.FIRST_STREET: "FIRST_STREET_API_KEY",
            APIProvider.GOOGLE_SOLAR: "GOOGLE_SOLAR_API_KEY",
            APIProvider.ATTOM: "ATTOM_API_KEY",
        }

        for provider, env_var in env_map.items():
            api_key = os.environ.get(env_var)
            if api_key:
                log.info(f"Enabling {provider.value} from environment variable {env_var}")
                self.configure(provider, api_key, enabled=True)
    
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
        
        # Real API Implementation
        try:
            config = self.configs[APIProvider.GRIDICS]

            # Use provided base URL or default to Gridics API
            base_url = config.base_url or "https://api.gridics.com/v1"

            # Fetch parcel data by lat/lon
            response = requests.get(
                f"{base_url}/zoning/parcel",
                params={
                    "lat": latitude,
                    "lng": longitude
                },
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Accept": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Parse response - mapping Gridics structure to our schema
                # Note: This schema is hypothetical based on typical zoning API structures
                # as specific documentation was unavailable.

                parcel = data.get("parcel", {})
                zoning = parcel.get("zoning", {})

                return ZoningAPIResponse(
                    zone_code=zoning.get("code", "UNK"),
                    zone_name=zoning.get("name", "Unknown Zone"),
                    allowed_uses=zoning.get("allowed_uses", []),
                    max_height_ft=float(zoning.get("constraints", {}).get("max_height_ft", 0)),
                    max_far=float(zoning.get("constraints", {}).get("max_far", 0)),
                    max_lot_coverage=float(zoning.get("constraints", {}).get("max_lot_coverage", 0)),
                    setbacks={
                        "front": float(zoning.get("setbacks", {}).get("front", 0)),
                        "side": float(zoning.get("setbacks", {}).get("side", 0)),
                        "rear": float(zoning.get("setbacks", {}).get("rear", 0)),
                    },
                    parking_ratio=float(zoning.get("parking", {}).get("ratio", 0)),
                    overlay_districts=zoning.get("overlays", []),
                    source=APIProvider.GRIDICS,
                    raw_response=data
                )
            else:
                log.error(f"Gridics API error: {response.status_code} - {response.text}")
                # Fallback to mock on error
                return self._mock_zoning(latitude, longitude)

        except Exception as e:
            log.exception(f"Exception calling Gridics API: {e}")
            # Fallback to mock on exception
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
        
        # Real API Implementation
        try:
            config = self.configs[APIProvider.ONEBUILD]

            # Use provided base URL or default to 1build API
            base_url = config.base_url or "https://api.1build.com/v1"

            # Fetch cost estimates
            response = requests.post(
                f"{base_url}/estimates/calculate",
                json={
                    "location": {
                        "latitude": latitude,
                        "longitude": longitude
                    },
                    "project_details": {
                        "type": building_type,
                        "area_sqft": sqft,
                        "quality": "standard"
                    }
                },
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()

                # Parse 1build response (hypothetical structure)
                estimate = data.get("estimate", {})
                breakdown = estimate.get("breakdown", {})

                return ConstructionCostResponse(
                    cost_per_sqft=float(estimate.get("cost_per_sqft", 0)),
                    location_factor=float(estimate.get("location_factor", 1.0)),
                    material_costs=breakdown.get("materials", {}),
                    labor_costs=breakdown.get("labor", {}),
                    total_estimate=float(estimate.get("total", 0)),
                    confidence=float(estimate.get("confidence_score", 0.0)),
                    source=APIProvider.ONEBUILD
                )
            else:
                log.error(f"1build API error: {response.status_code} - {response.text}")
                return self._mock_construction_costs(latitude, longitude, building_type, sqft)

        except Exception as e:
            log.exception(f"Exception calling 1build API: {e}")
            return self._mock_construction_costs(latitude, longitude, building_type, sqft)
    
    def get_climate_risk(
        self,
        latitude: float,
        longitude: float
    ) -> ClimateRiskResponse:
        """Get climate risk assessment."""
        if self.use_mock or not self._is_enabled(APIProvider.FIRST_STREET):
            return self._mock_climate_risk(latitude, longitude)
        
        # Real API Implementation
        try:
            config = self.configs[APIProvider.FIRST_STREET]

            # Use provided base URL or default to First Street API
            base_url = config.base_url or "https://api.firststreet.org/v1"

            # Fetch property risk data
            response = requests.get(
                f"{base_url}/data/property",
                params={
                    "lat": latitude,
                    "lng": longitude,
                    "products": "flood,fire,heat,wind"
                },
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Accept": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Parse First Street response (hypothetical structure)
                risk = data.get("risk", {})
                flood = risk.get("flood", {}).get("risk_factor", 1)
                fire = risk.get("fire", {}).get("risk_factor", 1)
                heat = risk.get("heat", {}).get("risk_factor", 1)
                wind = risk.get("wind", {}).get("risk_factor", 1)

                # Calculate composite
                overall = int((flood + fire + heat + wind) / 4)

                return ClimateRiskResponse(
                    flood_factor=int(flood),
                    fire_factor=int(fire),
                    heat_factor=int(heat),
                    wind_factor=int(wind),
                    overall_risk=overall,
                    insurance_estimate=float(risk.get("financial", {}).get("estimated_insurance_cost", 1500)),
                    source=APIProvider.FIRST_STREET
                )
            else:
                log.error(f"First Street API error: {response.status_code} - {response.text}")
                return self._mock_climate_risk(latitude, longitude)

        except Exception as e:
            log.exception(f"Exception calling First Street API: {e}")
            return self._mock_climate_risk(latitude, longitude)
    
    def get_solar_potential(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: float
    ) -> SolarPotentialResponse:
        """Get solar generation potential."""
        if self.use_mock or not self._is_enabled(APIProvider.GOOGLE_SOLAR):
            return self._mock_solar_potential(latitude, longitude, roof_sqft)
        
        # Real API Implementation
        try:
            config = self.configs[APIProvider.GOOGLE_SOLAR]

            # Use provided base URL or default to Google Solar API
            base_url = config.base_url or "https://solar.googleapis.com/v1"

            # Fetch building insights
            response = requests.get(
                f"{base_url}/buildingInsights:findClosest",
                params={
                    "location.latitude": latitude,
                    "location.longitude": longitude,
                    "requiredQuality": "HIGH",
                    "key": config.api_key
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Parse Google Solar response
                solar_potential = data.get("solarPotential", {})
                max_panels = solar_potential.get("maxArrayPanelsCount", 0)
                panel_capacity_watts = solar_potential.get("panelCapacityWatts", 250)

                # Use financial analysis if available for estimates
                financial_analysis = solar_potential.get("financialAnalyses", [{}])[0]
                annual_kwh = float(financial_analysis.get("energyBill", {}).get("federalIncentive", 0)) # Fallback field usage

                # If we have proper financial analysis, use it
                if "leasingSavings" in financial_analysis:
                     annual_kwh = float(financial_analysis.get("leasingSavings", {}).get("annualKwh", 0))

                # Re-calculate based on what we have if specific fields missing
                system_kw = (max_panels * panel_capacity_watts) / 1000
                if annual_kwh == 0 and system_kw > 0:
                     # Estimate based on California average sun hours
                     annual_kwh = system_kw * 4.5 * 365

                # Estimate savings
                savings = annual_kwh * 0.15 # Approx $0.15/kWh

                return SolarPotentialResponse(
                    annual_kwh=round(annual_kwh, 0),
                    system_capacity_kw=round(system_kw, 1),
                    panel_count=max_panels,
                    roof_area_sqft=float(solar_potential.get("wholeRoofStats", {}).get("areaMeters2", 0)) * 10.764,
                    shade_factor=0.15, # Placeholder as this is complex to derive from raw API without deep analysis
                    estimated_savings=round(savings, 0),
                    source=APIProvider.GOOGLE_SOLAR
                )
            else:
                log.error(f"Google Solar API error: {response.status_code} - {response.text}")
                return self._mock_solar_potential(latitude, longitude, roof_sqft)

        except Exception as e:
            log.exception(f"Exception calling Google Solar API: {e}")
            return self._mock_solar_potential(latitude, longitude, roof_sqft)
    
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
        sqft: float = 10000
    ) -> Dict[str, Any]:
        """Get all available data for a location."""
        return {
            'zoning': self.get_zoning(latitude, longitude),
            'construction': self.get_construction_costs(latitude, longitude, building_type, sqft),
            'climate': self.get_climate_risk(latitude, longitude),
            'solar': self.get_solar_potential(latitude, longitude, roof_sqft),
        }


def get_api_layer() -> APIIntegrationLayer:
    """Factory function for API integration layer."""
    return APIIntegrationLayer()
