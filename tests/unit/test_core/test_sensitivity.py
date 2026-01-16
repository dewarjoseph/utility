"""Tests for the sensitivity analysis module."""

import pytest
from core.sensitivity import (
    SensitivityAnalyzer, SensitivityResult, MonteCarloResult,
    ScenarioType, get_sensitivity_analyzer
)


class TestSensitivityAnalyzer:
    """Tests for sensitivity analysis."""

    def test_interest_rate_analysis(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.analyze_interest_rate(
            base_rate=0.06,
            new_rate=0.07,
            loan_amount=1000000,
            noi=100000
        )
        
        assert isinstance(result, SensitivityResult)
        assert result.scenario.scenario_type == ScenarioType.INTEREST_RATE
        assert result.impact_pct != 0

    def test_construction_cost_analysis(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.analyze_construction_cost(
            base_cost=2000000,
            change_pct=10,
            cap_rate=0.06
        )
        
        assert isinstance(result, SensitivityResult)
        assert result.scenario.scenario_type == ScenarioType.CONSTRUCTION_COST
        # Cost increase should have negative impact
        assert result.impact_pct < 0

    def test_vacancy_analysis(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.analyze_vacancy(
            gross_income=200000,
            base_vacancy=0.05,
            new_vacancy=0.10
        )
        
        assert isinstance(result, SensitivityResult)
        assert result.scenario.scenario_type == ScenarioType.VACANCY
        # Higher vacancy = less income
        assert result.adjusted_value < result.base_value


class TestMonteCarloSimulation:
    """Tests for Monte Carlo simulation."""

    def test_monte_carlo_basic(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run_monte_carlo(
            base_noi=100000,
            iterations=100
        )
        
        assert isinstance(result, MonteCarloResult)
        assert result.iterations == 100

    def test_monte_carlo_percentiles(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run_monte_carlo(
            base_noi=100000,
            iterations=500
        )
        
        # Percentiles should be ordered
        assert result.percentile_5 <= result.percentile_50
        assert result.percentile_50 <= result.percentile_95

    def test_monte_carlo_bounds(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run_monte_carlo(
            base_noi=100000,
            iterations=500
        )
        
        assert result.worst_case <= result.mean_noi
        assert result.best_case >= result.mean_noi

    def test_probability_positive(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run_monte_carlo(
            base_noi=100000,
            iterations=500
        )
        
        # With positive base NOI, most should be positive
        assert result.probability_positive > 50


class TestScenarioMatrix:
    """Tests for scenario matrix generation."""

    def test_generate_interest_scenarios(self):
        analyzer = SensitivityAnalyzer()
        scenarios = analyzer.generate_scenario_matrix({
            'interest_rate': 0.06,
            'loan_amount': 1000000,
            'noi': 100000,
        })
        
        assert len(scenarios) > 0
        assert all(isinstance(s, SensitivityResult) for s in scenarios)

    def test_generate_cost_scenarios(self):
        analyzer = SensitivityAnalyzer()
        scenarios = analyzer.generate_scenario_matrix({
            'construction_cost': 2000000,
        })
        
        assert len(scenarios) > 0


class TestResultSerialization:
    """Tests for result serialization."""

    def test_sensitivity_result_to_dict(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.analyze_interest_rate(0.06, 0.07, 1000000, 100000)
        
        d = result.to_dict()
        assert 'scenario_name' in d
        assert 'impact_pct' in d
        assert 'recommendation' in d

    def test_monte_carlo_to_dict(self):
        analyzer = SensitivityAnalyzer()
        result = analyzer.run_monte_carlo(100000, iterations=100)
        
        d = result.to_dict()
        assert 'mean_noi' in d
        assert 'percentile_50' in d


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_sensitivity_analyzer(self):
        analyzer = get_sensitivity_analyzer()
        assert isinstance(analyzer, SensitivityAnalyzer)
