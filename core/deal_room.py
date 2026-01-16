"""
Deal Room Module

Capital formation, investor management, and deal tracking
for Real Estate Investment Cooperatives.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, date
import uuid


class DealStatus(Enum):
    """Status of a deal."""
    DRAFT = "draft"
    DUE_DILIGENCE = "due_diligence"
    FUNDRAISING = "fundraising"
    FUNDED = "funded"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class InvestmentType(Enum):
    """Type of investment instrument."""
    EQUITY = "equity"
    REVENUE_SHARE = "revenue_share"
    CONVERTIBLE_NOTE = "convertible_note"
    SAFE = "safe"
    LOAN = "loan"


class InvestorStatus(Enum):
    """Status of an investor commitment."""
    INTERESTED = "interested"
    COMMITTED = "committed"
    FUNDED = "funded"
    WITHDRAWN = "withdrawn"


@dataclass
class CapitalStackItem:
    """An item in the capital stack."""
    id: str
    name: str
    investment_type: InvestmentType
    amount: float
    terms: Dict[str, Any] = field(default_factory=dict)
    
    # For revenue share
    revenue_share_pct: Optional[float] = None
    repayment_multiple: Optional[float] = None
    
    # For equity
    ownership_pct: Optional[float] = None
    
    # For debt
    interest_rate: Optional[float] = None
    term_months: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.investment_type.value,
            'amount': self.amount,
            'terms': self.terms,
        }


@dataclass
class InvestorCommitment:
    """A commitment from an investor."""
    id: str
    investor_name: str
    investor_email: str
    amount: float
    investment_type: InvestmentType
    status: InvestorStatus = InvestorStatus.INTERESTED
    committed_at: Optional[datetime] = None
    funded_at: Optional[datetime] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'investor': self.investor_name,
            'amount': self.amount,
            'type': self.investment_type.value,
            'status': self.status.value,
        }


@dataclass
class PropertyDetails:
    """Details about the property in a deal."""
    address: str
    city: str
    state: str
    zip_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    lot_size_sqft: float = 0
    building_sqft: float = 0
    units: int = 0
    year_built: Optional[int] = None
    zoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'lot_size': self.lot_size_sqft,
            'building_sqft': self.building_sqft,
            'units': self.units,
            'zoning': self.zoning,
        }


@dataclass
class FinancialSummary:
    """Financial summary for a deal."""
    acquisition_cost: float = 0
    renovation_cost: float = 0
    soft_costs: float = 0
    total_project_cost: float = 0
    
    projected_noi: float = 0
    projected_value: float = 0
    yield_on_cost: float = 0
    
    # Funding
    equity_required: float = 0
    debt_amount: float = 0
    ltv_ratio: float = 0
    
    def calculate_totals(self):
        """Recalculate derived fields."""
        self.total_project_cost = self.acquisition_cost + self.renovation_cost + self.soft_costs
        if self.total_project_cost > 0:
            self.yield_on_cost = self.projected_noi / self.total_project_cost
        if self.projected_value > 0:
            self.ltv_ratio = self.debt_amount / self.projected_value


@dataclass
class Deal:
    """A real estate deal in the deal room."""
    id: str
    name: str
    description: str
    status: DealStatus = DealStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    
    # Property
    property_details: Optional[PropertyDetails] = None
    
    # Financials
    financials: FinancialSummary = field(default_factory=FinancialSummary)
    
    # Capital stack
    capital_stack: List[CapitalStackItem] = field(default_factory=list)
    
    # Investors
    commitments: List[InvestorCommitment] = field(default_factory=list)
    
    # Documents
    documents: List[str] = field(default_factory=list)
    
    # Governance
    cooperative_name: Optional[str] = None
    target_members: int = 0
    
    @property
    def total_raised(self) -> float:
        """Total amount raised from committed/funded investors."""
        return sum(
            c.amount for c in self.commitments 
            if c.status in [InvestorStatus.COMMITTED, InvestorStatus.FUNDED]
        )
    
    @property
    def funding_progress(self) -> float:
        """Percentage of funding target raised."""
        target = self.financials.equity_required
        if target <= 0:
            return 0
        return min(100, (self.total_raised / target) * 100)
    
    @property
    def investor_count(self) -> int:
        """Number of committed investors."""
        return len([c for c in self.commitments 
                   if c.status in [InvestorStatus.COMMITTED, InvestorStatus.FUNDED]])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status.value,
            'total_raised': self.total_raised,
            'funding_progress': f"{self.funding_progress:.1f}%",
            'investor_count': self.investor_count,
            'property': self.property_details.to_dict() if self.property_details else None,
        }


class CapitalStackBuilder:
    """Builder for creating capital stacks."""
    
    def __init__(self, total_project_cost: float):
        self.total_cost = total_project_cost
        self.items: List[CapitalStackItem] = []
    
    def add_senior_debt(
        self,
        amount: float,
        interest_rate: float,
        term_months: int = 360,
        name: str = "Senior Mortgage"
    ) -> 'CapitalStackBuilder':
        """Add senior debt to the stack."""
        item = CapitalStackItem(
            id=str(uuid.uuid4())[:8],
            name=name,
            investment_type=InvestmentType.LOAN,
            amount=amount,
            interest_rate=interest_rate,
            term_months=term_months,
        )
        self.items.append(item)
        return self
    
    def add_revenue_share(
        self,
        amount: float,
        revenue_share_pct: float = 0.05,
        repayment_multiple: float = 1.5,
        name: str = "Community Revenue Share"
    ) -> 'CapitalStackBuilder':
        """Add revenue share investment."""
        item = CapitalStackItem(
            id=str(uuid.uuid4())[:8],
            name=name,
            investment_type=InvestmentType.REVENUE_SHARE,
            amount=amount,
            revenue_share_pct=revenue_share_pct,
            repayment_multiple=repayment_multiple,
        )
        self.items.append(item)
        return self
    
    def add_member_equity(
        self,
        amount: float,
        ownership_pct: Optional[float] = None,
        name: str = "Member Equity"
    ) -> 'CapitalStackBuilder':
        """Add member equity."""
        item = CapitalStackItem(
            id=str(uuid.uuid4())[:8],
            name=name,
            investment_type=InvestmentType.EQUITY,
            amount=amount,
            ownership_pct=ownership_pct,
        )
        self.items.append(item)
        return self
    
    def build(self) -> List[CapitalStackItem]:
        """Build and return the capital stack."""
        return self.items
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the capital stack."""
        total_debt = sum(i.amount for i in self.items if i.investment_type == InvestmentType.LOAN)
        total_equity = sum(i.amount for i in self.items if i.investment_type == InvestmentType.EQUITY)
        total_revenue_share = sum(i.amount for i in self.items if i.investment_type == InvestmentType.REVENUE_SHARE)
        total = total_debt + total_equity + total_revenue_share
        
        return {
            'total_capital': total,
            'debt': total_debt,
            'equity': total_equity,
            'revenue_share': total_revenue_share,
            'debt_pct': (total_debt / total * 100) if total > 0 else 0,
            'equity_pct': (total_equity / total * 100) if total > 0 else 0,
            'gap': self.total_cost - total,
        }


class DealRoom:
    """Manages deals and investor commitments."""
    
    def __init__(self):
        self.deals: Dict[str, Deal] = {}
        self.investors: Dict[str, Dict[str, Any]] = {}
    
    def create_deal(
        self,
        name: str,
        description: str,
        property_address: Optional[str] = None
    ) -> Deal:
        """Create a new deal."""
        deal = Deal(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
        )
        
        if property_address:
            deal.property_details = PropertyDetails(
                address=property_address,
                city="",
                state="",
                zip_code="",
            )
        
        self.deals[deal.id] = deal
        return deal
    
    def add_commitment(
        self,
        deal_id: str,
        investor_name: str,
        investor_email: str,
        amount: float,
        investment_type: InvestmentType = InvestmentType.REVENUE_SHARE
    ) -> InvestorCommitment:
        """Add an investor commitment to a deal."""
        if deal_id not in self.deals:
            raise ValueError(f"Deal {deal_id} not found")
        
        commitment = InvestorCommitment(
            id=str(uuid.uuid4())[:8],
            investor_name=investor_name,
            investor_email=investor_email,
            amount=amount,
            investment_type=investment_type,
        )
        
        self.deals[deal_id].commitments.append(commitment)
        return commitment
    
    def update_commitment_status(
        self,
        deal_id: str,
        commitment_id: str,
        status: InvestorStatus
    ) -> bool:
        """Update the status of a commitment."""
        deal = self.deals.get(deal_id)
        if not deal:
            return False
        
        for commitment in deal.commitments:
            if commitment.id == commitment_id:
                commitment.status = status
                if status == InvestorStatus.COMMITTED:
                    commitment.committed_at = datetime.now()
                elif status == InvestorStatus.FUNDED:
                    commitment.funded_at = datetime.now()
                return True
        
        return False
    
    def get_deal_summary(self, deal_id: str) -> Dict[str, Any]:
        """Get a summary of a deal."""
        deal = self.deals.get(deal_id)
        if not deal:
            return {}
        
        return {
            'deal': deal.to_dict(),
            'financials': {
                'total_cost': deal.financials.total_project_cost,
                'equity_required': deal.financials.equity_required,
                'total_raised': deal.total_raised,
                'funding_progress': deal.funding_progress,
            },
            'investors': {
                'total': len(deal.commitments),
                'committed': deal.investor_count,
            },
        }
    
    def get_all_deals(self) -> List[Dict[str, Any]]:
        """Get all deals."""
        return [deal.to_dict() for deal in self.deals.values()]


def get_deal_room() -> DealRoom:
    """Factory function for deal room."""
    return DealRoom()
