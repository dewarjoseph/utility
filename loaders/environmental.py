"""
Environmental Risk Loader - Climate and hazard risk assessment.

Provides flood, fire, and climate risk scoring for parcels.
Mock data for development, with First Street Foundation API integration points.
"""

import random
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class RiskLevel(Enum):
    """Risk level classifications."""
    MINIMAL = 1
    MINOR = 2
    MODERATE = 3
    MAJOR = 4
    SEVERE = 5
    EXTREME = 6


@dataclass
class FloodRisk:
    """Flood risk assessment."""
    factor: int  # 1-10 scale
    level: RiskLevel
    annual_probability: float  # % chance per year
    fema_zone: str  # A, AE, X, etc.
    projected_2050: int  # Future risk factor

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor': self.factor,
            'level': self.level.name,
            'annual_probability': self.annual_probability,
            'fema_zone': self.fema_zone,
            'projected_2050': self.projected_2050,
        }


@dataclass
class FireRisk:
    """Wildfire risk assessment."""
    factor: int  # 1-10 scale
    level: RiskLevel
    burn_probability: float
    wui_zone: bool  # Wildland-Urban Interface
    defensible_space_required: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor': self.factor,
            'level': self.level.name,
            'burn_probability': self.burn_probability,
            'wui_zone': self.wui_zone,
            'defensible_space_required': self.defensible_space_required,
        }


@dataclass
class HeatRisk:
    """Extreme heat risk assessment."""
    factor: int  # 1-10 scale
    hot_days_per_year: int  # Days over 100°F
    projected_2050_hot_days: int
    cooling_degree_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'factor': self.factor,
            'hot_days_per_year': self.hot_days_per_year,
            'projected_2050_hot_days': self.projected_2050_hot_days,
            'cooling_degree_days': self.cooling_degree_days,
        }


@dataclass
class EnvironmentalRiskProfile:
    """Complete environmental risk profile for a location."""
    flood: FloodRisk
    fire: FireRisk
    heat: HeatRisk
    overall_score: int  # 1-10 composite
    insurance_impact_pct: float  # % increase to base insurance
    solar_potential_kwh: float  # Annual kWh generation potential

    def to_dict(self) -> Dict[str, Any]:
        return {
            'flood': self.flood.to_dict(),
            'fire': self.fire.to_dict(),
            'heat': self.heat.to_dict(),
            'overall_score': self.overall_score,
            'insurance_impact_pct': self.insurance_impact_pct,
            'solar_potential_kwh': self.solar_potential_kwh,
        }


def _factor_to_level(factor: int) -> RiskLevel:
    """Convert 1-10 factor to risk level."""
    if factor <= 2:
        return RiskLevel.MINIMAL
    elif factor <= 4:
        return RiskLevel.MINOR
    elif factor <= 6:
        return RiskLevel.MODERATE
    elif factor <= 8:
        return RiskLevel.MAJOR
    elif factor <= 9:
        return RiskLevel.SEVERE
    return RiskLevel.EXTREME


class EnvironmentalRiskLoader:
    """
    Environmental risk data loader.
    
    Future integration points:
    - First Street Foundation API (flood, fire, heat)
    - Google Solar API (solar potential)
    - FEMA flood maps
    """

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self._cache: Dict[str, EnvironmentalRiskProfile] = {}

    def get_risk_profile(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: Optional[float] = None
    ) -> EnvironmentalRiskProfile:
        """Get complete environmental risk profile for a location."""
        cache_key = f"{latitude:.6f},{longitude:.6f}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_mock:
            profile = self._generate_mock_profile(latitude, longitude, roof_sqft)
        else:
            profile = self._fetch_from_apis(latitude, longitude, roof_sqft)

        self._cache[cache_key] = profile
        return profile

    def _generate_mock_profile(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: Optional[float] = None
    ) -> EnvironmentalRiskProfile:
        """Generate realistic mock risk data based on location."""
        random.seed(int(abs(latitude * 10000) + abs(longitude * 10000)))

        # Coastal/low elevation = higher flood risk
        is_coastal = abs(longitude) > 120 or abs(latitude) < 35
        
        # California = higher fire risk
        is_california = -125 < longitude < -114 and 32 < latitude < 42
        
        # Southern = higher heat risk
        is_southern = latitude < 38

        # Flood risk
        flood_factor = random.randint(1, 4) + (3 if is_coastal else 0)
        flood_factor = min(10, flood_factor)
        fema_zones = ['X', 'X', 'X', 'AE', 'A', 'VE']
        
        flood = FloodRisk(
            factor=flood_factor,
            level=_factor_to_level(flood_factor),
            annual_probability=flood_factor * 0.5,
            fema_zone=random.choice(fema_zones[:4 if flood_factor < 5 else 6]),
            projected_2050=min(10, flood_factor + random.randint(1, 2)),
        )

        # Fire risk
        fire_factor = random.randint(1, 4) + (4 if is_california else 0)
        fire_factor = min(10, fire_factor)
        
        fire = FireRisk(
            factor=fire_factor,
            level=_factor_to_level(fire_factor),
            burn_probability=fire_factor * 0.3,
            wui_zone=fire_factor > 5,
            defensible_space_required=fire_factor > 6,
        )

        # Heat risk
        heat_factor = random.randint(2, 5) + (3 if is_southern else 0)
        heat_factor = min(10, heat_factor)
        base_hot_days = 5 + heat_factor * 3
        
        heat = HeatRisk(
            factor=heat_factor,
            hot_days_per_year=base_hot_days,
            projected_2050_hot_days=int(base_hot_days * 1.5),
            cooling_degree_days=500 + heat_factor * 200,
        )

        # Overall score (weighted average)
        overall = int((flood_factor * 0.4 + fire_factor * 0.35 + heat_factor * 0.25))

        # Insurance impact (higher risk = higher premiums)
        insurance_impact = (overall - 3) * 5  # 5% per point above 3
        insurance_impact = max(0, insurance_impact)

        # Solar potential (based on latitude and heat/sun correlation)
        base_solar = 1200  # kWh per kW installed
        lat_factor = 1.0 + (40 - abs(latitude)) * 0.01
        sun_factor = 1.0 + heat_factor * 0.05
        solar_per_sqft = 15  # Watts per sqft
        roof = roof_sqft or 1500
        system_kw = (roof * 0.7 * solar_per_sqft) / 1000  # 70% usable roof
        solar_kwh = base_solar * lat_factor * sun_factor * system_kw

        return EnvironmentalRiskProfile(
            flood=flood,
            fire=fire,
            heat=heat,
            overall_score=overall,
            insurance_impact_pct=insurance_impact,
            solar_potential_kwh=round(solar_kwh, 0),
        )

    def _fetch_from_apis(
        self,
        latitude: float,
        longitude: float,
        roof_sqft: Optional[float] = None
    ) -> EnvironmentalRiskProfile:
        """Fetch from real APIs (TODO: implement)."""
        return self._generate_mock_profile(latitude, longitude, roof_sqft)

    def calculate_insurance_adjustment(
        self,
        base_premium: float,
        risk_profile: EnvironmentalRiskProfile
    ) -> Dict[str, float]:
        """Calculate adjusted insurance based on risk."""
        flood_adj = base_premium * (risk_profile.flood.factor / 10) * 0.3
        fire_adj = base_premium * (risk_profile.fire.factor / 10) * 0.25
        
        return {
            'base_premium': base_premium,
            'flood_adjustment': flood_adj,
            'fire_adjustment': fire_adj,
            'total_premium': base_premium + flood_adj + fire_adj,
            'annual_increase': (flood_adj + fire_adj) / base_premium * 100,
        }


def get_environmental_loader(use_mock: bool = True) -> EnvironmentalRiskLoader:
    """Factory function for environmental risk loader."""
    return EnvironmentalRiskLoader(use_mock=use_mock)
