"""Tests for the governance module."""

import pytest
from core.governance import (
    QuadraticVotingEngine, Proposal, VoterAllocation, VotingResult,
    ProposalStatus, get_voting_engine
)


class TestVoterAllocation:
    """Tests for voter allocation mechanics."""

    def test_quadratic_cost(self):
        alloc = VoterAllocation(voter_id="user1", proposal_id="p1")
        assert alloc.calculate_cost(1) == 1
        assert alloc.calculate_cost(2) == 4
        assert alloc.calculate_cost(3) == 9
        assert alloc.calculate_cost(10) == 100

    def test_can_allocate(self):
        alloc = VoterAllocation(voter_id="user1", proposal_id="p1", total_credits=100)
        assert alloc.can_allocate("option1", 10)  # 100 credits = 10 votes
        assert not alloc.can_allocate("option1", 11)  # 121 > 100

    def test_allocate_votes(self):
        alloc = VoterAllocation(voter_id="user1", proposal_id="p1", total_credits=100)
        assert alloc.allocate("option1", 5)  # Costs 25
        assert alloc.credits_used == 25
        assert alloc.credits_remaining == 75

    def test_reallocate_votes(self):
        alloc = VoterAllocation(voter_id="user1", proposal_id="p1", total_credits=100)
        alloc.allocate("option1", 5)  # 25 credits
        alloc.allocate("option1", 3)  # Should now cost 9
        assert alloc.credits_used == 9


class TestQuadraticVotingEngine:
    """Tests for the voting engine."""

    def test_create_proposal(self):
        engine = QuadraticVotingEngine()
        proposal = engine.create_proposal(
            "p1", "Test Proposal", "Description", ["A", "B", "C"]
        )
        assert proposal.id == "p1"
        assert len(proposal.options) == 3

    def test_activate_proposal(self):
        engine = QuadraticVotingEngine()
        engine.create_proposal("p1", "Test", "Desc", ["A", "B"])
        assert engine.activate_proposal("p1")
        assert engine.proposals["p1"].status == ProposalStatus.ACTIVE

    def test_cast_vote(self):
        engine = QuadraticVotingEngine()
        engine.create_proposal("p1", "Test", "Desc", ["A", "B"])
        engine.activate_proposal("p1")
        
        success = engine.cast_vote("p1", "voter1", {"A": 5, "B": 3})
        assert success
        
        alloc = engine.get_voter_allocation("p1", "voter1")
        assert alloc.allocations["A"] == 5
        assert alloc.allocations["B"] == 3

    def test_cast_vote_exceeds_credits(self):
        engine = QuadraticVotingEngine(credits_per_voter=100)
        engine.create_proposal("p1", "Test", "Desc", ["A", "B"])
        engine.activate_proposal("p1")
        
        # 10 votes = 100 credits, 11 votes = 121 credits
        success = engine.cast_vote("p1", "voter1", {"A": 11})
        assert not success

    def test_tally_votes(self):
        engine = QuadraticVotingEngine()
        engine.add_member("voter1")
        engine.add_member("voter2")
        engine.create_proposal("p1", "Test", "Desc", ["A", "B"])
        engine.activate_proposal("p1")
        
        engine.cast_vote("p1", "voter1", {"A": 5, "B": 2})
        engine.cast_vote("p1", "voter2", {"A": 3, "B": 4})
        
        result = engine.tally_votes("p1")
        assert result.option_votes["A"] == 8  # 5 + 3
        assert result.option_votes["B"] == 6  # 2 + 4

    def test_winner_determination(self):
        engine = QuadraticVotingEngine()
        engine.add_member("voter1")
        engine.create_proposal("p1", "Test", "Desc", ["A", "B"])
        engine.activate_proposal("p1")
        
        engine.cast_vote("p1", "voter1", {"A": 8, "B": 2})
        
        result = engine.close_proposal("p1")
        assert result.winner == "A"
        assert result.passed


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_voting_engine(self):
        engine = get_voting_engine(credits=50)
        assert isinstance(engine, QuadraticVotingEngine)
        assert engine.credits_per_voter == 50
