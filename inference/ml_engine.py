"""
ML Engine for automated model selection and training.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score

log = logging.getLogger("inference.ml_engine")


class MLEngine:
    """
    Automated ML model selection and training for land utility prediction.
    
    Supports:
    - Random Forest
    - XGBoost (if installed)
    - LightGBM (if installed)
    
    Automatically selects best performing model via cross-validation.
    """
    
    def __init__(self, model_dir: str = "."):
        self.model_dir = model_dir
        self.models: Dict = {}
        self.best_model = None
        self.best_model_name: Optional[str] = None
        self.best_score: float = -np.inf
        self.feature_columns: List[str] = []
        
        # Try to load existing model
        model_path = os.path.join(model_dir, "best_model.pkl")
        if os.path.exists(model_path):
            try:
                self.best_model = joblib.load(model_path)
                log.info(f"Loaded existing model from {model_path}")
            except Exception as e:
                log.warning(f"Could not load model: {e}")
    
    def load_training_data(
        self, 
        filepath: str = "training_dataset.jsonl"
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Load and prepare data from JSONL file."""
        data = []
        with open(filepath, "r") as f:
            for line in f:
                try:
                    data.append(json.loads(line))
                except:
                    continue
        
        df = pd.DataFrame(data)
        
        # Extract basic features
        X_basic = pd.DataFrame({
            'has_water': df['features_raw'].apply(lambda x: x.get('has_water', 0)),
            'has_road': df['features_raw'].apply(lambda x: x.get('has_road', 0)),
            'is_industrial': df['features_raw'].apply(lambda x: x.get('is_industrial', 0)),
            'is_residential': df['features_raw'].apply(lambda x: x.get('is_residential', 0))
        })
        
        # Extract socioeconomic features if available
        if 'socioeconomic' in df.columns:
            socio = pd.json_normalize(df['socioeconomic'])
            X = pd.concat([X_basic, socio], axis=1)
        else:
            X = X_basic
        
        # Extract GIS features if available
        if 'gis_data' in df.columns:
            try:
                from loaders.gis import GISFeatureExtractor
                gis_features_list = [
                    GISFeatureExtractor.extract_features(gis_data) if gis_data else {}
                    for gis_data in df['gis_data']
                ]
                gis_df = pd.DataFrame(gis_features_list)
                X = pd.concat([X, gis_df], axis=1)
            except ImportError:
                pass
        
        # Store feature columns for prediction
        self.feature_columns = list(X.columns)
        
        # Target variable
        y = df['expert_label'].apply(lambda x: x.get('gross_utility_score', 0))
        
        return X, y
    
    def train_random_forest(
        self, 
        X: pd.DataFrame, 
        y: pd.Series
    ) -> Tuple[RandomForestRegressor, float]:
        """Train Random Forest model."""
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y, cv=kf, scoring='r2')
        
        model.fit(X, y)
        
        return model, float(scores.mean())
    
    def train_xgboost(
        self, 
        X: pd.DataFrame, 
        y: pd.Series
    ) -> Tuple[Optional[object], float]:
        """Train XGBoost model."""
        try:
            import xgboost as xgb
            
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1
            )
            
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            scores = cross_val_score(model, X, y, cv=kf, scoring='r2')
            
            model.fit(X, y)
            return model, float(scores.mean())
        except ImportError:
            log.debug("XGBoost not installed, skipping")
            return None, -np.inf
    
    def train_lightgbm(
        self, 
        X: pd.DataFrame, 
        y: pd.Series
    ) -> Tuple[Optional[object], float]:
        """Train LightGBM model."""
        try:
            import lightgbm as lgb
            
            model = lgb.LGBMRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
            
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            scores = cross_val_score(model, X, y, cv=kf, scoring='r2')
            
            model.fit(X, y)
            return model, float(scores.mean())
        except ImportError:
            log.debug("LightGBM not installed, skipping")
            return None, -np.inf
    
    def auto_select_model(self, min_samples: int = 50) -> Optional[object]:
        """
        Train all available models and select the best one.
        
        Args:
            min_samples: Minimum number of training samples required
            
        Returns:
            Best trained model, or None if insufficient data
        """
        log.info("Loading training data...")
        X, y = self.load_training_data()
        
        if len(X) < min_samples:
            log.warning(f"Only {len(X)} samples. Need at least {min_samples} for reliable training.")
            return None
        
        log.info(f"Training on {len(X)} samples with {X.shape[1]} features...")
        
        # Train all models
        log.info("Training Random Forest...")
        rf_model, rf_score = self.train_random_forest(X, y)
        self.models['RandomForest'] = {'model': rf_model, 'score': rf_score}
        log.info(f"Random Forest R² = {rf_score:.4f}")
        
        log.info("Training XGBoost...")
        xgb_model, xgb_score = self.train_xgboost(X, y)
        if xgb_model:
            self.models['XGBoost'] = {'model': xgb_model, 'score': xgb_score}
            log.info(f"XGBoost R² = {xgb_score:.4f}")
        
        log.info("Training LightGBM...")
        lgb_model, lgb_score = self.train_lightgbm(X, y)
        if lgb_model:
            self.models['LightGBM'] = {'model': lgb_model, 'score': lgb_score}
            log.info(f"LightGBM R² = {lgb_score:.4f}")
        
        # Select best
        best_name = max(self.models.items(), key=lambda x: x[1]['score'])[0]
        self.best_model_name = best_name
        self.best_model = self.models[best_name]['model']
        self.best_score = self.models[best_name]['score']
        
        log.info(f"Best Model: {best_name} (R² = {self.best_score:.4f})")
        
        # Save best model
        model_path = os.path.join(self.model_dir, "best_model.pkl")
        joblib.dump(self.best_model, model_path)
        log.info(f"Model saved to {model_path}")
        
        return self.best_model
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from best model."""
        if self.best_model is None:
            return {}
        
        if not self.feature_columns:
            X, _ = self.load_training_data()
            self.feature_columns = list(X.columns)
        
        if hasattr(self.best_model, 'feature_importances_'):
            importances = self.best_model.feature_importances_
            return dict(zip(self.feature_columns, importances))
        
        return {}
    
    def identify_uncertain_areas(self, threshold: float = 0.3) -> List[int]:
        """
        Active learning: identify areas with high prediction uncertainty.
        
        For tree-based models, uses variance across trees as uncertainty measure.
        
        Returns:
            List of sample indices with high uncertainty
        """
        if self.best_model is None:
            return []
        
        X, y = self.load_training_data()
        
        if hasattr(self.best_model, 'estimators_'):
            predictions = np.array([tree.predict(X) for tree in self.best_model.estimators_])
            variance = np.var(predictions, axis=0)
            uncertain_indices = np.where(variance > threshold)[0]
            return uncertain_indices.tolist()
        
        return []
