"""Tests for the pro forma module."""

import pytest
from core.proforma import (
    ProFormaEngine, ProFormaInputs, ProFormaResult,
    CostAssumptions, RevenueAssumptions, ProjectType,
    create_proforma, get_proforma_engine
)


class TestProFormaEngine:
    """Tests for the pro forma calculation engine."""

    def test_basic_calculation(self):
        engine = ProFormaEngine()
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=15000,
            num_units=10,
        )
        result = engine.calculate(inputs)
        
        assert result.total_development_cost > 0
        assert result.land_cost == 10000 * 50  # Default $50/sqft
        assert result.hard_costs == 15000 * 200  # Default $200/sqft
        assert result.net_operating_income > 0

    def test_yield_on_cost(self):
        engine = ProFormaEngine()
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=20000,
        )
        result = engine.calculate(inputs)
        
        # Yield should be positive and reasonable (typically 4-10%)
        assert 0.01 < result.yield_on_cost < 0.20

    def test_cost_per_unit(self):
        engine = ProFormaEngine()
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=15000,
            num_units=10,
        )
        result = engine.calculate(inputs)
        
        assert result.cost_per_unit == result.total_development_cost / 10

    def test_custom_assumptions(self):
        engine = ProFormaEngine()
        custom_costs = CostAssumptions(
            land_cost_per_sqft=100,
            hard_cost_per_sqft=300,
        )
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=15000,
            cost_assumptions=custom_costs,
        )
        result = engine.calculate(inputs)
        
        assert result.land_cost == 10000 * 100
        assert result.hard_costs == 15000 * 300

    def test_community_dividend(self):
        engine = ProFormaEngine()
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=20000,
        )
        result = engine.calculate(inputs)
        
        # Community dividend should be portion of NOI
        assert result.community_dividend_annual > 0
        assert result.community_dividend_annual < result.net_operating_income

    def test_affordability_index(self):
        engine = ProFormaEngine()
        inputs = ProFormaInputs(
            lot_size_sqft=10000,
            buildable_sqft=20000,
        )
        result = engine.calculate(inputs)
        
        # Affordability index should be between 0 and 1
        assert 0 <= result.affordability_index <= 1


class TestQuickEstimate:
    """Tests for quick estimation function."""

    def test_quick_estimate_returns_dict(self):
        engine = ProFormaEngine()
        result = engine.quick_estimate(10000)
        
        assert 'buildable_sqft' in result
        assert 'estimated_cost' in result
        assert 'estimated_value' in result

    def test_quick_estimate_scales_with_lot_size(self):
        engine = ProFormaEngine()
        small = engine.quick_estimate(5000)
        large = engine.quick_estimate(20000)
        
        assert large['estimated_cost'] > small['estimated_cost']


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_proforma(self):
        result = create_proforma(10000, 15000, 10)
        assert isinstance(result, ProFormaResult)
        assert result.total_development_cost > 0

    def test_get_proforma_engine(self):
        engine = get_proforma_engine()
        assert isinstance(engine, ProFormaEngine)


class TestProFormaResult:
    """Tests for ProFormaResult data class."""

    def test_to_dict(self):
        result = ProFormaResult(
            total_development_cost=1000000,
            land_cost=500000,
            net_operating_income=80000,
        )
        d = result.to_dict()
        
        assert d['total_development_cost'] == 1000000
        assert d['land_cost'] == 500000
        assert 'yield_on_cost' in d
