"""
Core data models for Land Utility Engine.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class LandQuantum:
    """
    A single spatial cell representing a micro-sector of land.
    This is the fundamental unit of analysis in the grid system.
    """
    x: int
    y: int
    lat: float
    lon: float
    has_water_infrastructure: bool = False
    has_road_access: bool = False
    has_power_infrastructure: bool = False
    zoning_type: str = "Unknown"
    gross_utility_score: float = 0.0
    debug_notes: List[str] = field(default_factory=list)
    
    # Extended attributes for ML inference
    lidar_elevation: float = 0.0
    lidar_slope: float = 0.0
    lidar_aspect: float = 0.0
    flood_risk_zone: bool = False
    fire_hazard_zone: bool = False
    parcel_value: float = 0.0


@dataclass
class Property:
    """
    A property parcel with zoning and physical attributes.
    Used for higher-level decision analysis.
    """
    id: str
    acres: float
    zoning: str  # e.g., "M-1" (Light Industrial), "R-1" (Residential), "A-1" (Agriculture)
    slope_percent: float
    distance_to_water_source_ft: float
    solar_exposure_score: float  # 0.0 to 1.0
    in_coastal_zone: bool
    flood_risk_zone: bool
    description: str = ""  # Text description for vector search


@dataclass
class UtilizationResult:
    """
    The output of a land utilization analysis.
    Contains the recommendation, confidence, and reasoning trace.
    """
    recommendation: str
    confidence_score: float
    reasoning_trace: List[str]


@dataclass
class MismatchResult:
    """
    Result of a GIS/LiDAR utility mismatch detection.
    Identifies discrepancies between data sources.
    """
    lat: float
    lon: float
    mismatch_type: str  # "slope", "zoning", "utility"
    gis_value: str
    lidar_value: str
    predicted_utility: float
    rule_based_utility: float
    severity: float  # 0.0 to 1.0
    description: str
