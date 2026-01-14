"""
Utility Predictor for runtime ML inference.
"""

import logging
import os
from typing import Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd

log = logging.getLogger("inference.predictor")


class UtilityPredictor:
    """
    Run trained ML models on new land parcels for utility prediction.
    
    This class is optimized for runtime inference, not training.
    For training, use MLEngine.
    """
    
    def __init__(self, model_path: str = "best_model.pkl"):
        self.model = None
        self.model_path = model_path
        
        if os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
                log.info(f"Loaded model from {model_path}")
            except Exception as e:
                log.error(f"Failed to load model: {e}")
        else:
            log.warning(f"Model not found at {model_path}")
    
    @property
    def is_ready(self) -> bool:
        """Check if model is loaded and ready for inference."""
        return self.model is not None
    
    def extract_features(self, quantum_dict: Dict) -> Dict:
        """
        Extract ML features from a quantum dictionary.
        
        Handles both raw quantum dicts and enriched ones with GIS/socioeconomic data.
        """
        features = {
            'has_water': int(quantum_dict.get('has_water_infrastructure', False)),
            'has_road': int(quantum_dict.get('has_road_access', False)),
            'is_industrial': 1 if quantum_dict.get('zoning_type') == 'Industrial' else 0,
            'is_residential': 1 if quantum_dict.get('zoning_type') == 'Residential' else 0,
        }
        
        # Add socioeconomic features if present
        if 'socioeconomic' in quantum_dict:
            socio = quantum_dict['socioeconomic']
            features.update({
                'median_income': socio.get('median_income', 75000),
                'population_density': socio.get('population_density', 1000),
                'employment_rate': socio.get('employment_rate', 0.9),
                'education_bachelor_plus': socio.get('education_bachelor_plus', 0.4),
                'age_median': socio.get('age_median', 35),
                'assessed_value': socio.get('assessed_value', 500000),
                'tax_rate': socio.get('tax_rate', 0.01),
                'last_sale_price': socio.get('last_sale_price', 500000),
                'last_sale_year': socio.get('last_sale_year', 2020),
                'political_leaning': socio.get('political_leaning', 0),
                'voter_turnout': socio.get('voter_turnout', 0.6),
                'campaign_donations_per_capita': socio.get('campaign_donations_per_capita', 100),
                'local_ballot_support_development': socio.get('local_ballot_support_development', 0.5),
            })
        
        # Add GIS features if present
        if 'gis_data' in quantum_dict:
            gis = quantum_dict['gis_data']
            features.update({
                'elevation_normalized': gis.get('elevation_ft', 0) / 2000.0,
                'slope_normalized': gis.get('slope_percent', 0) / 45.0,
                'wildfire_safety': 1.0 - (gis.get('wildfire_risk_score', 5) / 10.0),
                'flood_safety': 1.0 - (gis.get('flood_risk_score', 5) / 10.0),
                'sewer_accessibility': 1.0 / (1.0 + gis.get('distance_to_sewer_ft', 1000) / 500.0),
                'water_accessibility': 1.0 / (1.0 + gis.get('distance_to_water_main_ft', 1000) / 500.0),
                'is_industrial_zoned': 1 if 'M-' in gis.get('current_zoning', '') else 0,
                'is_residential_zoned': 1 if 'R-' in gis.get('current_zoning', '') else 0,
                'is_agricultural_zoned': 1 if 'A-' in gis.get('current_zoning', '') else 0,
            })
        
        return features
    
    def predict(self, quantum_dict: Dict) -> float:
        """
        Predict utility score for a single land quantum.
        
        Args:
            quantum_dict: Dictionary with quantum attributes
            
        Returns:
            Predicted utility score (float)
        """
        if not self.is_ready:
            log.warning("Model not loaded, returning 0")
            return 0.0
        
        features = self.extract_features(quantum_dict)
        df = pd.DataFrame([features])
        
        # Ensure column order matches training
        # Fill missing columns with 0
        try:
            prediction = self.model.predict(df)[0]
            return float(prediction)
        except Exception as e:
            log.error(f"Prediction failed: {e}")
            return 0.0
    
    def predict_batch(self, quanta: List[Dict]) -> np.ndarray:
        """
        Batch prediction for multiple quanta.
        
        More efficient than calling predict() in a loop.
        """
        if not self.is_ready:
            return np.zeros(len(quanta))
        
        features_list = [self.extract_features(q) for q in quanta]
        df = pd.DataFrame(features_list)
        
        try:
            return self.model.predict(df)
        except Exception as e:
            log.error(f"Batch prediction failed: {e}")
            return np.zeros(len(quanta))
    
    def predict_with_confidence(self, quantum_dict: Dict) -> Dict:
        """
        Predict utility with confidence interval (for tree-based models).
        
        Returns:
            Dict with 'prediction', 'confidence_low', 'confidence_high'
        """
        if not self.is_ready:
            return {'prediction': 0.0, 'confidence_low': 0.0, 'confidence_high': 0.0}
        
        features = self.extract_features(quantum_dict)
        df = pd.DataFrame([features])
        
        try:
            if hasattr(self.model, 'estimators_'):
                # Tree ensemble - get predictions from all trees
                predictions = np.array([tree.predict(df)[0] for tree in self.model.estimators_])
                return {
                    'prediction': float(np.mean(predictions)),
                    'confidence_low': float(np.percentile(predictions, 5)),
                    'confidence_high': float(np.percentile(predictions, 95)),
                    'std': float(np.std(predictions))
                }
            else:
                pred = self.model.predict(df)[0]
                return {
                    'prediction': float(pred),
                    'confidence_low': float(pred),
                    'confidence_high': float(pred),
                    'std': 0.0
                }
        except Exception as e:
            log.error(f"Prediction failed: {e}")
            return {'prediction': 0.0, 'confidence_low': 0.0, 'confidence_high': 0.0, 'std': 0.0}
