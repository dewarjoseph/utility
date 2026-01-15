"""
Online Learner: River-based incremental machine learning for real-time utility prediction.

This module replaces batch training with continuous online learning, enabling the model
to adapt in real-time as new data arrives from the daemon scanning loop.
"""

import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import joblib

log = logging.getLogger("inference.online_learner")

# Attempt to import River - graceful fallback if not installed
try:
    from river import forest, metrics, preprocessing, compose, drift, utils
    RIVER_AVAILABLE = True
    log.info("River library loaded successfully - online learning enabled")
except ImportError:
    RIVER_AVAILABLE = False
    log.warning("River library not installed. Run 'pip install river>=0.21.0' for online learning.")


@dataclass
class LearningMetrics:
    """Snapshot of learning performance metrics."""
    samples_learned: int = 0
    current_mae: float = 0.0
    current_r2: float = 0.0
    error_ema: float = 0.0
    high_surprise_count: int = 0
    drift_events: int = 0
    last_update_time: float = 0.0
    

@dataclass
class LearningEvent:
    """Record of a single learning step."""
    timestamp: float
    error: float
    error_ema: float
    prediction: float
    actual: float
    is_surprise: bool
    drift_detected: bool


class OnlineBrain:
    """
    Incremental ML brain with concept drift detection for real-time learning.
    
    Uses River's Adaptive Model Forest (AMF) for online regression with:
    - Automatic scaling via StandardScaler
    - Concept drift detection via ADWIN
    - Exponential moving average for trend tracking
    - Rolling window metrics for recent performance
    - Thread-safe model updates
    
    The brain learns immediately after each prediction, enabling continuous
    improvement without batch retraining cycles.
    
    Usage:
        brain = OnlineBrain()
        
        # In the daemon loop:
        prediction = brain.predict(features)
        actual = calculate_ground_truth(quantum)
        prediction, error, is_surprise = brain.learn(features, actual)
        
        # Periodically save the model:
        brain.save("online_model.pkl")
    """
    
    DEFAULT_MODEL_PATH = "online_model.pkl"
    ERROR_EMA_ALPHA = 0.1  # Smoothing factor for error EMA
    SURPRISE_MULTIPLIER = 2.0  # Error > 2x EMA = surprise
    ROLLING_WINDOW = 100  # Window size for rolling metrics
    
    def __init__(
        self,
        n_estimators: int = 15,
        model_path: Optional[str] = None,
        load_existing: bool = True
    ):
        """
        Initialize the OnlineBrain.
        
        Args:
            n_estimators: Number of trees in the Adaptive Model Forest
            model_path: Path for model persistence
            load_existing: If True, attempt to load existing model from path
        """
        if not RIVER_AVAILABLE:
            raise RuntimeError(
                "River library is required for online learning. "
                "Install with: pip install river>=0.21.0"
            )
        
        self._lock = threading.RLock()
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self.n_estimators = n_estimators
        
        # Initialize or load model
        self.model = None
        self.scaler = None
        self._drift_detector = None
        self._feature_names: List[str] = []
        
        if load_existing and os.path.exists(self.model_path):
            self._load_model()
        else:
            self._init_fresh_model()
        
        # Metrics tracking (windowed for recency)
        # In River 0.23+, Rolling is in utils module
        self._mae_metric = utils.Rolling(metrics.MAE(), window_size=self.ROLLING_WINDOW)
        self._r2_metric = utils.Rolling(metrics.R2(), window_size=self.ROLLING_WINDOW)
        self._rmse_metric = utils.Rolling(metrics.RMSE(), window_size=self.ROLLING_WINDOW)
        
        # Learning curve with bounded memory
        self._learning_curve: deque = deque(maxlen=1000)
        
        # Exponential moving average of errors
        self._error_ema: float = 0.0
        self._first_sample = True  # For EMA initialization
        
        # Statistics
        self._samples_learned: int = 0
        self._high_surprise_events: int = 0
        self._drift_events: int = 0
        self._total_error_sum: float = 0.0
        self._session_start_time: float = time.time()
        
        log.info(f"OnlineBrain initialized with {n_estimators} estimators")
    
    def _init_fresh_model(self) -> None:
        """Initialize a new model pipeline."""
        # Preprocessing: StandardScaler for feature normalization
        self.scaler = preprocessing.StandardScaler()
        
        # Adaptive Model Forest Regressor
        # - Handles concept drift automatically
        # - Uses aggregation for better predictions
        base_model = forest.AMFRegressor(
            n_estimators=self.n_estimators,
            use_aggregation=True,
            seed=42
        )
        
        # Full pipeline with scaling
        self.model = compose.Pipeline(
            self.scaler,
            base_model
        )
        
        # Concept drift detector (ADWIN algorithm)
        self._drift_detector = drift.ADWIN(delta=0.002)
        
        log.info("Initialized fresh OnlineBrain model")
    
    def _load_model(self) -> bool:
        """Load model from disk."""
        try:
            with open(self.model_path, "rb") as f:
                state = joblib.load(f)
            
            self.model = state['model']
            self._drift_detector = state.get('drift_detector', drift.ADWIN(delta=0.002))
            self._feature_names = state.get('feature_names', [])
            self._samples_learned = state.get('samples_learned', 0)
            self._error_ema = state.get('error_ema', 0.0)
            
            log.info(f"Loaded OnlineBrain from {self.model_path} ({self._samples_learned} samples)")
            return True
            
        except Exception as e:
            log.warning(f"Could not load model from {self.model_path}: {e}")
            self._init_fresh_model()
            return False
    
    def save(self, path: Optional[str] = None) -> bool:
        """
        Save model to disk for persistence.
        
        Args:
            path: Custom path, or uses self.model_path
            
        Returns:
            True on success, False on failure
        """
        save_path = path or self.model_path
        
        with self._lock:
            try:
                state = {
                    'model': self.model,
                    'drift_detector': self._drift_detector,
                    'feature_names': self._feature_names,
                    'samples_learned': self._samples_learned,
                    'error_ema': self._error_ema,
                    'timestamp': time.time()
                }
                
                with open(save_path, "wb") as f:
                    joblib.dump(state, f)
                
                log.info(f"Saved OnlineBrain to {save_path} ({self._samples_learned} samples)")
                return True
                
            except Exception as e:
                log.error(f"Failed to save model: {e}")
                return False
    
    def predict(self, features: Dict[str, float]) -> float:
        """
        Predict utility score for a single sample.
        
        Args:
            features: Dictionary of feature name -> value
            
        Returns:
            Predicted utility score (float), or 0.0 if model is empty
        """
        with self._lock:
            try:
                prediction = self.model.predict_one(features)
                return prediction if prediction is not None else 0.0
            except Exception as e:
                log.debug(f"Prediction failed (model may be empty): {e}")
                return 0.0
    
    def learn(
        self,
        features: Dict[str, float],
        target: float
    ) -> Tuple[float, float, bool]:
        """
        Learn from a single sample immediately.
        
        This method first predicts (before learning) to measure "surprise",
        then updates the model weights with the actual target.
        
        Args:
            features: Dictionary of feature name -> value
            target: Ground truth utility score
            
        Returns:
            Tuple of (prediction, error, is_surprise):
            - prediction: What we predicted BEFORE learning
            - error: Absolute difference from target
            - is_surprise: True if this sample was unexpectedly hard
        """
        with self._lock:
            timestamp = time.time()
            
            # Track feature names for saving
            if not self._feature_names:
                self._feature_names = list(features.keys())
            
            # PREDICT BEFORE LEARNING (measures surprise)
            prediction = self.model.predict_one(features)
            if prediction is None:
                prediction = 0.0
            
            # UPDATE MODEL WEIGHTS
            self.model.learn_one(features, target)
            
            # Calculate error
            error = abs(target - prediction)
            
            # Update rolling metrics
            self._mae_metric.update(target, prediction)
            self._r2_metric.update(target, prediction)
            self._rmse_metric.update(target, prediction)
            
            # Update EMA (initialize on first sample)
            if self._first_sample:
                self._error_ema = error
                self._first_sample = False
            else:
                self._error_ema = (
                    self.ERROR_EMA_ALPHA * error + 
                    (1 - self.ERROR_EMA_ALPHA) * self._error_ema
                )
            
            # Detect surprise (error > 2x EMA)
            is_surprise = error > (self.SURPRISE_MULTIPLIER * self._error_ema) if self._error_ema > 0 else False
            if is_surprise:
                self._high_surprise_events += 1
                log.debug(f"SURPRISE EVENT: error={error:.4f}, ema={self._error_ema:.4f}")
            
            # Check for concept drift
            drift_detected = False
            if self._drift_detector is not None:
                self._drift_detector.update(error)
                if self._drift_detector.drift_detected:
                    self._drift_events += 1
                    drift_detected = True
                    log.warning(
                        f"CONCEPT DRIFT DETECTED (event #{self._drift_events})! "
                        f"Model is encountering new territory. "
                        f"Current MAE: {self._mae_metric.get():.4f}"
                    )
            
            # Record learning event
            event = LearningEvent(
                timestamp=timestamp,
                error=error,
                error_ema=self._error_ema,
                prediction=prediction,
                actual=target,
                is_surprise=is_surprise,
                drift_detected=drift_detected
            )
            self._learning_curve.append(event)
            
            # Update statistics
            self._samples_learned += 1
            self._total_error_sum += error
            
            # Periodic logging
            if self._samples_learned % 100 == 0:
                log.info(
                    f"Learning progress: {self._samples_learned} samples, "
                    f"MAE={self._mae_metric.get():.4f}, "
                    f"R²={self._r2_metric.get():.4f}, "
                    f"Surprises={self._high_surprise_events}"
                )
            
            return prediction, error, is_surprise
    
    def predict_with_confidence(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Predict with uncertainty estimate.
        
        For AMF, we estimate uncertainty based on recent error variance.
        
        Args:
            features: Dictionary of feature name -> value
            
        Returns:
            Dict with 'prediction', 'uncertainty', 'confidence'
        """
        prediction = self.predict(features)
        
        # Estimate uncertainty from recent errors
        if len(self._learning_curve) > 10:
            recent_errors = [e.error for e in list(self._learning_curve)[-50:]]
            import statistics
            std_error = statistics.stdev(recent_errors) if len(recent_errors) > 1 else 1.0
            uncertainty = std_error
            confidence = max(0, min(1, 1 - (std_error / 5)))  # Normalize to 0-1
        else:
            uncertainty = float('inf')
            confidence = 0.0
        
        return {
            'prediction': prediction,
            'uncertainty': uncertainty,
            'confidence': confidence,
            'lower_bound': prediction - 2 * uncertainty,
            'upper_bound': prediction + 2 * uncertainty
        }
    
    def get_metrics(self) -> LearningMetrics:
        """Get current learning performance metrics."""
        with self._lock:
            return LearningMetrics(
                samples_learned=self._samples_learned,
                current_mae=self._mae_metric.get() if self._samples_learned > 0 else 0.0,
                current_r2=self._r2_metric.get() if self._samples_learned > 0 else 0.0,
                error_ema=self._error_ema,
                high_surprise_count=self._high_surprise_events,
                drift_events=self._drift_events,
                last_update_time=self._learning_curve[-1].timestamp if self._learning_curve else 0.0
            )
    
    def get_learning_curve(self, last_n: int = 100) -> List[Dict]:
        """
        Get recent learning history for visualization.
        
        Args:
            last_n: Number of recent events to return
            
        Returns:
            List of dicts with error, ema, timestamp, is_surprise
        """
        with self._lock:
            recent = list(self._learning_curve)[-last_n:]
            return [
                {
                    'timestamp': e.timestamp,
                    'error': e.error,
                    'error_ema': e.error_ema,
                    'prediction': e.prediction,
                    'actual': e.actual,
                    'is_surprise': e.is_surprise,
                    'drift_detected': e.drift_detected
                }
                for e in recent
            ]
    
    def get_learning_velocity(self) -> float:
        """Get samples learned per minute over the session."""
        elapsed_minutes = (time.time() - self._session_start_time) / 60
        if elapsed_minutes > 0:
            return self._samples_learned / elapsed_minutes
        return 0.0
    
    def reset_metrics(self) -> None:
        """Reset metrics without resetting the model."""
        with self._lock:
            self._mae_metric = utils.Rolling(metrics.MAE(), window_size=self.ROLLING_WINDOW)
            self._r2_metric = utils.Rolling(metrics.R2(), window_size=self.ROLLING_WINDOW)
            self._rmse_metric = utils.Rolling(metrics.RMSE(), window_size=self.ROLLING_WINDOW)
            self._learning_curve.clear()
            self._high_surprise_events = 0
            self._drift_events = 0
            self._session_start_time = time.time()
            log.info("OnlineBrain metrics reset")
    
    @property 
    def is_ready(self) -> bool:
        """Check if brain has learned enough samples for reliable predictions."""
        return self._samples_learned >= 10
    
    def __repr__(self) -> str:
        metrics = self.get_metrics()
        return (
            f"OnlineBrain(samples={metrics.samples_learned}, "
            f"MAE={metrics.current_mae:.4f}, R²={metrics.current_r2:.4f}, "
            f"surprises={metrics.high_surprise_count}, drifts={metrics.drift_events})"
        )


class FallbackBrain:
    """
    Fallback brain when River is not installed.
    
    Uses a simple running average as a baseline prediction.
    """
    
    def __init__(self):
        self._sum = 0.0
        self._count = 0
        self._samples_learned = 0
        log.warning("Using FallbackBrain (River not available)")
    
    def predict(self, features: Dict[str, float]) -> float:
        if self._count == 0:
            return 0.0
        return self._sum / self._count
    
    def learn(self, features: Dict[str, float], target: float) -> Tuple[float, float, bool]:
        prediction = self.predict(features)
        self._sum += target
        self._count += 1
        self._samples_learned += 1
        error = abs(target - prediction)
        return prediction, error, False
    
    def save(self, path: Optional[str] = None) -> bool:
        return True
    
    def get_metrics(self) -> LearningMetrics:
        return LearningMetrics(samples_learned=self._samples_learned)
    
    def get_learning_curve(self, last_n: int = 100) -> List[Dict]:
        return []
    
    @property
    def is_ready(self) -> bool:
        return self._count >= 10


def create_brain(**kwargs) -> Any:
    """
    Factory function to create the appropriate brain.
    
    Returns OnlineBrain if River is available, else FallbackBrain.
    """
    if RIVER_AVAILABLE:
        return OnlineBrain(**kwargs)
    else:
        return FallbackBrain()
