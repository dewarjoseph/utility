import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to the path so we can import core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.api_layer import (
    APIIntegrationLayer,
    APIProvider,
    ZoningAPIResponse,
    ConstructionCostResponse,
    ClimateRiskResponse,
    SolarPotentialResponse
)

class TestAPIIntegrationLayer(unittest.TestCase):
    def setUp(self):
        # Reset environment variables to ensure clean state
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()
        self.api_layer = APIIntegrationLayer()

    def tearDown(self):
        self.env_patcher.stop()

    def test_initialization(self):
        """Test that the API layer initializes with mock data enabled by default."""
        self.assertTrue(self.api_layer.use_mock)
        for provider in APIProvider:
            self.assertIn(provider, self.api_layer.configs)

    def test_mock_zoning(self):
        """Test retrieving mock zoning data."""
        response = self.api_layer.get_zoning(36.9741, -122.0308)
        self.assertIsInstance(response, ZoningAPIResponse)
        self.assertEqual(response.source, APIProvider.GRIDICS)
        self.assertIsNotNone(response.zone_code)
        self.assertIsNotNone(response.allowed_uses)

    def test_mock_construction_costs(self):
        """Test retrieving mock construction costs."""
        response = self.api_layer.get_construction_costs(36.9741, -122.0308, 'wood_frame', 1000)
        self.assertIsInstance(response, ConstructionCostResponse)
        self.assertEqual(response.source, APIProvider.ONEBUILD)
        self.assertGreater(response.total_estimate, 0)

    def test_mock_climate_risk(self):
        """Test retrieving mock climate risk data."""
        response = self.api_layer.get_climate_risk(36.9741, -122.0308)
        self.assertIsInstance(response, ClimateRiskResponse)
        self.assertEqual(response.source, APIProvider.FIRST_STREET)
        self.assertGreaterEqual(response.overall_risk, 0)
        self.assertLessEqual(response.overall_risk, 10)

    def test_mock_solar_potential(self):
        """Test retrieving mock solar potential data."""
        response = self.api_layer.get_solar_potential(36.9741, -122.0308, 2000)
        self.assertIsInstance(response, SolarPotentialResponse)
        self.assertEqual(response.source, APIProvider.GOOGLE_SOLAR)
        self.assertGreater(response.annual_kwh, 0)

    def test_configure_provider(self):
        """Test configuring a provider enables it and disables global mock."""
        self.api_layer.configure(APIProvider.GRIDICS, "test_key")
        self.assertFalse(self.api_layer.use_mock)
        config = self.api_layer.configs[APIProvider.GRIDICS]
        self.assertTrue(config.enabled)
        self.assertEqual(config.api_key, "test_key")

    @patch('requests.get')
    def test_real_gridics_api(self, mock_get):
        """Test parsing of real Gridics API response."""
        # Enable Gridics
        self.api_layer.configure(APIProvider.GRIDICS, "fake_key")

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "parcel": {
                "zoning": {
                    "code": "R-1",
                    "name": "Single Family",
                    "allowed_uses": ["residential"],
                    "constraints": {
                        "max_height_ft": 30,
                        "max_far": 0.5,
                        "max_lot_coverage": 0.4
                    },
                    "setbacks": {"front": 20, "side": 5, "rear": 10},
                    "parking": {"ratio": 2.0},
                    "overlays": ["Historic"]
                }
            }
        }
        mock_get.return_value = mock_response

        # Call method
        response = self.api_layer.get_zoning(36.9741, -122.0308)

        # Verify
        self.assertIsInstance(response, ZoningAPIResponse)
        self.assertEqual(response.zone_code, "R-1")
        self.assertEqual(response.max_height_ft, 30)
        self.assertEqual(response.setbacks['front'], 20)
        self.assertEqual(response.source, APIProvider.GRIDICS)
        mock_get.assert_called_once()

    @patch('requests.post')
    def test_real_onebuild_api(self, mock_post):
        """Test parsing of real 1build API response."""
        # Enable 1build
        self.api_layer.configure(APIProvider.ONEBUILD, "fake_key")

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "estimate": {
                "cost_per_sqft": 200,
                "location_factor": 1.2,
                "total": 200000,
                "confidence_score": 0.9,
                "breakdown": {
                    "materials": {"lumber": 50000},
                    "labor": {"carpentry": 60000}
                }
            }
        }
        mock_post.return_value = mock_response

        # Call method
        response = self.api_layer.get_construction_costs(36.9741, -122.0308, "wood_frame", 1000)

        # Verify
        self.assertIsInstance(response, ConstructionCostResponse)
        self.assertEqual(response.total_estimate, 200000)
        self.assertEqual(response.cost_per_sqft, 200)
        self.assertEqual(response.source, APIProvider.ONEBUILD)
        mock_post.assert_called_once()

    @patch('requests.get')
    def test_real_first_street_api(self, mock_get):
        """Test parsing of real First Street API response."""
        # Enable First Street
        self.api_layer.configure(APIProvider.FIRST_STREET, "fake_key")

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "risk": {
                "flood": {"risk_factor": 2},
                "fire": {"risk_factor": 5},
                "heat": {"risk_factor": 8},
                "wind": {"risk_factor": 1},
                "financial": {"estimated_insurance_cost": 2000}
            }
        }
        mock_get.return_value = mock_response

        # Call method
        response = self.api_layer.get_climate_risk(36.9741, -122.0308)

        # Verify
        self.assertIsInstance(response, ClimateRiskResponse)
        self.assertEqual(response.flood_factor, 2)
        self.assertEqual(response.fire_factor, 5)
        self.assertEqual(response.overall_risk, 4) # (2+5+8+1)/4 = 4
        self.assertEqual(response.insurance_estimate, 2000)
        self.assertEqual(response.source, APIProvider.FIRST_STREET)
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_real_google_solar_api(self, mock_get):
        """Test parsing of real Google Solar API response."""
        # Enable Google Solar
        self.api_layer.configure(APIProvider.GOOGLE_SOLAR, "fake_key")

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "solarPotential": {
                "maxArrayPanelsCount": 20,
                "panelCapacityWatts": 300,
                "wholeRoofStats": {"areaMeters2": 100},
                "financialAnalyses": [{
                    "leasingSavings": {"annualKwh": 8000}
                }]
            }
        }
        mock_get.return_value = mock_response

        # Call method
        response = self.api_layer.get_solar_potential(36.9741, -122.0308, 1000)

        # Verify
        self.assertIsInstance(response, SolarPotentialResponse)
        self.assertEqual(response.annual_kwh, 8000)
        self.assertEqual(response.panel_count, 20)
        self.assertEqual(response.system_capacity_kw, 6.0) # (20 * 300) / 1000
        self.assertEqual(response.source, APIProvider.GOOGLE_SOLAR)
        mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()
