"""
API Integration Layer - External data source integrations.

Provides unified interface to external APIs for zoning, construction costs,
environmental risk, and solar potential. Uses mock data in development.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import random


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
        
        # TODO: Implement real 1build/RSMeans API call
        return self._mock_construction_costs(latitude, longitude, building_type, sqft)
    
    def get_climate_risk(
        self,
        latitude: float,
        longitude: float
    ) -> ClimateRiskResponse:
        """Get climate risk assessment."""
        if self.use_mock or not self._is_enabled(APIProvider.FIRST_STREET):
            return self._mock_climate_risk(latitude, longitude)
        
        # TODO: Implement real First Street Foundation API call
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
        
        # TODO: Implement real Google Solar API call
        return self._mock_solar_potential(latitude, longitude, roof_sqft)
    
    def _is_enabled(self, provider: APIProvider) -> bool:
        """Check if a provider is enabled."""
        config = self.configs.get(provider)
        return config and config.enabled and config.api_key
    
    def _mock_zoning(self, lat: float, lon: float) -> ZoningAPIResponse:
        """Generate mock zoning data."""
        random.seed(int(abs(lat * 1000) + abs(lon * 1000)))
        
        zones = [
            ("R-1", "Single Family Residential", ["single_family", "adu"]),
            ("R-2", "Two-Family Residential", ["single_family", "duplex", "adu"]),
            ("R-3", "Multi-Family Residential", ["apartment", "condo", "mixed_use"]),
            ("C-1", "Neighborhood Commercial", ["retail", "restaurant", "office"]),
            ("C-2", "Community Commercial", ["retail", "office", "hotel", "entertainment"]),
        ]
        
        zone = random.choice(zones)
        
        return ZoningAPIResponse(
            zone_code=zone[0],
            zone_name=zone[1],
            allowed_uses=zone[2],
            max_height_ft=random.choice([30, 35, 45, 55, 65]),
            max_far=random.choice([0.5, 0.6, 1.0, 1.5, 2.0]),
            max_lot_coverage=random.choice([0.4, 0.45, 0.5, 0.6]),
            setbacks={
                'front': random.choice([15, 20, 25]),
                'side': random.choice([5, 7, 10]),
                'rear': random.choice([10, 15, 20]),
            },
            parking_ratio=random.choice([1.0, 1.5, 2.0]),
            overlay_districts=random.choice([[], ["TOD"], ["Historic"]]),
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
        random.seed(int(abs(lat * 1000) + abs(lon * 1000)))
        
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
        
        cost_per_sqft = base * location_factor * random.uniform(0.9, 1.1)
        
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
        random.seed(int(abs(lat * 1000) + abs(lon * 1000)))
        
        # Coastal = flood risk, California = fire risk, South = heat
        is_coastal = abs(lon) > 120
        is_california = -125 < lon < -114 and 32 < lat < 42
        is_southern = lat < 38
        
        flood = random.randint(1, 4) + (3 if is_coastal else 0)
        fire = random.randint(1, 4) + (4 if is_california else 0)
        heat = random.randint(2, 5) + (3 if is_southern else 0)
        wind = random.randint(2, 6)
        
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
