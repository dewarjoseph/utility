"""
Land Utilization Daemon: Real-time scanning with online machine learning.

This daemon continuously scans geographic sectors, calculates utility scores,
and trains an online ML model that improves in real-time. Features include:
- Incremental learning via River's AMF regressor
- Mismatch detection for anomaly identification
- Dual logging to JSONL (archive) and EventBuffer (live dashboard)
- Graceful shutdown with model persistence
"""

import json
import logging
import os
import random
import signal
import sys
import time
from typing import Dict, List, Optional

from core import GridEngine, DecisionEngine, EventBuffer
from loaders import OSMLoader, GISLoader, SocioeconomicLoader
from loaders.gis import GISFeatureExtractor
from data_sink import TrainingLogger

# Attempt to import online learning components (graceful fallback)
try:
    from inference.online_learner import OnlineBrain, create_brain, RIVER_AVAILABLE
    from inference.mismatch_detector import MismatchDetector
    ONLINE_LEARNING_ENABLED = RIVER_AVAILABLE
except ImportError as e:
    ONLINE_LEARNING_ENABLED = False
    OnlineBrain = None
    MismatchDetector = None

# Configure logging with rich formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(name)-20s │ %(levelname)-8s │ %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)
log = logging.getLogger("daemon")

# Center of Santa Cruz
DAEMON_START_LAT = 36.974
DAEMON_START_LON = -122.030

# Daemon configuration
SCAN_RADIUS_METERS = 1500
GRID_WIDTH_CELLS = 10
GRID_HEIGHT_CELLS = 5
CELL_SIZE_METERS = 100
CYCLE_SLEEP_SECONDS = 3
MODEL_SAVE_INTERVAL = 50  # Save model every N cycles


class DaemonState:
    """Manages daemon state and graceful shutdown."""
    
    def __init__(self):
        self.running = True
        self.cycle_count = 0
        self.high_value_total = 0
        self.surprise_total = 0
        self.total_quanta_processed = 0
        self.start_time = time.time()
    
    def get_uptime_str(self) -> str:
        elapsed = time.time() - self.start_time
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_velocity(self) -> float:
        """Quanta processed per minute."""
        elapsed_min = (time.time() - self.start_time) / 60
        return self.total_quanta_processed / elapsed_min if elapsed_min > 0 else 0


def signal_handler(signum, frame, state: DaemonState, brain=None):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    log.info("┌────────────────────────────────────────┐")
    log.info("│      SHUTDOWN SIGNAL RECEIVED          │")
    log.info("└────────────────────────────────────────┘")
    
    state.running = False
    
    # Save model if brain exists
    if brain is not None and hasattr(brain, 'save'):
        log.info("Persisting online model to disk...")
        brain.save()
        log.info("Model saved successfully.")
    
    log.info(f"Final Statistics:")
    log.info(f"  • Cycles completed: {state.cycle_count}")
    log.info(f"  • Quanta processed: {state.total_quanta_processed}")
    log.info(f"  • High-value targets: {state.high_value_total}")
    log.info(f"  • Surprise events: {state.surprise_total}")
    log.info(f"  • Uptime: {state.get_uptime_str()}")


def run_daemon():
    """Main daemon loop with online learning integration."""
    
    # ASCII banner for console
    log.info("┌────────────────────────────────────────────────────────────┐")
    log.info("│  🛰️  LAND UTILIZATION DAEMON v2.0 - ONLINE LEARNING MODE   │")
    log.info("└────────────────────────────────────────────────────────────┘")
    
    # Initialize state
    state = DaemonState()
    
    # Initialize components
    log.info("Initializing components...")
    
    training_logger = TrainingLogger()
    engine = DecisionEngine()
    osm_loader = OSMLoader()
    socio_loader = SocioeconomicLoader()
    gis_loader = GISLoader()
    
    # Initialize online learning brain
    brain = None
    mismatch_detector = None
    
    if ONLINE_LEARNING_ENABLED:
        try:
            brain = create_brain(n_estimators=15, load_existing=True)
            mismatch_detector = MismatchDetector(
                gis_loader=gis_loader,
                analyzer=engine
            )
            log.info("✓ Online Learning ENABLED (River AMF regressor)")
            log.info(f"  → Model status: {brain}")
        except Exception as e:
            log.warning(f"⚠ Online learning initialization failed: {e}")
            log.warning("  → Falling back to rule-based mode")
            brain = None
    else:
        log.warning("⚠ Online Learning DISABLED (River not installed)")
        log.info("  → Run 'pip install river>=0.21.0' to enable")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, state, brain))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, state, brain))
    
    # Daemon loop configuration
    current_lat = DAEMON_START_LAT
    current_lon = DAEMON_START_LON
    
    log.info("┌────────────────────────────────────────┐")
    log.info("│      ENTERING MAIN SCANNING LOOP       │")
    log.info("└────────────────────────────────────────┘")
    log.info(f"Starting position: ({current_lat:.4f}, {current_lon:.4f})")
    log.info(f"Scan radius: {SCAN_RADIUS_METERS}m | Grid: {GRID_WIDTH_CELLS}x{GRID_HEIGHT_CELLS}")
    
    try:
        while state.running:
            state.cycle_count += 1
            cycle_start = time.time()
            
            # Write status file for dashboard
            status = {
                "cycles": state.cycle_count,
                "running": True,
                "uptime": state.get_uptime_str(),
                "high_value_total": state.high_value_total,
                "surprise_total": state.surprise_total,
                "quanta_processed": state.total_quanta_processed,
                "online_learning": brain is not None
            }
            try:
                with open("daemon_status.json", "w") as f:
                    json.dump(status, f)
            except Exception as e:
                log.debug(f"Failed to write status file: {e}")
            
            # Shift position to simulate scanning different areas
            shift_lat = (random.random() - 0.5) * 0.01
            shift_lon = (random.random() - 0.5) * 0.01
            scan_lat = current_lat + shift_lat
            scan_lon = current_lon + shift_lon
            
            log.info(f"")
            log.info(f"══════════ CYCLE {state.cycle_count} ══════════")
            log.info(f"📍 Sector: ({scan_lat:.4f}, {scan_lon:.4f})")
            
            # ═══════════════════════════════════════════════════════════
            # PHASE 1: DATA INGESTION
            # ═══════════════════════════════════════════════════════════
            try:
                features = osm_loader.fetch_and_parse(
                    scan_lat, scan_lon, 
                    radius_meters=SCAN_RADIUS_METERS
                )
                log.debug(f"OSM ingested {len(features)} features")
            except Exception as e:
                log.warning(f"OSM fetch failed: {e}")
                features = []
            
            # ═══════════════════════════════════════════════════════════
            # PHASE 2: GRID PROJECTION
            # ═══════════════════════════════════════════════════════════
            grid = GridEngine(
                scan_lat, scan_lon,
                width_cells=GRID_WIDTH_CELLS,
                height_cells=GRID_HEIGHT_CELLS,
                cell_size_meters=CELL_SIZE_METERS
            )
            
            for f in features:
                grid.project_feature(f["type"], f["lat"], f["lon"])
            
            quanta_list = grid.get_all_quanta()
            log.debug(f"Grid projected {len(quanta_list)} quanta")
            
            # ═══════════════════════════════════════════════════════════
            # PHASE 3: ANALYSIS + ONLINE LEARNING
            # ═══════════════════════════════════════════════════════════
            cycle_high_value = 0
            cycle_surprises = 0
            cycle_errors = []
            cycle_mismatches = []
            
            for q in quanta_list:
                try:
                    # Convert quantum to dict for enrichment
                    q_dict = q.__dict__
                    
                    # Enrich with socioeconomic data
                    enriched = socio_loader.enrich_quantum(q_dict)
                    
                    # Enrich with GIS data
                    enriched = gis_loader.enrich_quantum(enriched)
                    
                    # Extract ML features
                    gis_data = enriched.get('gis_data', {})
                    ml_features = GISFeatureExtractor.extract_features(gis_data)
                    
                    # ──────────────────────────────────────────────────
                    # PREDICTION (before we know the answer)
                    # ──────────────────────────────────────────────────
                    predicted_utility = 0.0
                    if brain is not None:
                        predicted_utility = brain.predict(ml_features)
                    
                    # ──────────────────────────────────────────────────
                    # GROUND TRUTH (rule-based calculation)
                    # ──────────────────────────────────────────────────
                    result = engine.calculate_gross_utility(q)
                    actual_utility = result["score"]
                    trace = result["trace"]
                    
                    # ──────────────────────────────────────────────────
                    # ONLINE LEARNING (update model with truth)
                    # ──────────────────────────────────────────────────
                    prediction = 0.0
                    error = 0.0
                    is_surprise = False
                    
                    if brain is not None:
                        prediction, error, is_surprise = brain.learn(ml_features, actual_utility)
                        cycle_errors.append(error)
                        
                        if is_surprise:
                            cycle_surprises += 1
                            state.surprise_total += 1
                    
                    # ──────────────────────────────────────────────────
                    # MISMATCH DETECTION
                    # ──────────────────────────────────────────────────
                    mismatches = []
                    if mismatch_detector is not None:
                        try:
                            mismatches = mismatch_detector.scan_quantum(enriched)
                            cycle_mismatches.extend(mismatches)
                        except Exception as e:
                            log.debug(f"Mismatch detection failed: {e}")
                    
                    # ──────────────────────────────────────────────────
                    # LOGGING
                    # ──────────────────────────────────────────────────
                    ml_metadata = {
                        'prediction': prediction,
                        'error': error,
                        'is_surprise': is_surprise,
                        'mismatches': [m.__dict__ if hasattr(m, '__dict__') else m for m in mismatches],
                        'features': ml_features
                    }
                    
                    training_logger.log_sample(
                        enriched, 
                        actual_utility, 
                        trace,
                        ml_metadata=ml_metadata
                    )
                    
                    # Track high-value targets
                    if actual_utility > 5.0:
                        cycle_high_value += 1
                        state.high_value_total += 1
                    
                    state.total_quanta_processed += 1
                    
                except Exception as e:
                    log.warning(f"Error processing quantum: {e}")
                    continue
            
            # ═══════════════════════════════════════════════════════════
            # CYCLE SUMMARY
            # ═══════════════════════════════════════════════════════════
            cycle_duration = time.time() - cycle_start
            avg_error = sum(cycle_errors) / len(cycle_errors) if cycle_errors else 0
            
            log.info(f"📊 Processed: {len(quanta_list)} quanta in {cycle_duration:.2f}s")
            log.info(f"⭐ High-Value: {cycle_high_value} | 🔴 Surprises: {cycle_surprises}")
            
            if brain is not None:
                metrics = brain.get_metrics()
                log.info(
                    f"🧠 ML Stats: MAE={metrics.current_mae:.4f} | "
                    f"R²={metrics.current_r2:.4f} | "
                    f"Samples={metrics.samples_learned}"
                )
            
            if cycle_mismatches:
                log.info(f"🛡️ Mismatches: {len(cycle_mismatches)} detected")
                for m in cycle_mismatches[:3]:  # Show top 3
                    mtype = m.mismatch_type if hasattr(m, 'mismatch_type') else 'unknown'
                    severity = m.severity if hasattr(m, 'severity') else 0
                    log.info(f"   └─ [{mtype.upper()}] severity={severity:.2f}")
            
            # ═══════════════════════════════════════════════════════════
            # PERIODIC MODEL PERSISTENCE
            # ═══════════════════════════════════════════════════════════
            if brain is not None and state.cycle_count % MODEL_SAVE_INTERVAL == 0:
                log.info("💾 Persisting model checkpoint...")
                brain.save()
            
            # ═══════════════════════════════════════════════════════════
            # SLEEP BEFORE NEXT CYCLE
            # ═══════════════════════════════════════════════════════════
            log.debug(f"Sleeping {CYCLE_SLEEP_SECONDS}s before next cycle...")
            time.sleep(CYCLE_SLEEP_SECONDS)
                
    except KeyboardInterrupt:
        pass  # Handled by signal handler
    except Exception as e:
        log.error(f"Daemon crashed with error: {e}")
        raise
    finally:
        # Final cleanup
        if brain is not None:
            brain.save()
        training_logger.close()
        log.info("Daemon shutdown complete.")


if __name__ == "__main__":
    run_daemon()

