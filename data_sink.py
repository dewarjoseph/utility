import json
import time
import os

class TrainingLogger:
    def __init__(self, filename="training_dataset.jsonl"):
        # Log to the current directory
        self.filepath = os.path.join(os.getcwd(), filename)

    def log_sample(self, quantum_data: dict, calculated_score: float, reasoning_trace: list):
        """
        Appends a training sample to the JSONL file.
        Format is optimized for easy loading into Pandas/PyTorch.
        """
        
        entry = {
            "timestamp": time.time(),
            "location": {
                "lat": quantum_data.get("lat"),
                "lon": quantum_data.get("lon")
            },
            "features_raw": {
                "has_water": int(quantum_data.get("has_water_infrastructure", False)),
                "has_road": int(quantum_data.get("has_road_access", False)),
                # One-hot encode zoning for simplicity in training
                "is_industrial": 1 if quantum_data.get("zoning_type") == "Industrial" else 0,
                "is_residential": 1 if quantum_data.get("zoning_type") == "Residential" else 0
            },
            "expert_label": {
                "gross_utility_score": calculated_score,
                # We can store the text trace as 'auxiliary' data for training Chain-of-Thought models
                "reasoning_trace": reasoning_trace 
            }
        }
        
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            return True
        except Exception as e:
            print(f"[Logger Error] Failed to write sample: {e}")
            return False
