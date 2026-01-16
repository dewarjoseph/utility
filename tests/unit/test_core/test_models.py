import pytest
from core.models import LandQuantum, Property, UtilizationResult, MismatchResult

def test_land_quantum_initialization():
    """Verify LandQuantum defaults and initialization."""
    lq = LandQuantum(x=0, y=0, lat=37.0, lon=-122.0)
    assert lq.x == 0
    assert lq.y == 0
    assert lq.lat == 37.0
    assert lq.lon == -122.0
    assert lq.has_water_infrastructure is False
    assert lq.debug_notes == []
    
    # Check default mL attributes
    assert lq.lidar_elevation == 0.0
    assert lq.zoning_type == "Unknown"

def test_property_initialization():
    """Verify Property data class."""
    prop = Property(
        id="prop-1",
        acres=5.0,
        zoning="R-1",
        slope_percent=10.0,
        distance_to_water_source_ft=500.0,
        solar_exposure_score=0.8,
        in_coastal_zone=False,
        flood_risk_zone=False
    )
    assert prop.id == "prop-1"
    assert prop.zoning == "R-1"
    assert prop.description == ""

def test_utilization_result():
    """Verify UtilizationResult."""
    result = UtilizationResult(
        recommendation="Build Housing",
        confidence_score=0.95,
        reasoning_trace=["Zoning fits", "Slope is good"]
    )
    assert result.confidence_score == 0.95
    assert len(result.reasoning_trace) == 2

def test_mismatch_result():
    """Verify MismatchResult."""
    mismatch = MismatchResult(
        lat=37.0,
        lon=-122.0,
        mismatch_type="zoning",
        gis_value="R-1",
        lidar_value="Industrial",
        predicted_utility=0.8,
        rule_based_utility=0.2,
        severity=0.6,
        description="Zoning conflict"
    )
    assert mismatch.mismatch_type == "zoning"
    assert mismatch.severity == 0.6
