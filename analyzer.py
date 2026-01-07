from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Property:
    id: str
    acres: float
    zoning: str  # e.g., "M-1" (Light Industrial), "R-1" (Residential), "A-1" (Agriculture)
    slope_percent: float
    distance_to_water_source_ft: float
    solar_exposure_score: float  # 0.0 to 1.0
    in_coastal_zone: bool
    flood_risk_zone: bool
    description: str = "" # Text description for vector search

@dataclass
class UtilizationResult:
    recommendation: str
    confidence_score: float
    reasoning_trace: List[str]

class DecisionEngine:
    """
    The 'Brain' that uses a human-parsible decision tree to recommend land use.
    """

    def analyze(self, prop: Property) -> UtilizationResult:
        traces = []
        
        traces.append(f"Analyzing Property: {prop.id} ({prop.acres} acres, Zoning: {prop.zoning})")

        # Play 1: High-Density Vertical Hydroponics (The "Water Pivot")
        # Needs: Industrial/Ag zoning, flat land, good water access
        hydro_score = self._evaluate_hydroponics(prop, traces)
        
        # Play 2: Dense Residential
        # Needs: Residential zoning, low flood risk
        residential_score = self._evaluate_residential(prop, traces)

        # Play 3: Conservation / Carbon Credits
        # Good for: Steep slopes, coastal zones, flood zones
        conservation_score = self._evaluate_conservation(prop, traces)

        # Decision
        best_score = max(hydro_score, residential_score, conservation_score)
        
        if best_score < 0.5:
             return UtilizationResult(
                recommendation="Hold / Land Banking (No obvious immediate utility)",
                confidence_score=best_score,
                reasoning_trace=traces
            )
        
        if hydro_score == best_score:
            rec = "Vertical Hydroponics / Agri-Tech Facility"
        elif residential_score == best_score:
            rec = "High-Density Residential Development"
        else:
            rec = "Conservation Easement / Carbon Credit Bank"

        return UtilizationResult(
            recommendation=rec,
            confidence_score=best_score,
            reasoning_trace=traces
        )

    def _evaluate_hydroponics(self, prop: Property, trace: List[str]) -> float:
        score = 0.0
        trace.append("--- Evaluating: Vertical Hydroponics ---")
        
        # Rule 1: Zoning
        if prop.zoning in ["M-1", "A-1", "C-3"]: # Industrial, Ag, Commercial
            score += 0.4
            trace.append("[PASS] Zoning allows commercial/industrial/ag use.")
        else:
            trace.append("[FAIL] Zoning is strictly Residential (R-1) or restricted.")
            return 0.0 # Hard Stop

        # Rule 2: Slope (Needs flat pads)
        if prop.slope_percent > 20.0:
            trace.append(f"[FAIL] Slope {prop.slope_percent}% is too steep for industrial facility.")
            return 0.0 # HARD STOP for Industrial

        if prop.slope_percent < 10:
            score += 0.2
            trace.append(f"[PASS] Slope {prop.slope_percent}% is suitable for construction.")
        else:
            score -= 0.1
            trace.append(f"[WARNING] Slope {prop.slope_percent}% requires grading.")

        # Rule 3: Water Access
        if prop.distance_to_water_source_ft < 500:
            score += 0.3
            trace.append("[PASS] Close proximity to water source.")
        else:
            trace.append("[FAIL] Too far from water infrastructure.")
        
        # Rule 4: Solar for Energy Offset
        if prop.solar_exposure_score > 0.7:
             score += 0.1
             trace.append("[BONUS] High solar potential for OpEx reduction.")

        return score

    def _evaluate_residential(self, prop: Property, trace: List[str]) -> float:
        score = 0.0
        trace.append("--- Evaluating: Residential Development ---")

        if prop.zoning in ["R-1", "R-M", "MU"]:
             score += 0.5
             trace.append("[PASS] Residential Zoning confirmed.")
        elif prop.zoning == "A-1":
            # Sometimes Ag has dwelling rights, but low density
             score += 0.1
             trace.append("[INFO] Agriculture land allows limited housing.")
        else:
             trace.append("[FAIL] Non-residential zoning.")
             return 0.0

        if prop.slope_percent > 30.0:
            trace.append(f"[FAIL] Slope {prop.slope_percent}% is unbuildable for dense residential.")
            return 0.0 # HARD STOP

        if prop.flood_risk_zone:
            score -= 0.3
            trace.append("[CRITICAL] Property is in a Flood Zone.")
        
        if prop.in_coastal_zone:
             # Coastal Commission headache
             score -= 0.2
             trace.append("[WARNING] Coastal Zone requires extra permitting.")
        
        return score

    def calculate_gross_utility(self, quantum) -> dict:
        # Returns dict with score and trace
        # Formula: GUS = (W * 3.0) + (R * 2.0) + (I * 4.0)
        
        score = 0.0
        trace = []
        
        if quantum.has_water_infrastructure:
            score += 3.0 
            trace.append("Water Access (+3.0)")
        
        if quantum.has_road_access:
            score += 2.0 
            trace.append("Road Access (+2.0)")
            
        if quantum.zoning_type == "Industrial":
            score += 4.0 
            trace.append("Industrial Zoning (+4.0)")
        elif quantum.zoning_type == "Residential":
            score += 1.0 
            trace.append("Residential Zoning (+1.0)")
            
        return {
            "score": score,
            "trace": trace
        }

    def _evaluate_conservation(self, prop: Property, trace: List[str]) -> float:
        score = 0.0
        trace.append("--- Evaluating: Conservation / Carbon ---")
        
        # Conservation is the 'Fallback' for difficult land
        if prop.slope_percent > 30:
            score += 0.4
            trace.append("[PASS] Steep slope makes development hard, ideal for conservation.")
        
        if prop.in_coastal_zone:
            score += 0.3
            trace.append("[PASS] Coastal habitat is high value for preservation.")
        
        if prop.flood_risk_zone:
            score += 0.2
            trace.append("[PASS] Floodway preservation.")

        return score
