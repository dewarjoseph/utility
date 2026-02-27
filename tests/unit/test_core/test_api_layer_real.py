"""Tests for the API integration layer with Real Google Solar API Logic (Mocked)."""

import pytest
from unittest.mock import MagicMock, patch
import sys

# We need to make sure core.api_layer has solar_v1 defined for our tests to work,
# even if the import failed in the actual module.
# We can do this by patching the module attribute.

from core.api_layer import (
    APIIntegrationLayer, APIProvider, SolarPotentialResponse,
    get_api_layer
)
import core.api_layer

class TestAPIIntegrationLayerRealSolar:
    """Tests for the API integration layer specifically for Google Solar."""

    @pytest.fixture
    def api_layer(self):
        return APIIntegrationLayer()

    def test_get_solar_potential_mock_default(self, api_layer):
        """Test that default behavior is to use mock data."""
        # Ensure _get_solar_client returns None (default behavior if no API key)
        with patch.object(api_layer, '_get_solar_client', return_value=None):
             result = api_layer.get_solar_potential(36.9741, -122.0308, 2000)

        assert isinstance(result, SolarPotentialResponse)
        assert result.source == APIProvider.GOOGLE_SOLAR
        # Check standard mock values logic
        assert result.annual_kwh > 0
        assert result.estimated_savings > 0

    def test_get_solar_potential_real_api(self, api_layer):
        """Test real API integration with mocked Google client."""
        # Create a mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_potential = MagicMock()

        # Set up mock data
        mock_potential.max_array_panels_count = 20
        mock_potential.max_array_area_meters2 = 40.0
        mock_potential.max_sunshine_hours_per_year = 1500.0
        mock_potential.panel_capacity_watts = 400.0

        mock_response.solar_potential = mock_potential
        mock_client.find_closest_building_insights.return_value = mock_response

        # Mock solar_v1 on the module level so FindClosestBuildingInsightsRequest works
        mock_solar_v1 = MagicMock()

        # Patch both the client getter AND the module attribute
        with patch.object(api_layer, '_get_solar_client', return_value=mock_client), \
             patch.object(core.api_layer, 'solar_v1', mock_solar_v1, create=True):

            # Configure API to ensure internal state is enabled
            api_layer.configure(APIProvider.GOOGLE_SOLAR, "fake_key", enabled=True)

            # Call method
            result = api_layer.get_solar_potential(36.9741, -122.0308, 2000, electricity_rate=0.20)

            # Verify API call
            mock_client.find_closest_building_insights.assert_called_once()

            # Verify Result Calculation
            # Capacity: 20 panels * 400W = 8000W = 8.0 kW
            expected_capacity = 8.0
            # Annual kWh: 8.0 kW * 1500 hours * 0.8 efficiency = 9600 kWh
            expected_kwh = 9600.0
            # Savings: 9600 kWh * $0.20 = $1920
            expected_savings = 1920.0
            # Area: 40 m2 * 10.7639 = 430.556 sqft
            expected_area = 430.6

            assert result.system_capacity_kw == expected_capacity
            assert result.annual_kwh == expected_kwh
            assert result.estimated_savings == expected_savings
            assert result.panel_count == 20
            assert result.source == APIProvider.GOOGLE_SOLAR

    def test_get_solar_potential_api_error_fallback(self, api_layer):
        """Test fallback to mock data on API error."""
        # Create a mock client that raises an exception
        mock_client = MagicMock()
        mock_client.find_closest_building_insights.side_effect = Exception("API Error")

        mock_solar_v1 = MagicMock()

        # Mock _get_solar_client to return our failing client
        with patch.object(api_layer, '_get_solar_client', return_value=mock_client), \
             patch.object(core.api_layer, 'solar_v1', mock_solar_v1, create=True):

            # Configure API
            api_layer.configure(APIProvider.GOOGLE_SOLAR, "fake_key", enabled=True)

            # Call method
            result = api_layer.get_solar_potential(36.9741, -122.0308, 2000)

            # Verify it fell back to mock data
            assert isinstance(result, SolarPotentialResponse)
            # Verify fallback results (should be non-mock objects)
            assert isinstance(result.annual_kwh, (int, float))
            assert result.annual_kwh > 0

    def test_get_all_data_passes_rate(self, api_layer):
        """Test that electricity rate is passed through get_all_data."""
        # Use a mock for get_solar_potential to verify arguments
        with patch.object(api_layer, 'get_solar_potential') as mock_get_solar:
            api_layer.get_all_data(36.9741, -122.0308, electricity_rate=0.25)

            mock_get_solar.assert_called_with(36.9741, -122.0308, 2000, 0.25)
