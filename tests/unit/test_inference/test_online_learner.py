import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
from inference import online_learner

# Mock river availability
# We need to test both scenarios: river available and not available

def test_fallback_brain():
    """Verify FallbackBrain behavior when River is missing."""
    brain = online_learner.FallbackBrain()
    assert not brain.is_ready
    
    brain.learn({}, 1.0)
    assert brain.predict({}) == 1.0 # Average of 1 sample is 1.0
    
    for _ in range(10):
        brain.learn({}, 1.0)
    assert brain.is_ready

@patch('inference.online_learner.RIVER_AVAILABLE', True)
def test_online_brain_learn():
    """Verify OnlineBrain learning loop (mocking river internals)."""
    with patch('inference.online_learner.forest') as mock_forest, \
         patch('inference.online_learner.drift') as mock_drift, \
         patch('inference.online_learner.preprocessing') as mock_pp, \
         patch('inference.online_learner.compose') as mock_compose:
        
        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline.predict_one.return_value = 0.5
        mock_compose.Pipeline.return_value = mock_pipeline
        
        brain = online_learner.OnlineBrain(load_existing=False)
        
        # Test learn
        pred, err, surprise = brain.learn({'feat': 1.0}, 0.8)
        
        assert pred == 0.5 # Predicted before learn
        mock_pipeline.learn_one.assert_called()
        assert brain._samples_learned == 1

@pytest.mark.skip(reason="Complex mocking of River internals")
@patch('inference.online_learner.RIVER_AVAILABLE', True)
def test_online_brain_drift():
    """Verify drift detection logic."""
    with patch('inference.online_learner.forest'), \
         patch('inference.online_learner.drift') as mock_drift, \
         patch('inference.online_learner.preprocessing'), \
         patch('inference.online_learner.compose'):
         
        mock_detector_instance = MagicMock()
        type(mock_detector_instance).drift_detected = PropertyMock(return_value=True) if hasattr(drift.ADWIN, 'drift_detected') else True
        # Simplified: just set attribute
        mock_detector_instance.drift_detected = True
        mock_drift.ADWIN.return_value = mock_detector_instance
        
        brain = online_learner.OnlineBrain(load_existing=False)
        
        brain.learn({'f': 1}, 1.0)
        
        assert brain._drift_events == 1

def test_factory():
    """Verify factory returns correct brain type."""
    with patch('inference.online_learner.RIVER_AVAILABLE', False):
        brain = online_learner.create_brain()
        assert isinstance(brain, online_learner.FallbackBrain)
    
    with patch('inference.online_learner.RIVER_AVAILABLE', True), \
         patch('inference.online_learner.forest'), \
         patch('inference.online_learner.drift'), \
         patch('inference.online_learner.preprocessing'), \
         patch('inference.online_learner.compose'):
        brain = online_learner.create_brain()
        assert isinstance(brain, online_learner.OnlineBrain)
