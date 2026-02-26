import unittest
from unittest.mock import MagicMock, patch, Mock
import os
import json
from core.onebuild_client import OneBuildClient, OneBuildItem

class TestOneBuildClient(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_key"
        self.client = OneBuildClient(api_key=self.api_key)

    def test_init_with_env_var(self):
        with patch.dict(os.environ, {"ONEBUILD_API_KEY": "env_key"}):
            client = OneBuildClient()
            self.assertEqual(client.api_key, "env_key")
            self.assertTrue(client.is_configured())

    def test_init_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            client = OneBuildClient()
            self.assertIsNone(client.api_key)
            self.assertFalse(client.is_configured())

    @patch("requests.post")
    def test_execute_query_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"search": {"edges": []}}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.client._execute_query("query { foo }")
        self.assertEqual(result, {"search": {"edges": []}})
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_execute_query_error(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"errors": [{"message": "Bad query"}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with self.assertRaises(Exception) as cm:
            self.client._execute_query("query { foo }")
        self.assertIn("GraphQL Error", str(cm.exception))

    def test_execute_query_no_key(self):
        client = OneBuildClient()
        with self.assertRaises(ValueError):
            client._execute_query("query")

    @patch("core.onebuild_client.OneBuildClient._execute_query")
    def test_get_cost_data(self, mock_execute):
        # Setup mock return for search
        # We need to handle multiple calls since get_cost_data iterates
        def side_effect(query, variables):
            term = variables['query']
            price = 10.0
            category = "material"
            if "Labor" in term:
                category = "labor"
                price = 50.0

            return {
                "search": {
                    "edges": [{
                        "node": {
                            "id": "123",
                            "name": term,
                            "unit": "each",
                            "price": {"amount": price, "currency": "USD"},
                            "category": {"name": category}
                        }
                    }]
                }
            }

        mock_execute.side_effect = side_effect

        items = self.client.get_cost_data("wood_frame")

        self.assertTrue(len(items) > 0)
        self.assertIsInstance(items[0], OneBuildItem)
        self.assertTrue(any(i.category == 'material' for i in items))
        self.assertTrue(any(i.category == 'labor' for i in items))

    @patch("core.onebuild_client.OneBuildClient._execute_query")
    def test_get_cost_data_partial_failure(self, mock_execute):
        # First call succeeds, second fails
        mock_execute.side_effect = [
            {"search": {"edges": [{"node": {"id": "1", "name": "Item 1", "unit": "ea", "price": {"amount": 10}, "category": {"name": "mat"}}}]}},
            Exception("Network error"),
            {"search": {"edges": [{"node": {"id": "2", "name": "Item 2", "unit": "ea", "price": {"amount": 20}, "category": {"name": "mat"}}}]}}
        ]

        # We need to make sure _get_search_terms returns at least 3 items for this test
        # wood_frame returns > 3 items
        items = self.client.get_cost_data("wood_frame")

        # Should have results despite the middle failure
        self.assertTrue(len(items) > 0)

if __name__ == '__main__':
    unittest.main()
