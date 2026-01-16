import pytest
from core.scoring import get_scorer, UseCase, UseCaseProfile

def test_scorer_factory():
    """Verify factory returns correct scorer type."""
    scorer = get_scorer(UseCase.GENERAL)
    assert scorer.use_case == UseCase.GENERAL
    assert scorer.profile.name == "General Industrial"
    
    scorer_desal = get_scorer(UseCase.DESALINATION)
    assert scorer_desal.use_case == UseCase.DESALINATION
    assert "Desalination" in scorer_desal.profile.name

def test_score_basics():
    """Verify basic scoring logic."""
    scorer = get_scorer(UseCase.GENERAL)
    features = {
        "is_industrial": True,  # +1.5
        "has_water": True,      # +1.0
        "has_road": True,       # +1.0
        # + Synergy(water, industrial) = 1.0
        # Base = 5.0
        # Total = 5 + 1.5 + 1 + 1 + 1 = 9.5
    }
    score = scorer.score(features, apply_diminishing=False)
    assert score == 9.5

def test_requirements_failure():
    """Verify missing requirements penalize score."""
    scorer = get_scorer(UseCase.DESALINATION)
    # Missing coastal_access (required)
    features = {
        "has_power_nearby": True,
        "is_industrial": True
    }
    result = scorer.score(features, detailed=True)
    assert not result["breakdown"]["requirements_met"]
    # Penalty applied
    assert result["score"] < 10.0 # Just ensure penalty exists

def test_disqualifier():
    """Verify disqualifiers zero out the score."""
    scorer = get_scorer(UseCase.DESALINATION)
    features = {
        "coastal_access": True,
        "has_power_nearby": True,
        "protected_habitat": True # Disqualifier
    }
    score = scorer.score(features)
    assert score == 0.0

def test_explain_score():
    """Verify explanation generation."""
    scorer = get_scorer(UseCase.GENERAL)
    features = {"is_industrial": True}
    explanation = scorer.explain_score(features)
    assert "Score:" in explanation
    assert "is_industrial" in explanation
