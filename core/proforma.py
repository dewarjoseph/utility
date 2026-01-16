"""
Pro Forma Financial Engine - Basic development financial modeling.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ProjectType(Enum):
    """Types of development projects."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"
    COOPERATIVE = "cooperative"


@dataclass
class CostAssumptions:
    """Construction and development cost assumptions."""
    land_cost_per_sqft: float = 50.0
    hard_cost_per_sqft: float = 200.0  # Construction
    soft_cost_pct: float = 0.20  # % of hard costs
    contingency_pct: float = 0.10
    financing_cost_pct: float = 0.05


@dataclass
class RevenueAssumptions:
    """Revenue and operating assumptions."""
    rent_per_sqft_annual: float = 24.0
    vacancy_rate: float = 0.05
    operating_expense_ratio: float = 0.35
    cap_rate: float = 0.06
    solar_revenue_per_kwh: float = 0.12


@dataclass
class ProFormaInputs:
    """Inputs for pro forma calculation."""
    lot_size_sqft: float
    buildable_sqft: float
    project_type: ProjectType = ProjectType.MIXED_USE
    num_units: int = 0
    cost_assumptions: CostAssumptions = field(default_factory=CostAssumptions)
    revenue_assumptions: RevenueAssumptions = field(default_factory=RevenueAssumptions)


@dataclass
class ProFormaResult:
    """Results of pro forma calculation."""
    # Costs
    land_cost: float = 0.0
    hard_costs: float = 0.0
    soft_costs: float = 0.0
    contingency: float = 0.0
    financing_costs: float = 0.0
    total_development_cost: float = 0.0
    
    # Revenue
    gross_potential_income: float = 0.0
    effective_gross_income: float = 0.0
    operating_expenses: float = 0.0
    net_operating_income: float = 0.0
    
    # Returns
    yield_on_cost: float = 0.0
    stabilized_value: float = 0.0
    profit_margin: float = 0.0
    cost_per_unit: float = 0.0
    
    # Cooperative metrics
    community_dividend_annual: float = 0.0
    affordability_index: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_development_cost': self.total_development_cost,
            'land_cost': self.land_cost,
            'hard_costs': self.hard_costs,
            'soft_costs': self.soft_costs,
            'net_operating_income': self.net_operating_income,
            'yield_on_cost': self.yield_on_cost,
            'stabilized_value': self.stabilized_value,
            'profit_margin': self.profit_margin,
            'cost_per_unit': self.cost_per_unit,
            'community_dividend_annual': self.community_dividend_annual,
        }


class ProFormaEngine:
    """Engine for calculating development pro formas."""

    def calculate(self, inputs: ProFormaInputs) -> ProFormaResult:
        """Calculate full pro forma from inputs."""
        result = ProFormaResult()
        costs = inputs.cost_assumptions
        revenue = inputs.revenue_assumptions

        # Calculate costs
        result.land_cost = inputs.lot_size_sqft * costs.land_cost_per_sqft
        result.hard_costs = inputs.buildable_sqft * costs.hard_cost_per_sqft
        result.soft_costs = result.hard_costs * costs.soft_cost_pct
        result.contingency = (result.hard_costs + result.soft_costs) * costs.contingency_pct
        subtotal = result.land_cost + result.hard_costs + result.soft_costs + result.contingency
        result.financing_costs = subtotal * costs.financing_cost_pct
        result.total_development_cost = subtotal + result.financing_costs

        # Calculate revenue
        result.gross_potential_income = inputs.buildable_sqft * revenue.rent_per_sqft_annual
        result.effective_gross_income = result.gross_potential_income * (1 - revenue.vacancy_rate)
        result.operating_expenses = result.effective_gross_income * revenue.operating_expense_ratio
        result.net_operating_income = result.effective_gross_income - result.operating_expenses

        # Calculate returns
        if result.total_development_cost > 0:
            result.yield_on_cost = result.net_operating_income / result.total_development_cost
        if revenue.cap_rate > 0:
            result.stabilized_value = result.net_operating_income / revenue.cap_rate
        if result.total_development_cost > 0:
            result.profit_margin = (result.stabilized_value - result.total_development_cost) / result.total_development_cost
        if inputs.num_units > 0:
            result.cost_per_unit = result.total_development_cost / inputs.num_units

        # Cooperative metrics
        debt_service_ratio = 0.6  # Assume 60% of NOI goes to debt
        result.community_dividend_annual = result.net_operating_income * (1 - debt_service_ratio)
        
        # Affordability: % of units that could be below market while breaking even
        if result.gross_potential_income > 0:
            break_even_income = result.operating_expenses + (result.net_operating_income * debt_service_ratio)
            result.affordability_index = 1 - (break_even_income / result.gross_potential_income)

        return result

    def quick_estimate(self, lot_sqft: float, far: float = 1.5, 
                       cost_per_sqft: float = 250.0) -> Dict[str, float]:
        """Quick cost/value estimate without full inputs."""
        buildable = lot_sqft * far
        total_cost = lot_sqft * 50 + buildable * cost_per_sqft
        annual_income = buildable * 24 * 0.95 * 0.65  # Rough NOI
        value = annual_income / 0.06
        
        return {
            'buildable_sqft': buildable,
            'estimated_cost': total_cost,
            'estimated_noi': annual_income,
            'estimated_value': value,
            'estimated_profit': value - total_cost,
        }


def create_proforma(lot_sqft: float, buildable_sqft: float, 
                    num_units: int = 0) -> ProFormaResult:
    """Convenience function to create a pro forma."""
    engine = ProFormaEngine()
    inputs = ProFormaInputs(
        lot_size_sqft=lot_sqft,
        buildable_sqft=buildable_sqft,
        num_units=num_units,
    )
    return engine.calculate(inputs)


def get_proforma_engine() -> ProFormaEngine:
    """Factory function for pro forma engine."""
    return ProFormaEngine()
