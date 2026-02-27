import unittest
from unittest.mock import MagicMock, patch
from core.api_layer import APIIntegrationLayer, APIProvider, ClimateRiskResponse

class TestAPIIntegrationLayer(unittest.TestCase):
    def setUp(self):
        self.api = APIIntegrationLayer()

    @patch('core.api_layer.requests.post')
    def test_get_first_street_risk_success_with_filtering(self, mock_post):
        # Configure API
        self.api.configure(APIProvider.FIRST_STREET, api_key="test_key")

        # Mock response data with multiple scenarios to test filtering
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "placeByCoordinate": {
                    "placeId": "12345",
                    "flood": {
                        "data": {
                            "floodFactors": [
                                {"floodFactor": 90, "ssp": "SSP_5_85", "relativeYear": 30},
                                {"floodFactor": 20, "ssp": "SSP_2_45", "relativeYear": 0}, # Match
                            ],
                            "floodDamages": {
                                "aal": [
                                    {"aal": 1000, "ssp": "SSP_5_85", "relativeYear": 30},
                                    {"aal": 100, "ssp": "SSP_2_45", "relativeYear": 0}, # Match
                                ]
                            }
                        }
                    },
                    "wildfire": {
                        "data": {
                            "fireFactors": [
                                {"fireFactor": 30, "ssp": "SSP_2_45", "relativeYear": 0}, # Match
                            ],
                            "wildfireDamages": {"aal": [{"aal": 200, "ssp": "SSP_2_45", "relativeYear": 0}]}
                        }
                    },
                    "heat": {
                        "data": {
                            "heatFactors": [{"heatFactor": 50, "ssp": "SSP_2_45", "relativeYear": 0}] # Match
                        }
                    },
                    "wind": {
                        "data": {
                            "windFactors": [{"windFactor": 45, "ssp": "SSP_2_45", "relativeYear": 0}], # Match
                            "windDamages": {"aal": [{"aal": 50, "ssp": "SSP_2_45", "relativeYear": 0}]}
                        }
                    }
                }
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call method
        result = self.api.get_climate_risk(34.05, -118.25)

        # Verify calls
        mock_post.assert_called_once()

        # Verify result
        self.assertIsInstance(result, ClimateRiskResponse)
        self.assertEqual(result.flood_factor, 2) # Should pick 20, normalize to 2
        self.assertEqual(result.fire_factor, 3)
        self.assertEqual(result.heat_factor, 5)
        self.assertEqual(result.wind_factor, 5)
        self.assertEqual(result.source, APIProvider.FIRST_STREET)

        # Verify insurance calculation
        # Total AAL = 100 + 200 + 50 = 350
        self.assertEqual(result.insurance_estimate, 1025)

    @patch('core.api_layer.requests.post')
    def test_get_first_street_risk_low_values(self, mock_post):
        # Configure API
        self.api.configure(APIProvider.FIRST_STREET, api_key="test_key")

        # Mock response data with low values (1-10 range on 100 scale)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "placeByCoordinate": {
                    "placeId": "12345",
                    "flood": {
                        "data": {
                            "floodFactors": [{"floodFactor": 5, "ssp": "SSP_2_45", "relativeYear": 0}],
                            "floodDamages": {"aal": [{"aal": 10, "ssp": "SSP_2_45", "relativeYear": 0}]}
                        }
                    },
                    "wildfire": {
                        "data": {
                            "fireFactors": [{"fireFactor": 10, "ssp": "SSP_2_45", "relativeYear": 0}],
                            "wildfireDamages": {"aal": [{"aal": 20, "ssp": "SSP_2_45", "relativeYear": 0}]}
                        }
                    },
                    "heat": {
                        "data": {
                            "heatFactors": [{"heatFactor": 1, "ssp": "SSP_2_45", "relativeYear": 0}]
                        }
                    },
                    "wind": {
                        "data": {
                            "windFactors": [{"windFactor": 11, "ssp": "SSP_2_45", "relativeYear": 0}],
                            "windDamages": {"aal": [{"aal": 5, "ssp": "SSP_2_45", "relativeYear": 0}]}
                        }
                    }
                }
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call method
        result = self.api.get_climate_risk(34.05, -118.25)

        # Verify normalization
        self.assertEqual(result.flood_factor, 1) # ceil(5/10) = 1
        self.assertEqual(result.fire_factor, 1)  # ceil(10/10) = 1
        self.assertEqual(result.heat_factor, 1)  # ceil(1/10) = 1
        self.assertEqual(result.wind_factor, 2)  # ceil(11/10) = 2

    @patch('core.api_layer.requests.post')
    def test_get_first_street_risk_failure_fallback(self, mock_post):
        # Configure API
        self.api.configure(APIProvider.FIRST_STREET, api_key="test_key")

        # Mock failure
        mock_post.side_effect = Exception("API connection failed")

        # Call method - should catch exception and return mock
        with self.assertLogs('core.api_layer', level='ERROR') as cm:
            result = self.api.get_climate_risk(34.05, -118.25)

        # Verify logs
        self.assertTrue(any("First Street API failed" in output for output in cm.output))

        # Verify result is mock data
        self.assertIsInstance(result, ClimateRiskResponse)

    def test_get_climate_risk_mock_when_disabled(self):
        # API not configured/enabled
        result = self.api.get_climate_risk(34.05, -118.25)
        self.assertIsInstance(result, ClimateRiskResponse)
        # Should be deterministic mock
        self.assertEqual(result.source, APIProvider.FIRST_STREET)

if __name__ == '__main__':
    unittest.main()
