#!/usr/bin/env python
"""
Train ML models on accumulated land utility data.
Usage: python train_models.py
"""

from inference import MLEngine
import sys

def main():
    print("=" * 60)
    print("LAND UTILITY ML TRAINING")
    print("=" * 60)
    
    engine = MLEngine()
    
    # Auto-select best model
    best_model = engine.auto_select_model()
    
    if best_model is None:
        print("\n[Error] Not enough data to train. Run daemon for more cycles.")
        sys.exit(1)
    
    # Show feature importance
    print("\n" + "=" * 60)
    print("FEATURE IMPORTANCE")
    print("=" * 60)
    
    importances = engine.get_feature_importance()
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    
    for feature, importance in sorted_features[:10]:
        bar = "█" * int(importance * 50)
        print(f"{feature:30s} {bar} {importance:.4f}")
    
    # Identify uncertain areas for resampling
    print("\n" + "=" * 60)
    print("ACTIVE LEARNING: UNCERTAIN AREAS")
    print("=" * 60)
    
    uncertain = engine.identify_uncertain_areas()
    print(f"Found {len(uncertain)} high-uncertainty predictions.")
    print("These areas should be resampled for ground truth verification.")
    
    print("\n✓ Training complete! Model saved to 'best_model.pkl'")

if __name__ == "__main__":
    main()
