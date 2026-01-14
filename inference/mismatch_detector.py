"""
Mismatch Detector for identifying GIS/LiDAR utility discrepancies.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("inference.mismatch_detector")


@dataclass
class Mismatch:
    """Represents a detected utility mismatch."""
    lat: float
    lon: float
    mismatch_type: str  # "slope", "zoning", "utility", "flood"
    severity: float  # 0.0 to 1.0
    description: str
    gis_value: str
    lidar_value: str
    predicted_utility: float
    rule_based_utility: float


class MismatchDetector:
    """
    Detects areas where GIS and LiDAR data indicate utility mismatches.
    
    Types of mismatches detected:
    1. Slope Mismatch: GIS zoning says 'buildable' but LiDAR shows steep slopes
    2. Zoning Mismatch: LiDAR shows flat land but GIS has restrictive zoning
    3. Utility Mismatch: ML prediction differs significantly from rule-based score
    4. Flood Mismatch: GIS says no flood risk but terrain suggests otherwise
    
    These mismatches represent high-value investigation targets for land analysis.
    """
    
    # Thresholds for mismatch detection
    SLOPE_BUILDABLE_MAX = 15.0  # Max slope % for easy construction
    SLOPE_DIFFICULT_MIN = 25.0  # Min slope % for difficult construction
    UTILITY_MISMATCH_THRESHOLD = 2.5  # Score difference to flag
    
    def __init__(
        self, 
        predictor=None,
        gis_loader=None,
        analyzer=None
    ):
        """
        Initialize the mismatch detector.
        
        Args:
            predictor: UtilityPredictor instance for ML predictions
            gis_loader: GISLoader instance for data queries
            analyzer: DecisionEngine instance for rule-based scoring
        """
        self.predictor = predictor
        self.gis_loader = gis_loader
        self.analyzer = analyzer
    
    def detect_slope_mismatch(self, lat: float, lon: float) -> Optional[Mismatch]:
        """
        Compare GIS zoning against LiDAR terrain data.
        
        Flags when:
        - Industrial/commercial zoning on steep terrain (>25% slope)
        - Residential zoning on very steep terrain (>30% slope)
        """
        if self.gis_loader is None:
            return None
        
        # Get terrain data
        terrain = self.gis_loader.get_lidar_elevation(lat, lon)
        zoning = self.gis_loader.get_zoning_history(lat, lon)
        
        slope = terrain.get('slope_percent', 0)
        zoning_code = zoning.get('current_zoning', 'Unknown')
        
        # Check for slope/zoning mismatch
        is_commercial_industrial = 'M-' in zoning_code or 'C-' in zoning_code
        is_residential = 'R-' in zoning_code
        
        mismatch = None
        
        if is_commercial_industrial and slope > self.SLOPE_DIFFICULT_MIN:
            severity = min(1.0, (slope - self.SLOPE_DIFFICULT_MIN) / 20.0)
            mismatch = Mismatch(
                lat=lat,
                lon=lon,
                mismatch_type="slope",
                severity=severity,
                description=f"Industrial/commercial zone on steep terrain ({slope:.1f}% slope)",
                gis_value=f"Zoning: {zoning_code}",
                lidar_value=f"Slope: {slope:.1f}%",
                predicted_utility=0.0,
                rule_based_utility=0.0
            )
        elif is_residential and slope > 30.0:
            severity = min(1.0, (slope - 30.0) / 15.0)
            mismatch = Mismatch(
                lat=lat,
                lon=lon,
                mismatch_type="slope",
                severity=severity,
                description=f"Residential zone on very steep terrain ({slope:.1f}% slope)",
                gis_value=f"Zoning: {zoning_code}",
                lidar_value=f"Slope: {slope:.1f}%",
                predicted_utility=0.0,
                rule_based_utility=0.0
            )
        
        return mismatch
    
    def detect_zoning_opportunity(self, lat: float, lon: float) -> Optional[Mismatch]:
        """
        Find flat, accessible land with restrictive zoning.
        
        These may represent rezoning opportunities.
        """
        if self.gis_loader is None:
            return None
        
        terrain = self.gis_loader.get_lidar_elevation(lat, lon)
        zoning = self.gis_loader.get_zoning_history(lat, lon)
        utilities = self.gis_loader.get_utility_proximity(lat, lon)
        
        slope = terrain.get('slope_percent', 100)
        zoning_code = zoning.get('current_zoning', 'Unknown')
        water_dist = utilities.get('distance_to_water_main_ft', 9999)
        sewer_dist = utilities.get('distance_to_sewer_ft', 9999)
        
        # Flat land with good utility access but restrictive zoning
        is_flat = slope < self.SLOPE_BUILDABLE_MAX
        has_utilities = water_dist < 500 and sewer_dist < 500
        is_restricted = 'A-' in zoning_code  # Agricultural
        
        if is_flat and has_utilities and is_restricted:
            severity = 0.7  # Moderate opportunity
            return Mismatch(
                lat=lat,
                lon=lon,
                mismatch_type="zoning",
                severity=severity,
                description=f"Flat serviced land with restrictive zoning ({zoning_code})",
                gis_value=f"Zoning: {zoning_code}",
                lidar_value=f"Slope: {slope:.1f}%, Utils nearby",
                predicted_utility=0.0,
                rule_based_utility=0.0
            )
        
        return None
    
    def detect_utility_mismatch(self, quantum_dict: Dict) -> Optional[Mismatch]:
        """
        Compare ML prediction vs rule-based calculation.
        
        Large differences may indicate:
        - Model bias that needs correction
        - Unique situations not captured by rules
        - Data quality issues
        """
        if self.predictor is None or self.analyzer is None:
            return None
        
        # Get both predictions
        ml_score = self.predictor.predict(quantum_dict)
        rule_result = self.analyzer.calculate_gross_utility_from_dict(quantum_dict)
        rule_score = rule_result.get('score', 0)
        
        diff = abs(ml_score - rule_score)
        
        if diff > self.UTILITY_MISMATCH_THRESHOLD:
            severity = min(1.0, diff / 5.0)
            return Mismatch(
                lat=quantum_dict.get('lat', 0),
                lon=quantum_dict.get('lon', 0),
                mismatch_type="utility",
                severity=severity,
                description=f"ML prediction ({ml_score:.1f}) differs from rules ({rule_score:.1f})",
                gis_value=f"Rule-based: {rule_score:.1f}",
                lidar_value=f"ML predicted: {ml_score:.1f}",
                predicted_utility=ml_score,
                rule_based_utility=rule_score
            )
        
        return None
    
    def detect_flood_terrain_mismatch(self, lat: float, lon: float) -> Optional[Mismatch]:
        """
        Compare FEMA flood zones against LiDAR terrain.
        
        Flags low-lying areas not in flood zone (may be under-assessed risk).
        """
        if self.gis_loader is None:
            return None
        
        terrain = self.gis_loader.get_lidar_elevation(lat, lon)
        climate = self.gis_loader.get_climate_risk(lat, lon)
        
        elevation_ft = terrain.get('elevation_ft', 100)
        flood_score = climate.get('flood_risk_score', 5)
        
        # Low elevation but low flood risk - potential mismatch
        if elevation_ft < 30 and flood_score < 4:
            severity = 0.6
            return Mismatch(
                lat=lat,
                lon=lon,
                mismatch_type="flood",
                severity=severity,
                description=f"Low elevation ({elevation_ft:.0f}ft) not in high flood zone",
                gis_value=f"FEMA flood score: {flood_score}/10",
                lidar_value=f"Elevation: {elevation_ft:.0f}ft",
                predicted_utility=0.0,
                rule_based_utility=0.0
            )
        
        return None
    
    def scan_quantum(self, quantum_dict: Dict) -> List[Mismatch]:
        """
        Run all mismatch detections on a single quantum.
        
        Returns:
            List of all detected mismatches
        """
        lat = quantum_dict.get('lat', 0)
        lon = quantum_dict.get('lon', 0)
        
        mismatches = []
        
        # Run all detectors
        detectors = [
            lambda: self.detect_slope_mismatch(lat, lon),
            lambda: self.detect_zoning_opportunity(lat, lon),
            lambda: self.detect_utility_mismatch(quantum_dict),
            lambda: self.detect_flood_terrain_mismatch(lat, lon),
        ]
        
        for detector in detectors:
            try:
                result = detector()
                if result:
                    mismatches.append(result)
            except Exception as e:
                log.debug(f"Detector failed: {e}")
        
        return mismatches
    
    def scan_region(
        self, 
        quanta: List[Dict],
        min_severity: float = 0.5
    ) -> List[Mismatch]:
        """
        Scan all quanta in a region for mismatches.
        
        Args:
            quanta: List of quantum dictionaries
            min_severity: Minimum severity to include in results
            
        Returns:
            List of mismatches sorted by severity (highest first)
        """
        all_mismatches = []
        
        for quantum in quanta:
            mismatches = self.scan_quantum(quantum)
            all_mismatches.extend(mismatches)
        
        # Filter by severity and sort
        filtered = [m for m in all_mismatches if m.severity >= min_severity]
        filtered.sort(key=lambda m: m.severity, reverse=True)
        
        log.info(f"Found {len(filtered)} mismatches (severity >= {min_severity})")
        return filtered
    
    def generate_report(self, mismatches: List[Mismatch]) -> str:
        """Generate a human-readable report of mismatches."""
        if not mismatches:
            return "No mismatches detected."
        
        lines = [
            "=" * 60,
            "MISMATCH DETECTION REPORT",
            "=" * 60,
            f"Total mismatches: {len(mismatches)}",
            "",
        ]
        
        # Group by type
        by_type = {}
        for m in mismatches:
            by_type.setdefault(m.mismatch_type, []).append(m)
        
        for mtype, items in by_type.items():
            lines.append(f"\n{mtype.upper()} MISMATCHES ({len(items)}):")
            lines.append("-" * 40)
            for m in items[:5]:  # Top 5 per type
                lines.append(f"  [{m.severity:.0%}] {m.description}")
                lines.append(f"         @ {m.lat:.4f}, {m.lon:.4f}")
        
        return "\n".join(lines)
