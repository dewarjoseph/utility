import time
import random
import json
import logging

from core import GridEngine, DecisionEngine
from loaders import OSMLoader, GISLoader, SocioeconomicLoader
from data_sink import TrainingLogger

# Configure logging - outputs to console
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Outputs to console/terminal
    ]
)
log = logging.getLogger("daemon")

# Center of Santa Cruz
DAEMON_START_LAT = 36.974
DAEMON_START_LON = -122.030

def run_daemon():
    log.info(">>> LAND UTILIZATION DAEMON ONLINE <<<")
    log.info(">>> Listening for land data updates...")
    
    training_logger = TrainingLogger()
    engine = DecisionEngine()
    osm_loader = OSMLoader()
    socio_loader = SocioeconomicLoader()
    gis_loader = GISLoader()
    
    # Daemon Loop Configuration
    current_lat = DAEMON_START_LAT
    current_lon = DAEMON_START_LON
    scan_radius_meters = 1500
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            
            # Write status file for dashboard
            with open("daemon_status.json", "w") as f:
                json.dump({"cycles": cycle_count, "running": True}, f)
            
            log.info(f"[Cycle {cycle_count}] Scanning Sector: {current_lat:.4f}, {current_lon:.4f}")
            
            # 1. Ingest
            # In a real daemon, we might move the lat/lon to "crawl" the map
            # For this demo, we shift slightly to simulate moving across the city
            shift_lat = (random.random() - 0.5) * 0.01
            shift_lon = (random.random() - 0.5) * 0.01
            scan_lat = current_lat + shift_lat
            scan_lon = current_lon + shift_lon
            
            features = osm_loader.fetch_and_parse(scan_lat, scan_lon, radius_meters=scan_radius_meters)
            
            # 2. Grid Projection
            grid = GridEngine(scan_lat, scan_lon, width_cells=10, height_cells=5, cell_size_meters=100)
            for f in features:
                grid.project_feature(f["type"], f["lat"], f["lon"])
            
            # 3. Analyze & Log
            quanta_list = grid.get_all_quanta()
            
            high_value_count = 0
            for q in quanta_list:
                result = engine.calculate_gross_utility(q)
                score = result["score"]
                trace = result["trace"]
                
                # Log to Training Set
                # Enrich with socioeconomic and GIS data
                q_dict = q.__dict__
                enriched_dict = socio_loader.enrich_quantum(q_dict)
                enriched_dict = gis_loader.enrich_quantum(enriched_dict)
                training_logger.log_sample(enriched_dict, score, trace)
                
                if score > 5.0:
                    high_value_count += 1
            
            log.info(f"Processed {len(quanta_list)} Micro-Sectors.")
            log.info(f"Identified {high_value_count} High-Utility Targets.")
            log.debug("Data logged to training_dataset.jsonl")
            
            # 4. Wait
            log.debug("Sleeping 3s...")
            time.sleep(3)
                
                
    except KeyboardInterrupt:
        log.info("[STOP] Daemon shutting down.")

if __name__ == "__main__":
    run_daemon()
