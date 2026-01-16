"""Tests for the deal room module."""

import pytest
from core.deal_room import (
    DealRoom, Deal, CapitalStackBuilder, InvestorCommitment,
    PropertyDetails, FinancialSummary, CapitalStackItem,
    DealStatus, InvestmentType, InvestorStatus,
    get_deal_room
)


class TestCapitalStackBuilder:
    """Tests for capital stack builder."""

    def test_add_senior_debt(self):
        builder = CapitalStackBuilder(1000000)
        builder.add_senior_debt(650000, 0.065, 360)
        
        items = builder.build()
        assert len(items) == 1
        assert items[0].investment_type == InvestmentType.LOAN
        assert items[0].amount == 650000

    def test_add_revenue_share(self):
        builder = CapitalStackBuilder(1000000)
        builder.add_revenue_share(100000, 0.05, 1.5)
        
        items = builder.build()
        assert len(items) == 1
        assert items[0].investment_type == InvestmentType.REVENUE_SHARE
        assert items[0].repayment_multiple == 1.5

    def test_build_full_stack(self):
        builder = CapitalStackBuilder(1000000)
        builder.add_senior_debt(650000, 0.065)
        builder.add_revenue_share(200000, 0.05)
        builder.add_member_equity(150000)
        
        items = builder.build()
        assert len(items) == 3
        
        summary = builder.get_summary()
        assert summary['total_capital'] == 1000000
        assert summary['debt'] == 650000
        assert summary['revenue_share'] == 200000

    def test_gap_calculation(self):
        builder = CapitalStackBuilder(1000000)
        builder.add_senior_debt(500000, 0.065)
        
        summary = builder.get_summary()
        assert summary['gap'] == 500000


class TestDeal:
    """Tests for deal model."""

    def test_deal_creation(self):
        deal = Deal(
            id="test_deal",
            name="Test Project",
            description="A test deal"
        )
        assert deal.status == DealStatus.DRAFT
        assert deal.total_raised == 0

    def test_funding_progress(self):
        deal = Deal(
            id="test",
            name="Test",
            description="Test"
        )
        deal.financials.equity_required = 100000
        
        deal.commitments.append(InvestorCommitment(
            id="c1",
            investor_name="Test",
            investor_email="test@test.com",
            amount=50000,
            investment_type=InvestmentType.REVENUE_SHARE,
            status=InvestorStatus.COMMITTED
        ))
        
        assert deal.total_raised == 50000
        assert deal.funding_progress == 50.0


class TestDealRoom:
    """Tests for deal room management."""

    def test_create_deal(self):
        room = DealRoom()
        deal = room.create_deal(
            "Santa Cruz Co-op",
            "Community housing project",
            "123 Main St"
        )
        
        assert deal.id in room.deals
        assert deal.name == "Santa Cruz Co-op"

    def test_add_commitment(self):
        room = DealRoom()
        deal = room.create_deal("Test", "Test", None)
        
        commitment = room.add_commitment(
            deal.id,
            "Alice Smith",
            "alice@example.com",
            10000,
            InvestmentType.REVENUE_SHARE
        )
        
        assert len(room.deals[deal.id].commitments) == 1
        assert commitment.investor_name == "Alice Smith"

    def test_update_commitment_status(self):
        room = DealRoom()
        deal = room.create_deal("Test", "Test", None)
        commitment = room.add_commitment(
            deal.id, "Bob", "bob@test.com", 5000
        )
        
        success = room.update_commitment_status(
            deal.id, commitment.id, InvestorStatus.COMMITTED
        )
        
        assert success
        assert commitment.status == InvestorStatus.COMMITTED
        assert commitment.committed_at is not None

    def test_get_deal_summary(self):
        room = DealRoom()
        deal = room.create_deal("Test", "Test", None)
        deal.financials.equity_required = 100000
        room.add_commitment(deal.id, "Investor", "inv@test.com", 25000)
        
        summary = room.get_deal_summary(deal.id)
        
        assert 'deal' in summary
        assert 'financials' in summary
        assert 'investors' in summary


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_deal_room(self):
        room = get_deal_room()
        assert isinstance(room, DealRoom)
