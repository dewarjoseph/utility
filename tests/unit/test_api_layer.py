import unittest
from unittest.mock import MagicMock, patch
from core.api_layer import APIIntegrationLayer, APIProvider, ConstructionCostResponse
from core.onebuild_client import OneBuildClient, OneBuildItem

class TestAPIIntegrationLayer(unittest.TestCase):

    def setUp(self):
        self.api_layer = APIIntegrationLayer()
        self.api_layer.configure(APIProvider.ONEBUILD, api_key="test_key", enabled=True)

    def test_get_construction_costs_mock(self):
        # Force mock mode
        self.api_layer.use_mock = True
        response = self.api_layer.get_construction_costs(37.77, -122.41, 'wood_frame', 1000)
        self.assertIsInstance(response, ConstructionCostResponse)
        self.assertEqual(response.source, APIProvider.ONEBUILD) # Mock still uses provider enum

    @patch("core.api_layer.OneBuildClient")
    def test_get_construction_costs_real_success(self, mock_client_cls):
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.is_configured.return_value = True

        # Return fake items
        items = [
            OneBuildItem(id="1", name="Lumber", unit="ea", price=50.0, category="material"),
            OneBuildItem(id="2", name="Labor", unit="hr", price=100.0, category="labor")
        ]
        mock_client.get_cost_data.return_value = items

        self.api_layer.use_mock = False # Enable real API calls

        response = self.api_layer.get_construction_costs(37.77, -122.41, 'wood_frame', 1000)

        self.assertIsInstance(response, ConstructionCostResponse)
        self.assertEqual(response.source, APIProvider.ONEBUILD)

        # 50+100 = 150.
        self.assertAlmostEqual(response.cost_per_sqft, 150.0, delta=1.0)
        self.assertAlmostEqual(response.total_estimate, 150000.0, delta=1000.0)

    @patch("core.api_layer.OneBuildClient")
    def test_get_construction_costs_real_fallback(self, mock_client_cls):
        # API fails/returns empty
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.is_configured.return_value = True
        mock_client.get_cost_data.return_value = [] # Empty result

        self.api_layer.use_mock = False

        response = self.api_layer.get_construction_costs(37.77, -122.41, 'wood_frame', 1000)

        # Should return mock data as fallback
        self.assertIsInstance(response, ConstructionCostResponse)
        self.assertEqual(response.source, APIProvider.ONEBUILD)
        # Mock data is usually around ~200 * location factor
        self.assertGreater(response.cost_per_sqft, 0)

    @patch("core.api_layer.OneBuildClient")
    def test_get_construction_costs_client_error(self, mock_client_cls):
        # Client raises exception
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.is_configured.return_value = True
        mock_client.get_cost_data.side_effect = Exception("API Error")

        self.api_layer.use_mock = False

        response = self.api_layer.get_construction_costs(37.77, -122.41, 'wood_frame', 1000)

        # Should catch and return mock data
        self.assertIsInstance(response, ConstructionCostResponse)

if __name__ == '__main__':
    unittest.main()
