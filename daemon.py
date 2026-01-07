import time
import random
from osm_loader import fetch_santa_cruz_data, parse_osm_data
from grid_engine import GridEngine
from analyzer import DecisionEngine
from data_sink import TrainingLogger

# Center of Santa Cruz
DAEMON_START_LAT = 36.974
DAEMON_START_LON = -122.030

def run_daemon():
    print(">>> LAND UTILIZATION DAEMON ONLINE <<<")
    print(">>> Listening for land data updates...")
    
    logger = TrainingLogger()
    engine = DecisionEngine()
    
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
            
            print(f"\n[Cycle {cycle_count}] Scanning Sector: {current_lat:.4f}, {current_lon:.4f}")
            
            # 1. Ingest
            # In a real daemon, we might move the lat/lon to "crawl" the map
            # For this demo, we shift slightly to simulate moving across the city
            shift_lat = (random.random() - 0.5) * 0.01
            shift_lon = (random.random() - 0.5) * 0.01
            scan_lat = current_lat + shift_lat
            scan_lon = current_lon + shift_lon
            
            raw_data = fetch_santa_cruz_data(scan_lat, scan_lon, radius_meters=scan_radius_meters)
            features = parse_osm_data(raw_data)
            
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
                # We save the state of the quantum + the score the expert engine gave it
                q_dict = q.__dict__
                logger.log_sample(q_dict, score, trace)
                
                if score > 5.0:
                    high_value_count += 1
            
            print(f"   -> Processed {len(quanta_list)} Micro-Sectors.")
            print(f"   -> Identified {high_value_count} High-Utility Targets.")
            print("   -> Data logged to training_dataset.jsonl")
            
            # 4. Wait
            print("   [Sleeping 3s]...")
            time.sleep(3)
            
            # Stop after 3 cycles for the demo run
            if cycle_count >= 3:
                print("\n[STOP] Daemon demo limit reached.")
                break
                
    except KeyboardInterrupt:
        print("\n[STOP] Daemon shutting down.")

if __name__ == "__main__":
    run_daemon()
