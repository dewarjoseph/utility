import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from inference.predictor import UtilityPredictor

@pytest.fixture
def predictor():
    with patch('os.path.exists', return_value=True), \
         patch('joblib.load') as mock_load:
        
        # Mock model behavior
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8]
        mock_model.estimators_ = [MagicMock(), MagicMock()] # For confidence
        for tree in mock_model.estimators_:
            tree.predict.return_value = [0.8]
            
        mock_load.return_value = mock_model
        
        pred = UtilityPredictor("test_model.pkl")
        yield pred

def test_extract_features(predictor):
    """Verify feature extraction logic."""
    q = {
        'has_water_infrastructure': True,
        'has_road_access': False,
        'zoning_type': 'Industrial',
        'gis_data': {
            'elevation_ft': 2000,
            'slope_percent': 0,
            'wildfire_risk_score': 0,
            'flood_risk_score': 0
        }
    }
    
    feats = predictor.extract_features(q)
    assert feats['has_water'] == 1
    assert feats['has_road'] == 0
    assert feats['is_industrial'] == 1
    assert feats['elevation_normalized'] == 1.0

def test_predict(predictor):
    """Verify prediction wrapper."""
    q = {'zoning_type': 'Industrial'}
    score = predictor.predict(q)
    assert score == 0.8

def test_predict_with_confidence(predictor):
    """Verify confidence interval prediction."""
    q = {'zoning_type': 'Industrial'}
    result = predictor.predict_with_confidence(q)
    assert result['prediction'] == 0.8
    assert result['std'] >= 0.0

def test_predict_not_ready():
    """Verify behavior when model isn't loaded."""
    with patch('os.path.exists', return_value=False):
        pred = UtilityPredictor("missing.pkl")
        assert not pred.is_ready
        assert pred.predict({}) == 0.0
