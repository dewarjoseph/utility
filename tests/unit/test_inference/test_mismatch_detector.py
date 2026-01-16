import pytest
from unittest.mock import MagicMock
from inference.mismatch_detector import MismatchDetector, Mismatch

@pytest.fixture
def detector():
    mock_gis = MagicMock()
    # Setup default mock returns to avoid NoneTypes
    mock_gis.get_lidar_elevation.return_value = {}
    mock_gis.get_zoning_history.return_value = {}
    mock_gis.get_utility_proximity.return_value = {}
    mock_gis.get_climate_risk.return_value = {}
    
    return MismatchDetector(
        predictor=MagicMock(),
        gis_loader=mock_gis,
        analyzer=MagicMock()
    )

def test_detect_slope_mismatch(detector):
    """Verify slope mismatch detection."""
    # Case: Commercial on steep slope -> Mismatch
    detector.gis_loader.get_lidar_elevation.return_value = {'slope_percent': 30.0}
    detector.gis_loader.get_zoning_history.return_value = {'current_zoning': 'M-1'}
    
    mismatch = detector.detect_slope_mismatch(37.0, -122.0)
    assert mismatch is not None
    assert mismatch.mismatch_type == "slope"
    assert "steep" in mismatch.description

def test_detect_zoning_opportunity(detector):
    """Verify zoning opportunity detection."""
    # Case: Flat, Agg zoning, Utilities -> Opportunity
    detector.gis_loader.get_lidar_elevation.return_value = {'slope_percent': 5.0} # Flat
    detector.gis_loader.get_zoning_history.return_value = {'current_zoning': 'A-1'} # Ag
    detector.gis_loader.get_utility_proximity.return_value = {
        'distance_to_water_main_ft': 100,
        'distance_to_sewer_ft': 100
    }
    
    mismatch = detector.detect_zoning_opportunity(37.0, -122.0)
    assert mismatch is not None
    assert mismatch.mismatch_type == "zoning"

def test_detect_utility_mismatch(detector):
    """Verify ML vs Rule mismatch."""
    detector.predictor.predict.return_value = 9.0
    detector.analyzer.calculate_gross_utility_from_dict.return_value = {'score': 2.0}
    
    mismatch = detector.detect_utility_mismatch({})
    assert mismatch is not None
    assert mismatch.mismatch_type == "utility"
    assert abs(mismatch.predicted_utility - mismatch.rule_based_utility) == 7.0

def test_scan_quantum(detector):
    """Verify scanning aggregates mismatches."""
    # Force one detection
    detector.detect_slope_mismatch = MagicMock(return_value=Mismatch(0,0,"slope",0.8,"","", "", 0, 0))
    
    results = detector.scan_quantum({})
    assert len(results) >= 1
