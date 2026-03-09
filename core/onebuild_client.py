"""
1Build API Client - Construction cost estimation.

Provides a client for interacting with the 1Build GraphQL API to fetch
construction cost data.
"""

import os
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:
    # Fallback for mock environments where tenacity might not be installed
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def stop_after_attempt(*args, **kwargs): return None
    def wait_exponential(*args, **kwargs): return None


@dataclass
class OneBuildItem:
    """Represents a construction item from 1Build."""
    id: str
    name: str
    unit: str
    price: float
    category: str  # 'material' or 'labor'


class OneBuildClient:
    """Client for the 1Build GraphQL API."""

    BASE_URL = "https://api.1build.com/graphql"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ONEBUILD_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        """Check if the client is configured with an API key."""
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
    def _execute_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the 1Build API."""
        if not self.is_configured():
            raise ValueError("1Build API key is not configured.")

        payload = {"query": query, "variables": variables or {}}
        response = requests.post(self.BASE_URL, json=payload, headers=self.headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL Error: {data['errors']}")

        return data.get("data", {})

    def get_cost_data(self, building_type: str, region_id: Optional[str] = None) -> List[OneBuildItem]:
        """
        Fetch representative cost data for a building type.

        Since 1Build is item-based, we map high-level building types to a list of
        representative search queries (assemblies/materials) to estimate costs.

        Args:
            building_type: The type of building (e.g., 'wood_frame', 'concrete').
            region_id: Optional 1Build region ID (defaults to US National Average if None).

        Returns:
            A list of OneBuildItem objects with pricing.
        """
        items: List[OneBuildItem] = []
        search_terms = self._get_search_terms(building_type)

        for term in search_terms:
            # We search for items and take the top result for each term
            # This uses the same variable names as the query definition
            query_str = """
            query SearchItems($query: String!, $regionId: ID) {
              search(query: $query, first: 1, regionId: $regionId) {
                edges {
                  node {
                    id
                    name
                    unit
                    price {
                      amount
                      currency
                    }
                    category {
                      name
                    }
                  }
                }
              }
            }
            """
            variables = {
                "query": term,
                "regionId": region_id
            }

            try:
                # In a real implementation, we would call the API here.
                # Since we don't have a real key to test against the live API,
                # and the schema is hypothetical based on public info,
                # we rely on the _execute_query method which handles the request.

                if self.is_configured():
                    result = self._execute_query(query_str, variables)
                    edges = result.get("search", {}).get("edges", [])
                    if edges:
                        node = edges[0]["node"]

                        # Determine category
                        category = "material"
                        if node.get("category"):
                            cat_name = node["category"]["name"].lower()
                            if "labor" in cat_name or "install" in cat_name:
                                category = "labor"
                        elif "labor" in term.lower() or "install" in term.lower():
                            category = "labor"

                        items.append(OneBuildItem(
                            id=node["id"],
                            name=node["name"],
                            unit=node["unit"],
                            price=float(node["price"]["amount"]),
                            category=category
                        ))
            except Exception as e:
                # Log error and continue to next term to be resilient
                # For now, we just print to stdout, in production this should use logging
                print(f"Failed to fetch data for term '{term}': {e}")
                continue

        return items

    def _get_search_terms(self, building_type: str) -> List[str]:
        """Return a list of search terms based on building type."""
        common_labor = ["General Laborer", "Carpenter", "Electrician", "Plumber"]

        if building_type == 'wood_frame':
            return ["2x4 Lumber", "Plywood", "Wood Siding", "Asphalt Shingles"] + common_labor
        elif building_type == 'steel_frame':
            return ["Steel Stud", "Structural Steel", "Metal Decking", "Steel Siding"] + common_labor
        elif building_type == 'concrete':
            return ["Ready Mix Concrete", "Rebar", "Concrete Formwork", "Concrete Finisher"] + common_labor
        elif building_type == 'modular':
            return ["Modular Unit", "Crane Rental", "Site Preparation"] + common_labor
        else:
            # Default fallback
            return ["Concrete", "Lumber", "Drywall", "Paint"] + common_labor
