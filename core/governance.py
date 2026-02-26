"""
Governance Module - Democratic decision making for organizations.

Implements quadratic voting where vote cost = votes^2, protecting minority
interests while capturing intensity of preference.
Includes persistence for organizations and their voting history.
"""

import math
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from pathlib import Path
import logging

log = logging.getLogger(__name__)

class ProposalStatus(Enum):
    """Status of a voting proposal."""
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class Proposal:
    """A proposal for quadratic voting."""
    id: str
    title: str
    description: str
    options: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    closes_at: Optional[datetime] = None
    status: ProposalStatus = ProposalStatus.DRAFT
    minimum_participation: float = 0.25  # 25% of members must vote
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'options': self.options,
            'created_at': self.created_at.isoformat(),
            'closes_at': self.closes_at.isoformat() if self.closes_at else None,
            'status': self.status.value,
            'minimum_participation': self.minimum_participation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Proposal':
        return cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            options=data['options'],
            created_at=datetime.fromisoformat(data['created_at']),
            closes_at=datetime.fromisoformat(data['closes_at']) if data.get('closes_at') else None,
            status=ProposalStatus(data['status']),
            minimum_participation=data.get('minimum_participation', 0.25)
        )


@dataclass
class VoterAllocation:
    """A voter's allocation of voice credits."""
    voter_id: str
    proposal_id: str
    allocations: Dict[str, int] = field(default_factory=dict)  # option -> votes
    credits_used: int = 0
    total_credits: int = 100
    
    @property
    def credits_remaining(self) -> int:
        return self.total_credits - self.credits_used
    
    def calculate_cost(self, votes: int) -> int:
        """Quadratic cost: votes^2."""
        return votes * votes
    
    def can_allocate(self, option: str, votes: int) -> bool:
        """Check if voter can allocate this many votes."""
        current = self.allocations.get(option, 0)
        current_cost = self.calculate_cost(current)
        new_cost = self.calculate_cost(votes)
        additional_cost = new_cost - current_cost
        return additional_cost <= self.credits_remaining
    
    def allocate(self, option: str, votes: int) -> bool:
        """Allocate votes to an option. Returns True if successful."""
        if not self.can_allocate(option, votes):
            return False
        
        # Remove old allocation cost
        current = self.allocations.get(option, 0)
        self.credits_used -= self.calculate_cost(current)
        
        # Add new allocation
        self.allocations[option] = votes
        self.credits_used += self.calculate_cost(votes)
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'voter_id': self.voter_id,
            'proposal_id': self.proposal_id,
            'allocations': self.allocations,
            'credits_used': self.credits_used,
            'total_credits': self.total_credits,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoterAllocation':
        return cls(
            voter_id=data['voter_id'],
            proposal_id=data.get('proposal_id', 'unknown'),
            allocations=data['allocations'],
            credits_used=data['credits_used'],
            total_credits=data.get('total_credits', 100)
        )


@dataclass
class VotingResult:
    """Result of a quadratic vote."""
    proposal_id: str
    option_votes: Dict[str, int]  # option -> total votes
    option_voters: Dict[str, int]  # option -> number of voters
    total_voters: int
    total_eligible: int
    participation_rate: float
    winner: Optional[str]
    passed: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proposal_id': self.proposal_id,
            'option_votes': self.option_votes,
            'option_voters': self.option_voters,
            'total_voters': self.total_voters,
            'total_eligible': self.total_eligible,
            'participation_rate': self.participation_rate,
            'winner': self.winner,
            'passed': self.passed,
        }


class QuadraticVotingEngine:
    """Engine for managing quadratic voting."""
    
    def __init__(self, credits_per_voter: int = 100):
        self.credits_per_voter = credits_per_voter
        self.proposals: Dict[str, Proposal] = {}
        self.allocations: Dict[str, Dict[str, VoterAllocation]] = {}  # proposal_id -> {voter_id -> allocation}
        self.members: Dict[str, bool] = {}  # voter_id -> is_verified
    
    def add_member(self, voter_id: str, verified: bool = True):
        """Add a member to the voting system."""
        self.members[voter_id] = verified
    
    def create_proposal(
        self,
        proposal_id: str,
        title: str,
        description: str,
        options: List[str]
    ) -> Proposal:
        """Create a new voting proposal."""
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            options=options,
        )
        self.proposals[proposal_id] = proposal
        self.allocations[proposal_id] = {}
        return proposal
    
    def activate_proposal(self, proposal_id: str) -> bool:
        """Activate a proposal for voting."""
        if proposal_id not in self.proposals:
            return False
        self.proposals[proposal_id].status = ProposalStatus.ACTIVE
        return True
    
    def get_voter_allocation(self, proposal_id: str, voter_id: str) -> VoterAllocation:
        """Get or create voter allocation."""
        if proposal_id not in self.allocations:
            self.allocations[proposal_id] = {}
        
        if voter_id not in self.allocations[proposal_id]:
            self.allocations[proposal_id][voter_id] = VoterAllocation(
                voter_id=voter_id,
                proposal_id=proposal_id,
                total_credits=self.credits_per_voter,
            )
        
        return self.allocations[proposal_id][voter_id]
    
    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        allocations: Dict[str, int]
    ) -> bool:
        """Cast a quadratic vote with allocations to each option."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.status != ProposalStatus.ACTIVE:
            return False
        
        # Verify all options are valid
        for option in allocations.keys():
            if option not in proposal.options:
                return False
        
        voter = self.get_voter_allocation(proposal_id, voter_id)
        
        # Calculate total cost
        total_cost = sum(v * v for v in allocations.values())
        if total_cost > self.credits_per_voter:
            return False
        
        # Apply allocations
        voter.allocations = allocations
        voter.credits_used = total_cost
        return True
    
    def tally_votes(self, proposal_id: str) -> VotingResult:
        """Tally votes and determine result."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        option_votes: Dict[str, int] = {opt: 0 for opt in proposal.options}
        option_voters: Dict[str, int] = {opt: 0 for opt in proposal.options}
        
        voters = self.allocations.get(proposal_id, {})
        
        for voter_id, allocation in voters.items():
            for option, votes in allocation.allocations.items():
                if votes > 0:
                    option_votes[option] += votes
                    option_voters[option] += 1
        
        total_voters = len(voters)
        total_eligible = len([m for m, v in self.members.items() if v])
        participation = total_voters / total_eligible if total_eligible > 0 else 0
        
        # Determine winner
        winner = None
        max_votes = 0
        for option, votes in option_votes.items():
            if votes > max_votes:
                max_votes = votes
                winner = option
        
        passed = participation >= proposal.minimum_participation
        
        return VotingResult(
            proposal_id=proposal_id,
            option_votes=option_votes,
            option_voters=option_voters,
            total_voters=total_voters,
            total_eligible=total_eligible,
            participation_rate=participation,
            winner=winner if passed else None,
            passed=passed,
        )
    
    def close_proposal(self, proposal_id: str) -> VotingResult:
        """Close voting and finalize result."""
        result = self.tally_votes(proposal_id)
        
        proposal = self.proposals[proposal_id]
        proposal.status = ProposalStatus.PASSED if result.passed else ProposalStatus.FAILED
        
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialize engine state."""
        return {
            'credits_per_voter': self.credits_per_voter,
            'members': self.members,
            'proposals': {pid: p.to_dict() for pid, p in self.proposals.items()},
            'allocations': {
                pid: {vid: alloc.to_dict() for vid, alloc in p_allocs.items()}
                for pid, p_allocs in self.allocations.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuadraticVotingEngine':
        """Deserialize engine state."""
        engine = cls(credits_per_voter=data.get('credits_per_voter', 100))
        engine.members = data.get('members', {})

        # Load proposals
        for pid, p_data in data.get('proposals', {}).items():
            engine.proposals[pid] = Proposal.from_dict(p_data)

        # Load allocations
        for pid, p_allocs in data.get('allocations', {}).items():
            engine.allocations[pid] = {}
            for vid, a_data in p_allocs.items():
                engine.allocations[pid][vid] = VoterAllocation.from_dict(a_data)

        return engine


@dataclass
class Organization:
    """An organization managed by the platform."""
    id: str
    name: str
    type: str  # EntityType value
    voting_engine: QuadraticVotingEngine
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'created_at': self.created_at.isoformat(),
            'voting_engine': self.voting_engine.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Organization':
        return cls(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            created_at=datetime.fromisoformat(data['created_at']),
            voting_engine=QuadraticVotingEngine.from_dict(data['voting_engine'])
        )


class GovernanceManager:
    """Manages organization persistence and retrieval."""

    DATA_DIR = Path("governance_data")

    def __init__(self):
        self.DATA_DIR.mkdir(exist_ok=True)

    def create_organization(self, name: str, type_str: str, org_id: str = None) -> Organization:
        """Create and save a new organization."""
        if not org_id:
            import uuid
            org_id = str(uuid.uuid4())[:8]

        org = Organization(
            id=org_id,
            name=name,
            type=type_str,
            voting_engine=QuadraticVotingEngine()
        )
        self.save_organization(org)
        return org

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Load an organization by ID."""
        path = self.DATA_DIR / f"{org_id}.json"
        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return Organization.from_dict(data)
        except Exception as e:
            log.error(f"Failed to load organization {org_id}: {e}")
            return None

    def list_organizations(self) -> List[Organization]:
        """List all organizations."""
        orgs = []
        for file in self.DATA_DIR.glob("*.json"):
            org = self.get_organization(file.stem)
            if org:
                orgs.append(org)
        return sorted(orgs, key=lambda o: o.created_at, reverse=True)

    def save_organization(self, org: Organization):
        """Save organization state to disk."""
        path = self.DATA_DIR / f"{org.id}.json"
        with open(path, 'w') as f:
            json.dump(org.to_dict(), f, indent=2)


def get_voting_engine(credits: int = 100) -> QuadraticVotingEngine:
    """Factory function for voting engine (legacy support)."""
    return QuadraticVotingEngine(credits_per_voter=credits)
