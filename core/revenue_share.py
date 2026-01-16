"""
Revenue Share Module - Tracking member contributions and distributions.

Implements revenue share agreements and patronage dividend calculations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, date
import uuid


class TransactionType(Enum):
    """Type of financial transaction."""
    CAPITAL_CONTRIBUTION = "capital_contribution"
    PATRONAGE_DIVIDEND = "patronage_dividend"
    REVENUE_SHARE = "revenue_share"
    LOAN_REPAYMENT = "loan_repayment"
    DISTRIBUTION = "distribution"
    FEE = "fee"


@dataclass
class Transaction:
    """A financial transaction record."""
    id: str
    member_id: str
    transaction_type: TransactionType
    amount: float
    date: datetime
    description: str
    reference: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'member_id': self.member_id,
            'type': self.transaction_type.value,
            'amount': self.amount,
            'date': self.date.isoformat(),
            'description': self.description,
        }


@dataclass
class MemberAccount:
    """A member's capital account."""
    member_id: str
    name: str
    joined_date: date
    capital_balance: float = 0
    patronage_credits: float = 0
    total_distributions: float = 0
    transactions: List[Transaction] = field(default_factory=list)
    
    @property
    def net_position(self) -> float:
        """Net investment position."""
        return self.capital_balance + self.patronage_credits - self.total_distributions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'member_id': self.member_id,
            'name': self.name,
            'capital_balance': self.capital_balance,
            'patronage_credits': self.patronage_credits,
            'total_distributions': self.total_distributions,
            'net_position': self.net_position,
        }


@dataclass
class RevenueShareAgreement:
    """A revenue share investment agreement."""
    id: str
    investor_id: str
    investor_name: str
    principal: float
    revenue_share_pct: float  # e.g., 0.05 = 5%
    repayment_multiple: float  # e.g., 1.5 = repay 1.5x principal
    start_date: date
    total_repaid: float = 0
    
    @property
    def target_amount(self) -> float:
        """Total amount to repay."""
        return self.principal * self.repayment_multiple
    
    @property
    def remaining(self) -> float:
        """Amount still owed."""
        return max(0, self.target_amount - self.total_repaid)
    
    @property
    def is_complete(self) -> bool:
        """Whether the agreement is fully repaid."""
        return self.remaining <= 0
    
    @property
    def completion_pct(self) -> float:
        """Percentage of repayment complete."""
        return min(100, (self.total_repaid / self.target_amount) * 100)
    
    def calculate_payment(self, gross_revenue: float) -> float:
        """Calculate payment for a given revenue period."""
        if self.is_complete:
            return 0
        payment = gross_revenue * self.revenue_share_pct
        return min(payment, self.remaining)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'investor_name': self.investor_name,
            'principal': self.principal,
            'revenue_share_pct': f"{self.revenue_share_pct*100:.1f}%",
            'repayment_multiple': f"{self.repayment_multiple}x",
            'target_amount': self.target_amount,
            'total_repaid': self.total_repaid,
            'remaining': self.remaining,
            'completion_pct': f"{self.completion_pct:.1f}%",
            'is_complete': self.is_complete,
        }


class RevenueShareLedger:
    """Ledger for tracking revenue share and member accounts."""
    
    def __init__(self):
        self.members: Dict[str, MemberAccount] = {}
        self.agreements: Dict[str, RevenueShareAgreement] = {}
        self.transactions: List[Transaction] = []
    
    def add_member(self, member_id: str, name: str, joined_date: Optional[date] = None) -> MemberAccount:
        """Add a new member account."""
        account = MemberAccount(
            member_id=member_id,
            name=name,
            joined_date=joined_date or date.today(),
        )
        self.members[member_id] = account
        return account
    
    def record_contribution(self, member_id: str, amount: float, description: str = "") -> Transaction:
        """Record a capital contribution."""
        if member_id not in self.members:
            raise ValueError(f"Member {member_id} not found")
        
        txn = Transaction(
            id=str(uuid.uuid4())[:8],
            member_id=member_id,
            transaction_type=TransactionType.CAPITAL_CONTRIBUTION,
            amount=amount,
            date=datetime.now(),
            description=description or "Capital contribution",
        )
        
        self.members[member_id].capital_balance += amount
        self.members[member_id].transactions.append(txn)
        self.transactions.append(txn)
        
        return txn
    
    def add_revenue_share_agreement(
        self,
        investor_id: str,
        investor_name: str,
        principal: float,
        revenue_share_pct: float = 0.05,
        repayment_multiple: float = 1.5,
    ) -> RevenueShareAgreement:
        """Create a new revenue share agreement."""
        agreement = RevenueShareAgreement(
            id=str(uuid.uuid4())[:8],
            investor_id=investor_id,
            investor_name=investor_name,
            principal=principal,
            revenue_share_pct=revenue_share_pct,
            repayment_multiple=repayment_multiple,
            start_date=date.today(),
        )
        self.agreements[agreement.id] = agreement
        return agreement
    
    def process_revenue(self, gross_revenue: float) -> Dict[str, float]:
        """Process revenue and calculate payments to investors."""
        payments = {}
        
        for agreement_id, agreement in self.agreements.items():
            if not agreement.is_complete:
                payment = agreement.calculate_payment(gross_revenue)
                if payment > 0:
                    agreement.total_repaid += payment
                    payments[agreement.investor_name] = payment
                    
                    # Record transaction
                    txn = Transaction(
                        id=str(uuid.uuid4())[:8],
                        member_id=agreement.investor_id,
                        transaction_type=TransactionType.REVENUE_SHARE,
                        amount=payment,
                        date=datetime.now(),
                        description=f"Revenue share payment ({agreement.revenue_share_pct*100:.0f}%)",
                        reference=agreement_id,
                    )
                    self.transactions.append(txn)
        
        return payments
    
    def calculate_patronage_dividends(
        self,
        surplus: float,
        patronage_records: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate patronage dividends based on member participation."""
        total_patronage = sum(patronage_records.values())
        if total_patronage == 0:
            return {}
        
        dividends = {}
        for member_id, patronage in patronage_records.items():
            share = patronage / total_patronage
            dividend = surplus * share
            dividends[member_id] = dividend
            
            if member_id in self.members:
                self.members[member_id].patronage_credits += dividend
                
                txn = Transaction(
                    id=str(uuid.uuid4())[:8],
                    member_id=member_id,
                    transaction_type=TransactionType.PATRONAGE_DIVIDEND,
                    amount=dividend,
                    date=datetime.now(),
                    description="Patronage dividend",
                )
                self.members[member_id].transactions.append(txn)
                self.transactions.append(txn)
        
        return dividends
    
    def get_community_metrics(self) -> Dict[str, Any]:
        """Get community-wide financial metrics."""
        total_capital = sum(m.capital_balance for m in self.members.values())
        total_members = len(self.members)
        total_agreements = len(self.agreements)
        active_agreements = len([a for a in self.agreements.values() if not a.is_complete])
        total_outstanding = sum(a.remaining for a in self.agreements.values())
        
        return {
            'total_members': total_members,
            'total_capital_raised': total_capital,
            'average_investment': total_capital / total_members if total_members > 0 else 0,
            'revenue_share_agreements': total_agreements,
            'active_agreements': active_agreements,
            'total_outstanding_to_investors': total_outstanding,
        }


def get_revenue_ledger() -> RevenueShareLedger:
    """Factory function for revenue share ledger."""
    return RevenueShareLedger()
