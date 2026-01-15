"""
Advanced Scoring Module

Implements synergy-based scoring with:
- Interaction terms (feature combinations)
- Diminishing returns (prevent clustering)
- Use-case specific profiles
- Confidence weighting
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# USE CASE PROFILES
# ═══════════════════════════════════════════════════════════════════════════
class UseCase(Enum):
    """Predefined use case profiles for land utility analysis."""
    GENERAL = "general"
    DESALINATION = "desalination_plant"
    SILICON_FAB = "silicon_wafer_fab"
    WAREHOUSE = "warehouse_distribution"
    MANUFACTURING = "light_manufacturing"
    AGRICULTURAL = "agricultural_processing"


@dataclass
class UseCaseProfile:
    """Configuration for a specific use case scoring profile."""
    
    name: str
    description: str
    
    # Feature weights (positive = bonus, negative = penalty)
    feature_weights: Dict[str, float] = field(default_factory=dict)
    
    # Synergy bonuses (pairs that work well together)
    synergies: Dict[Tuple[str, str], float] = field(default_factory=dict)
    
    # Anti-synergies (pairs that conflict)
    anti_synergies: Dict[Tuple[str, str], float] = field(default_factory=dict)
    
    # Minimum requirements (must have these features)
    requirements: List[str] = field(default_factory=list)
    
    # Deal breakers (cannot have these features)
    disqualifiers: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# PREDEFINED PROFILES
# ═══════════════════════════════════════════════════════════════════════════
PROFILES = {
    UseCase.GENERAL: UseCaseProfile(
        name="General Industrial",
        description="Balanced scoring for general industrial development",
        feature_weights={
            "has_road": 1.0,
            "has_water": 1.0,
            "is_industrial": 1.5,
            "is_commercial": 1.0,
            "is_residential": -0.5,
            "is_agricultural": -0.5,
            "has_power_nearby": 1.0,
            "rail_nearby": 0.5,
            "flood_risk": -1.5,
            "high_elevation": -0.5,
        },
        synergies={
            ("has_water", "is_industrial"): 1.0,
            ("has_road", "has_power_nearby"): 0.5,
        },
    ),
    
    UseCase.DESALINATION: UseCaseProfile(
        name="Desalination Plant",
        description="Optimized for reverse osmosis desalination facility",
        feature_weights={
            # Critical requirements
            "coastal_access": 4.0,
            "has_power_nearby": 3.0,
            "is_industrial": 2.5,
            
            # Beneficial
            "has_road": 1.5,
            "highway_nearby": 1.0,
            "low_elevation": 1.0,
            
            # Less important
            "rail_nearby": 0.5,
            "urban_area": 0.5,  # Near population to serve
            
            # Penalties
            "is_residential": -2.0,
            "is_agricultural": -1.0,
            "high_elevation": -2.5,  # Pumping costs
            "protected_habitat": -5.0,  # Major constraint
        },
        synergies={
            ("coastal_access", "is_industrial"): 2.5,  # Perfect combo
            ("coastal_access", "has_power_nearby"): 2.0,
            ("low_elevation", "coastal_access"): 1.5,
            ("has_power_nearby", "is_industrial"): 1.0,
        },
        anti_synergies={
            ("coastal_access", "is_residential"): -2.0,  # Conflict
            ("coastal_access", "protected_habitat"): -3.0,
        },
        requirements=["coastal_access", "has_power_nearby"],
        disqualifiers=["protected_habitat"],
    ),
    
    UseCase.SILICON_FAB: UseCaseProfile(
        name="Silicon Wafer Fabrication",
        description="Optimized for semiconductor manufacturing",
        feature_weights={
            # Critical requirements
            "has_power_nearby": 4.0,  # Huge power needs
            "has_water": 3.0,  # Ultra-pure water needed
            "is_industrial": 2.5,
            
            # Beneficial
            "highway_nearby": 1.5,
            "has_road": 1.5,
            "has_manufacturing": 1.0,  # Skilled workforce
            "low_unemployment": 0.5,
            
            # Constraints
            "is_residential": -1.5,
            "flood_risk": -3.0,  # Cannot flood
            "high_elevation": -1.0,
            "is_agricultural": -0.5,
        },
        synergies={
            ("has_power_nearby", "is_industrial"): 2.0,
            ("has_water", "is_industrial"): 1.5,
            ("highway_nearby", "has_manufacturing"): 1.0,
        },
        anti_synergies={
            ("flood_risk", "is_industrial"): -2.0,
        },
        requirements=["has_power_nearby", "has_water"],
        disqualifiers=["flood_risk"],
    ),
    
    UseCase.WAREHOUSE: UseCaseProfile(
        name="Warehouse/Distribution",
        description="Optimized for logistics and distribution centers",
        feature_weights={
            "highway_nearby": 3.0,
            "has_road": 2.0,
            "rail_nearby": 2.0,
            "is_industrial": 2.0,
            "port_nearby": 1.5,
            "has_power_nearby": 0.5,
            
            "is_residential": -1.5,
            "high_elevation": -1.0,
        },
        synergies={
            ("highway_nearby", "rail_nearby"): 2.5,  # Multi-modal
            ("highway_nearby", "port_nearby"): 2.0,
            ("is_industrial", "highway_nearby"): 1.0,
        },
    ),
    
    UseCase.MANUFACTURING: UseCaseProfile(
        name="Light Manufacturing",
        description="Optimized for general manufacturing facilities",
        feature_weights={
            "is_industrial": 2.5,
            "has_power_nearby": 2.0,
            "has_road": 1.5,
            "has_water": 1.0,
            "highway_nearby": 1.0,
            "has_manufacturing": 0.5,
            
            "is_residential": -1.5,
            "is_agricultural": -0.5,
        },
        synergies={
            ("is_industrial", "has_power_nearby"): 1.5,
            ("has_road", "highway_nearby"): 1.0,
        },
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# SYNERGY SCORER
# ═══════════════════════════════════════════════════════════════════════════
class SynergyScorer:
    """
    Advanced scoring engine with synergies and diminishing returns.
    
    The scoring formula is:
    
    final_score = diminish(
        base_score + 
        Σ(feature_weight × feature_value) +
        Σ(synergy_bonus if both features present) +
        Σ(anti_synergy_penalty if conflicting features)
    )
    
    Where diminish() prevents clustering at extremes.
    """
    
    def __init__(self, use_case: UseCase = UseCase.GENERAL):
        self.use_case = use_case
        self.profile = PROFILES.get(use_case, PROFILES[UseCase.GENERAL])
    
    def score(
        self, 
        features: Dict[str, Any],
        base_score: float = 5.0,
        apply_diminishing: bool = True,
        detailed: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate utility score for a location.
        
        Args:
            features: Dictionary of feature name -> value
            base_score: Starting score (middle of 0-10 scale)
            apply_diminishing: Whether to apply diminishing returns
            detailed: If True, return breakdown of score components
            
        Returns:
            {"score": float, "breakdown": {...}} if detailed
            Just the score (float) otherwise
        """
        score = base_score
        breakdown = {
            "base": base_score,
            "features": {},
            "synergies": {},
            "anti_synergies": {},
            "requirements_met": True,
            "disqualified": False,
        }
        
        # Check disqualifiers first
        for disq in self.profile.disqualifiers:
            if features.get(disq):
                breakdown["disqualified"] = True
                breakdown["disqualifier"] = disq
                if detailed:
                    return {"score": 0.0, "breakdown": breakdown}
                return 0.0
        
        # Check requirements
        for req in self.profile.requirements:
            if not features.get(req):
                breakdown["requirements_met"] = False
                breakdown["missing_requirement"] = req
                score -= 3.0  # Significant penalty for missing requirements
        
        # Apply feature weights
        for feature, weight in self.profile.feature_weights.items():
            value = features.get(feature)
            
            if isinstance(value, bool):
                if value:
                    contribution = weight
                else:
                    contribution = 0
            elif isinstance(value, (int, float)):
                # For numeric features, scale by the value
                # Normalize - most numeric features are distances
                if "distance" in feature.lower():
                    # Invert distance (closer = better, weight is negative)
                    contribution = weight  # Weight already encodes preference
                else:
                    contribution = weight * min(1.0, value / 100)  # Normalize
            else:
                contribution = 0
            
            if contribution != 0:
                breakdown["features"][feature] = contribution
                score += contribution
        
        # Apply synergies
        for (feat1, feat2), bonus in self.profile.synergies.items():
            if features.get(feat1) and features.get(feat2):
                breakdown["synergies"][f"{feat1}+{feat2}"] = bonus
                score += bonus
        
        # Apply anti-synergies
        for (feat1, feat2), penalty in self.profile.anti_synergies.items():
            if features.get(feat1) and features.get(feat2):
                breakdown["anti_synergies"][f"{feat1}+{feat2}"] = penalty
                score += penalty  # Penalty is already negative
        
        # Apply diminishing returns
        if apply_diminishing:
            score = self._apply_diminishing_returns(score, base_score)
        
        # Clamp to 0-10
        final_score = max(0.0, min(10.0, score))
        
        breakdown["raw_score"] = score
        breakdown["final_score"] = final_score
        
        if detailed:
            return {"score": final_score, "breakdown": breakdown}
        return final_score
    
    def _apply_diminishing_returns(self, score: float, base: float) -> float:
        """
        Apply diminishing returns to prevent clustering at extremes.
        
        Uses log scaling for positive deltas and linear for negative.
        """
        delta = score - base
        
        if delta > 0:
            # Positive scores diminish
            # log1p(x) = log(1+x), gives diminishing returns
            return base + math.log1p(delta) * 2.5
        else:
            # Negative scores are linear but slightly dampened
            return base + delta * 0.8
    
    def explain_score(self, features: Dict[str, Any]) -> str:
        """Generate human-readable explanation of score."""
        result = self.score(features, detailed=True)
        breakdown = result["breakdown"]
        
        lines = [f"Score: {result['score']:.1f}/10"]
        lines.append(f"Use Case: {self.profile.name}")
        lines.append("")
        
        if breakdown["disqualified"]:
            lines.append(f"⛔ DISQUALIFIED: {breakdown['disqualifier']}")
            return "\n".join(lines)
        
        if not breakdown["requirements_met"]:
            lines.append(f"⚠️ Missing requirement: {breakdown['missing_requirement']}")
        
        lines.append("Feature contributions:")
        for feat, contrib in breakdown["features"].items():
            sign = "+" if contrib > 0 else ""
            lines.append(f"  {feat}: {sign}{contrib:.1f}")
        
        if breakdown["synergies"]:
            lines.append("\nSynergy bonuses:")
            for syn, bonus in breakdown["synergies"].items():
                lines.append(f"  {syn}: +{bonus:.1f}")
        
        if breakdown["anti_synergies"]:
            lines.append("\nConflicts:")
            for anti, penalty in breakdown["anti_synergies"].items():
                lines.append(f"  {anti}: {penalty:.1f}")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════
def get_scorer(use_case: UseCase = UseCase.GENERAL) -> SynergyScorer:
    """Get a scorer for the specified use case."""
    return SynergyScorer(use_case)


def get_desalination_scorer() -> SynergyScorer:
    """Get scorer optimized for desalination plants."""
    return SynergyScorer(UseCase.DESALINATION)


def get_silicon_fab_scorer() -> SynergyScorer:
    """Get scorer optimized for silicon wafer fabrication."""
    return SynergyScorer(UseCase.SILICON_FAB)


def list_use_cases() -> List[Dict[str, str]]:
    """List all available use case profiles."""
    return [
        {"id": uc.value, "name": PROFILES[uc].name, "description": PROFILES[uc].description}
        for uc in UseCase
        if uc in PROFILES
    ]
