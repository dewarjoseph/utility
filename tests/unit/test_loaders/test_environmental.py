"""Tests for the environmental risk loader."""

import pytest
from loaders.environmental import (
    EnvironmentalRiskLoader, EnvironmentalRiskProfile, 
    FloodRisk, FireRisk, HeatRisk, RiskLevel,
    get_environmental_loader
)


class TestEnvironmentalRiskLoader:
    """Tests for environmental risk assessment."""

    def test_get_risk_profile(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        profile = loader.get_risk_profile(36.9741, -122.0308)
        
        assert isinstance(profile, EnvironmentalRiskProfile)
        assert isinstance(profile.flood, FloodRisk)
        assert isinstance(profile.fire, FireRisk)
        assert isinstance(profile.heat, HeatRisk)

    def test_risk_factors_in_range(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        profile = loader.get_risk_profile(36.9741, -122.0308)
        
        assert 1 <= profile.flood.factor <= 10
        assert 1 <= profile.fire.factor <= 10
        assert 1 <= profile.heat.factor <= 10
        assert 1 <= profile.overall_score <= 10

    def test_profile_is_cached(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        p1 = loader.get_risk_profile(36.9741, -122.0308)
        p2 = loader.get_risk_profile(36.9741, -122.0308)
        
        assert p1 is p2

    def test_different_locations(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        p1 = loader.get_risk_profile(36.9741, -122.0308)  # Santa Cruz
        p2 = loader.get_risk_profile(40.7128, -74.0060)   # NYC
        
        assert p1 is not p2

    def test_solar_potential(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        profile = loader.get_risk_profile(36.9741, -122.0308, roof_sqft=2000)
        
        assert profile.solar_potential_kwh > 0

    def test_insurance_impact(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        profile = loader.get_risk_profile(36.9741, -122.0308)
        
        assert profile.insurance_impact_pct >= 0


class TestInsuranceCalculation:
    """Tests for insurance adjustment calculations."""

    def test_calculate_insurance_adjustment(self):
        loader = EnvironmentalRiskLoader(use_mock=True)
        profile = loader.get_risk_profile(36.9741, -122.0308)
        
        result = loader.calculate_insurance_adjustment(10000, profile)
        
        assert 'base_premium' in result
        assert 'total_premium' in result
        assert result['total_premium'] >= result['base_premium']


class TestFloodRisk:
    """Tests for flood risk data."""

    def test_flood_risk_to_dict(self):
        flood = FloodRisk(
            factor=5,
            level=RiskLevel.MODERATE,
            annual_probability=2.5,
            fema_zone='AE',
            projected_2050=7
        )
        d = flood.to_dict()
        
        assert d['factor'] == 5
        assert d['fema_zone'] == 'AE'
        assert 'projected_2050' in d


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_environmental_loader(self):
        loader = get_environmental_loader()
        assert isinstance(loader, EnvironmentalRiskLoader)
        assert loader.use_mock is True
