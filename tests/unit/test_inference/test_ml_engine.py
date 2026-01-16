import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, mock_open
from inference.ml_engine import MLEngine

@pytest.fixture
def engine():
    return MLEngine()

def test_load_training_data(engine):
    """Verify data loading and feature extraction."""
    json_data = '{"features_raw": {"has_water": 1}, "expert_label": {"gross_utility_score": 0.5}}\n'
    
    with patch("builtins.open", mock_open(read_data=json_data)):
        X, y = engine.load_training_data("dummy.jsonl")
        
        assert len(X) == 1
        assert "has_water" in X.columns
        assert y[0] == 0.5

def test_auto_select_model_insufficient_data(engine):
    """Verify early exit on small data."""
    with patch.object(engine, 'load_training_data', return_value=(pd.DataFrame(), pd.Series())):
        assert engine.auto_select_model(min_samples=10) is None

def test_auto_select_model_success(engine):
    """Verify model selection flow."""
    # Create dummy data
    X = pd.DataFrame({"feat1": np.random.rand(20), "feat2": np.random.rand(20)})
    y = pd.Series(np.random.rand(20))
    
    with patch.object(engine, 'load_training_data', return_value=(X, y)), \
         patch('joblib.dump'):
        
        model = engine.auto_select_model(min_samples=10)
        assert model is not None
        assert engine.best_model is not None
        assert "RandomForest" in engine.models

def test_train_xgboost_fallback(engine):
    """Verify graceful failure if XGBoost missing."""
    with patch.dict('sys.modules', {'xgboost': None}):
        X = pd.DataFrame({"a": [1]})
        y = pd.Series([1])
        model, score = engine.train_xgboost(X, y)
        assert model is None
        assert score == -np.inf
