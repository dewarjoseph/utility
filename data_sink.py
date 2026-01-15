"""
Data Sink: Training data logger with dual-write to JSONL (archive) and EventBuffer (live).

This module handles all data persistence for the daemon, supporting both historical
archival and real-time streaming to the dashboard.
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any

log = logging.getLogger("data_sink")


class TrainingLogger:
    """
    Logs training samples to both JSONL (archival) and EventBuffer (real-time).
    
    Features:
    - Dual-write for backwards compatibility + live streaming
    - Enriched logging with ML metadata (errors, surprises, mismatches)
    - Batch flushing for performance
    - Graceful degradation on write failures
    
    Usage:
        logger = TrainingLogger()
        logger.log_sample(
            quantum_data, 
            calculated_score=7.5, 
            reasoning_trace=["Water Access (+3.0)", ...],
            ml_metadata={
                'prediction': 6.8,
                'error': 0.7,
                'is_surprise': False,
                'mismatches': [...]
            }
        )
    """
    
    def __init__(
        self, 
        filename: str = "training_dataset.jsonl",
        use_event_buffer: bool = True
    ):
        """
        Initialize the TrainingLogger.
        
        Args:
            filename: JSONL file for archival storage
            use_event_buffer: If True, also write to EventBuffer for live dashboard
        """
        self.filepath = os.path.join(os.getcwd(), filename)
        self.use_event_buffer = use_event_buffer
        self._event_buffer = None
        
        # Lazy-load EventBuffer to avoid circular imports
        if use_event_buffer:
            try:
                from core.event_buffer import EventBuffer
                self._event_buffer = EventBuffer()
                log.info(f"TrainingLogger initialized with EventBuffer at {self.filepath}")
            except Exception as e:
                log.warning(f"Could not initialize EventBuffer: {e}. Using JSONL only.")
                self._event_buffer = None
        else:
            log.info(f"TrainingLogger initialized (JSONL only) at {self.filepath}")
        
        # Write statistics
        self._samples_logged = 0
        self._errors_count = 0
        self._high_value_count = 0
        self._surprise_count = 0

    def log_sample(
        self, 
        quantum_data: Dict, 
        calculated_score: float, 
        reasoning_trace: List[str],
        ml_metadata: Optional[Dict] = None
    ) -> bool:
        """
        Log a training sample to storage.
        
        Args:
            quantum_data: Dictionary with quantum attributes (lat, lon, features, etc.)
            calculated_score: Rule-based utility score (ground truth)
            reasoning_trace: List of reasoning steps that produced the score
            ml_metadata: Optional ML-related metadata:
                - prediction: ML predicted score
                - error: Absolute prediction error
                - is_surprise: Whether this was a surprise event
                - mismatches: List of detected mismatches
                - features: Extracted ML features dict
                
        Returns:
            True on success, False on failure
        """
        timestamp = time.time()
        ml_metadata = ml_metadata or {}
        
        # Extract common fields
        lat = quantum_data.get("lat", 0)
        lon = quantum_data.get("lon", 0)
        ml_error = ml_metadata.get('error', 0)
        is_surprise = ml_metadata.get('is_surprise', False)
        mismatches = ml_metadata.get('mismatches', [])
        features = ml_metadata.get('features', {})
        
        # Build JSONL entry (full archival record)
        entry = {
            "timestamp": timestamp,
            "location": {
                "lat": lat,
                "lon": lon
            },
            "features_raw": {
                "has_water": int(quantum_data.get("has_water_infrastructure", False)),
                "has_road": int(quantum_data.get("has_road_access", False)),
                "is_industrial": 1 if quantum_data.get("zoning_type") == "Industrial" else 0,
                "is_residential": 1 if quantum_data.get("zoning_type") == "Residential" else 0
            },
            "expert_label": {
                "gross_utility_score": calculated_score,
                "reasoning_trace": reasoning_trace 
            },
            # Include socioeconomic data if present
            "socioeconomic": quantum_data.get("socioeconomic"),
            # Include GIS data if present
            "gis_data": quantum_data.get("gis_data"),
            # ML metadata for online learning analysis
            "ml_metadata": {
                "prediction": ml_metadata.get('prediction'),
                "error": ml_error,
                "is_surprise": is_surprise,
                "mismatch_count": len(mismatches),
                "mismatch_types": [
                    m.get('mismatch_type') if isinstance(m, dict) else getattr(m, 'mismatch_type', 'unknown')
                    for m in mismatches
                ]
            } if ml_metadata else None
        }
        
        success = True
        
        # Write to JSONL (archival)
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.error(f"[TrainingLogger] Failed to write to JSONL: {e}")
            success = False
            self._errors_count += 1
        
        # Write to EventBuffer (real-time)
        if self._event_buffer is not None:
            try:
                self._event_buffer.insert_event(
                    quantum_data=quantum_data,
                    score=calculated_score,
                    ml_error=ml_error,
                    mismatches=mismatches,
                    features=features,
                    trace=reasoning_trace
                )
            except Exception as e:
                log.warning(f"[TrainingLogger] Failed to write to EventBuffer: {e}")
                # Don't mark as failure - JSONL may have succeeded
        
        # Update statistics
        self._samples_logged += 1
        if calculated_score >= 5.0:
            self._high_value_count += 1
        if is_surprise:
            self._surprise_count += 1
        
        # Periodic logging
        if self._samples_logged % 50 == 0:
            log.debug(
                f"[TrainingLogger] Progress: {self._samples_logged} samples, "
                f"{self._high_value_count} high-value, {self._surprise_count} surprises"
            )
        
        return success
    
    def get_event_buffer(self):
        """Get the underlying EventBuffer for direct access."""
        return self._event_buffer
    
    def get_stats(self) -> Dict:
        """Get logging statistics."""
        return {
            'samples_logged': self._samples_logged,
            'high_value_count': self._high_value_count,
            'surprise_count': self._surprise_count,
            'errors_count': self._errors_count,
            'filepath': self.filepath,
            'has_event_buffer': self._event_buffer is not None
        }
    
    def close(self):
        """Close underlying resources."""
        if self._event_buffer is not None:
            self._event_buffer.close()
            log.info("TrainingLogger closed")

