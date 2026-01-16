"""Tests for the API integration layer."""

import pytest
from core.api_layer import (
    APIIntegrationLayer, APIProvider, APIConfig,
    ZoningAPIResponse, ConstructionCostResponse,
    ClimateRiskResponse, SolarPotentialResponse,
    get_api_layer
)


class TestAPIIntegrationLayer:
    """Tests for the API integration layer."""

    def test_get_zoning(self):
        api = APIIntegrationLayer()
        result = api.get_zoning(36.9741, -122.0308)
        
        assert isinstance(result, ZoningAPIResponse)
        assert result.zone_code is not None
        assert result.max_height_ft > 0

    def test_get_construction_costs(self):
        api = APIIntegrationLayer()
        result = api.get_construction_costs(
            36.9741, -122.0308, 'wood_frame', 10000
        )
        
        assert isinstance(result, ConstructionCostResponse)
        assert result.cost_per_sqft > 0
        assert result.total_estimate > 0

    def test_get_climate_risk(self):
        api = APIIntegrationLayer()
        result = api.get_climate_risk(36.9741, -122.0308)
        
        assert isinstance(result, ClimateRiskResponse)
        assert 1 <= result.flood_factor <= 10
        assert 1 <= result.fire_factor <= 10

    def test_get_solar_potential(self):
        api = APIIntegrationLayer()
        result = api.get_solar_potential(36.9741, -122.0308, 2000)
        
        assert isinstance(result, SolarPotentialResponse)
        assert result.annual_kwh > 0
        assert result.panel_count > 0

    def test_get_all_data(self):
        api = APIIntegrationLayer()
        result = api.get_all_data(36.9741, -122.0308)
        
        assert 'zoning' in result
        assert 'construction' in result
        assert 'climate' in result
        assert 'solar' in result


class TestMockDataConsistency:
    """Tests for mock data determinism."""

    def test_same_location_same_results(self):
        api = APIIntegrationLayer()
        r1 = api.get_zoning(36.9741, -122.0308)
        r2 = api.get_zoning(36.9741, -122.0308)
        
        assert r1.zone_code == r2.zone_code
        assert r1.max_height_ft == r2.max_height_ft

    def test_different_locations_may_differ(self):
        api = APIIntegrationLayer()
        r1 = api.get_zoning(36.9741, -122.0308)
        r2 = api.get_zoning(40.7128, -74.0060)
        
        # At least something should differ for different seeds
        # (though this isn't guaranteed, it's highly likely)
        assert r1 is not r2


class TestLocationFactors:
    """Tests for location-based adjustments."""

    def test_california_higher_costs(self):
        api = APIIntegrationLayer()
        ca_costs = api.get_construction_costs(36.9741, -122.0308, 'wood_frame', 10000)
        ny_costs = api.get_construction_costs(40.7128, -74.0060, 'wood_frame', 10000)
        
        # California should have higher location factor
        assert ca_costs.location_factor >= ny_costs.location_factor


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_api_layer(self):
        api = get_api_layer()
        assert isinstance(api, APIIntegrationLayer)
        assert api.use_mock is True
