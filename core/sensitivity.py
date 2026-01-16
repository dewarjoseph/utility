"""
Sensitivity Analysis Module - What-if scenarios and Monte Carlo simulation.

Provides stress testing capabilities for pro forma financial models.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum


class ScenarioType(Enum):
    """Types of sensitivity scenarios."""
    INTEREST_RATE = "interest_rate"
    CONSTRUCTION_COST = "construction_cost"
    RENT_GROWTH = "rent_growth"
    VACANCY = "vacancy"
    CAP_RATE = "cap_rate"


@dataclass
class Scenario:
    """A single what-if scenario."""
    name: str
    scenario_type: ScenarioType
    base_value: float
    adjusted_value: float
    description: str


@dataclass
class SensitivityResult:
    """Result of a sensitivity analysis."""
    scenario: Scenario
    base_noi: float
    adjusted_noi: float
    base_value: float
    adjusted_value: float
    impact_pct: float
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario_name': self.scenario.name,
            'scenario_type': self.scenario.scenario_type.value,
            'base_value': self.base_value,
            'adjusted_value': self.adjusted_value,
            'impact_pct': self.impact_pct,
            'recommendation': self.recommendation,
        }


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    iterations: int
    mean_noi: float
    std_noi: float
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    probability_positive: float
    worst_case: float
    best_case: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'iterations': self.iterations,
            'mean_noi': self.mean_noi,
            'std_noi': self.std_noi,
            'percentile_5': self.percentile_5,
            'percentile_50': self.percentile_50,
            'percentile_95': self.percentile_95,
            'probability_positive': self.probability_positive,
            'worst_case': self.worst_case,
            'best_case': self.best_case,
        }


class SensitivityAnalyzer:
    """Analyzer for what-if scenarios and stress testing."""

    def __init__(self):
        self.results: List[SensitivityResult] = []

    def analyze_interest_rate(
        self,
        base_rate: float,
        new_rate: float,
        loan_amount: float,
        noi: float
    ) -> SensitivityResult:
        """Analyze impact of interest rate change on debt service."""
        base_debt_service = loan_amount * base_rate
        new_debt_service = loan_amount * new_rate
        
        base_cash_flow = noi - base_debt_service
        new_cash_flow = noi - new_debt_service
        
        impact = (new_cash_flow - base_cash_flow) / base_cash_flow * 100 if base_cash_flow > 0 else 0
        
        if new_rate > base_rate:
            rec = f"Rate increase of {(new_rate - base_rate)*100:.1f}% reduces cash flow by ${base_debt_service - new_debt_service:,.0f}/year"
        else:
            rec = f"Rate decrease saves ${new_debt_service - base_debt_service:,.0f}/year in debt service"

        scenario = Scenario(
            name=f"Interest Rate: {base_rate*100:.1f}% → {new_rate*100:.1f}%",
            scenario_type=ScenarioType.INTEREST_RATE,
            base_value=base_rate,
            adjusted_value=new_rate,
            description="Impact of interest rate change on annual debt service"
        )

        result = SensitivityResult(
            scenario=scenario,
            base_noi=noi,
            adjusted_noi=noi,  # NOI doesn't change, cash flow does
            base_value=base_cash_flow,
            adjusted_value=new_cash_flow,
            impact_pct=impact,
            recommendation=rec
        )
        
        self.results.append(result)
        return result

    def analyze_construction_cost(
        self,
        base_cost: float,
        change_pct: float,
        cap_rate: float
    ) -> SensitivityResult:
        """Analyze impact of construction cost changes."""
        new_cost = base_cost * (1 + change_pct / 100)
        cost_diff = new_cost - base_cost
        
        # Higher cost = lower return on cost
        base_yield = 0.06  # Assumed 6% yield on cost
        new_yield = base_yield * (base_cost / new_cost)
        
        impact = (new_yield - base_yield) / base_yield * 100

        if change_pct > 0:
            rec = f"Cost increase of ${cost_diff:,.0f} reduces yield on cost to {new_yield*100:.1f}%"
        else:
            rec = f"Cost savings of ${-cost_diff:,.0f} improves yield on cost to {new_yield*100:.1f}%"

        scenario = Scenario(
            name=f"Construction Cost: {change_pct:+.1f}%",
            scenario_type=ScenarioType.CONSTRUCTION_COST,
            base_value=base_cost,
            adjusted_value=new_cost,
            description="Impact of construction cost variance"
        )

        return SensitivityResult(
            scenario=scenario,
            base_noi=base_cost * base_yield,
            adjusted_noi=new_cost * new_yield,
            base_value=base_cost,
            adjusted_value=new_cost,
            impact_pct=impact,
            recommendation=rec
        )

    def analyze_vacancy(
        self,
        gross_income: float,
        base_vacancy: float,
        new_vacancy: float
    ) -> SensitivityResult:
        """Analyze impact of vacancy rate changes."""
        base_egi = gross_income * (1 - base_vacancy)
        new_egi = gross_income * (1 - new_vacancy)
        
        impact = (new_egi - base_egi) / base_egi * 100

        vacancy_diff = (new_vacancy - base_vacancy) * 100
        if vacancy_diff > 0:
            rec = f"Vacancy increase of {vacancy_diff:.1f}% reduces income by ${base_egi - new_egi:,.0f}/year"
        else:
            rec = f"Vacancy decrease of {-vacancy_diff:.1f}% adds ${new_egi - base_egi:,.0f}/year"

        scenario = Scenario(
            name=f"Vacancy: {base_vacancy*100:.0f}% → {new_vacancy*100:.0f}%",
            scenario_type=ScenarioType.VACANCY,
            base_value=base_vacancy,
            adjusted_value=new_vacancy,
            description="Impact of vacancy rate change"
        )

        return SensitivityResult(
            scenario=scenario,
            base_noi=base_egi,
            adjusted_noi=new_egi,
            base_value=base_egi,
            adjusted_value=new_egi,
            impact_pct=impact,
            recommendation=rec
        )

    def run_monte_carlo(
        self,
        base_noi: float,
        cost_volatility: float = 0.10,
        rent_volatility: float = 0.08,
        vacancy_volatility: float = 0.03,
        iterations: int = 1000
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation for NOI uncertainty."""
        random.seed(42)  # For reproducibility
        
        results = []
        for _ in range(iterations):
            # Random factors
            cost_factor = 1 + random.gauss(0, cost_volatility)
            rent_factor = 1 + random.gauss(0, rent_volatility)
            vacancy_shock = random.gauss(0, vacancy_volatility)
            
            # Combined impact on NOI
            noi = base_noi * rent_factor * cost_factor * (1 - vacancy_shock)
            results.append(noi)
        
        results.sort()
        n = len(results)
        
        return MonteCarloResult(
            iterations=iterations,
            mean_noi=sum(results) / n,
            std_noi=(sum((x - sum(results)/n)**2 for x in results) / n) ** 0.5,
            percentile_5=results[int(n * 0.05)],
            percentile_25=results[int(n * 0.25)],
            percentile_50=results[int(n * 0.50)],
            percentile_75=results[int(n * 0.75)],
            percentile_95=results[int(n * 0.95)],
            probability_positive=sum(1 for x in results if x > 0) / n * 100,
            worst_case=min(results),
            best_case=max(results),
        )

    def generate_scenario_matrix(
        self,
        base_values: Dict[str, float]
    ) -> List[SensitivityResult]:
        """Generate a matrix of common scenarios."""
        scenarios = []
        
        # Interest rate scenarios
        if 'interest_rate' in base_values and 'loan_amount' in base_values:
            base_rate = base_values['interest_rate']
            loan = base_values['loan_amount']
            noi = base_values.get('noi', 100000)
            
            for delta in [-0.01, 0.01, 0.02, 0.03]:
                scenarios.append(self.analyze_interest_rate(
                    base_rate, base_rate + delta, loan, noi
                ))

        # Construction cost scenarios
        if 'construction_cost' in base_values:
            cost = base_values['construction_cost']
            cap = base_values.get('cap_rate', 0.06)
            
            for pct in [-10, -5, 5, 10, 20]:
                scenarios.append(self.analyze_construction_cost(cost, pct, cap))

        # Vacancy scenarios
        if 'gross_income' in base_values:
            income = base_values['gross_income']
            base_vac = base_values.get('vacancy', 0.05)
            
            for new_vac in [0.03, 0.07, 0.10, 0.15]:
                scenarios.append(self.analyze_vacancy(income, base_vac, new_vac))

        return scenarios


def get_sensitivity_analyzer() -> SensitivityAnalyzer:
    """Factory function for sensitivity analyzer."""
    return SensitivityAnalyzer()
