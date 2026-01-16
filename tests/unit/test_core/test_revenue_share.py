"""Tests for the revenue share module."""

import pytest
from core.revenue_share import (
    RevenueShareLedger, RevenueShareAgreement, MemberAccount, Transaction,
    TransactionType, get_revenue_ledger
)


class TestRevenueShareAgreement:
    """Tests for revenue share agreements."""

    def test_target_amount(self):
        agreement = RevenueShareAgreement(
            id="a1",
            investor_id="i1",
            investor_name="Test Investor",
            principal=100000,
            revenue_share_pct=0.05,
            repayment_multiple=1.5,
            start_date=None
        )
        assert agreement.target_amount == 150000

    def test_completion_tracking(self):
        agreement = RevenueShareAgreement(
            id="a1",
            investor_id="i1",
            investor_name="Test",
            principal=100000,
            revenue_share_pct=0.05,
            repayment_multiple=1.5,
            start_date=None,
            total_repaid=75000
        )
        assert agreement.remaining == 75000
        assert agreement.completion_pct == 50

    def test_calculate_payment(self):
        agreement = RevenueShareAgreement(
            id="a1",
            investor_id="i1",
            investor_name="Test",
            principal=100000,
            revenue_share_pct=0.05,
            repayment_multiple=1.5,
            start_date=None
        )
        # 5% of 200k revenue = 10k
        payment = agreement.calculate_payment(200000)
        assert payment == 10000


class TestRevenueShareLedger:
    """Tests for the revenue share ledger."""

    def test_add_member(self):
        ledger = RevenueShareLedger()
        account = ledger.add_member("m1", "John Doe")
        
        assert isinstance(account, MemberAccount)
        assert account.capital_balance == 0

    def test_record_contribution(self):
        ledger = RevenueShareLedger()
        ledger.add_member("m1", "John Doe")
        
        txn = ledger.record_contribution("m1", 5000, "Initial investment")
        
        assert ledger.members["m1"].capital_balance == 5000
        assert len(ledger.transactions) == 1

    def test_add_revenue_share_agreement(self):
        ledger = RevenueShareLedger()
        agreement = ledger.add_revenue_share_agreement(
            investor_id="i1",
            investor_name="Investor A",
            principal=50000,
            revenue_share_pct=0.05,
            repayment_multiple=1.5
        )
        
        assert agreement.target_amount == 75000
        assert len(ledger.agreements) == 1

    def test_process_revenue(self):
        ledger = RevenueShareLedger()
        ledger.add_revenue_share_agreement(
            investor_id="i1",
            investor_name="Investor A",
            principal=100000,
            revenue_share_pct=0.05,
            repayment_multiple=1.5
        )
        
        payments = ledger.process_revenue(200000)
        
        assert "Investor A" in payments
        assert payments["Investor A"] == 10000

    def test_patronage_dividends(self):
        ledger = RevenueShareLedger()
        ledger.add_member("m1", "Member 1")
        ledger.add_member("m2", "Member 2")
        
        patronage = {"m1": 1000, "m2": 3000}  # M2 used 3x more
        dividends = ledger.calculate_patronage_dividends(10000, patronage)
        
        assert dividends["m1"] == 2500  # 25%
        assert dividends["m2"] == 7500  # 75%

    def test_community_metrics(self):
        ledger = RevenueShareLedger()
        ledger.add_member("m1", "Member 1")
        ledger.add_member("m2", "Member 2")
        ledger.record_contribution("m1", 5000)
        ledger.record_contribution("m2", 10000)
        
        metrics = ledger.get_community_metrics()
        
        assert metrics['total_members'] == 2
        assert metrics['total_capital_raised'] == 15000
        assert metrics['average_investment'] == 7500


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_revenue_ledger(self):
        ledger = get_revenue_ledger()
        assert isinstance(ledger, RevenueShareLedger)
