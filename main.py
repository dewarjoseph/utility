from osm_loader import fetch_santa_cruz_data, parse_osm_data
from grid_engine import GridEngine
from analyzer import DecisionEngine

# Santa Cruz Westside (Approx Industrial Area)
START_LAT = 36.960
START_LON = -122.050

def main():
    print("Initializing Santa Cruz Land Utilization Engine (Grid Scale)...")
    
    # 1. Initialize the Infinite Grid
    print(f"1. Creating Quantum Grid @ {START_LAT}, {START_LON}...")
    grid = GridEngine(START_LAT, START_LON, width_cells=15, height_cells=8, cell_size_meters=100)
    
    # 2. Scrape The World (OSM)
    print("2. Scraping Real-World Data (Overpass API)...")
    raw_data = fetch_santa_cruz_data(START_LAT, START_LON, radius_meters=1500)
    features = parse_osm_data(raw_data)
    print(f"   -> Extracted {len(features)} relevant land features.")
    
    # 3. Project Reality -> Quanta
    print("3. Projecting features onto Grid...")
    for f in features:
        grid.project_feature(f["type"], f["lat"], f["lon"])
        
    # 4. Calculate Gross Utility
    print("4. Calculating Gross Utility Scores (GUS)...")
    engine = DecisionEngine()
    
    quanta = grid.get_all_quanta()
    max_score = 0
    for q in quanta:
        q.gross_utility_score = engine.calculate_gross_utility(q)
        if q.gross_utility_score > max_score:
            max_score = q.gross_utility_score

    # 5. Visualize (ASCII Heatmap)
    print("\n=== LAND UTILITY HEATMAP ===")
    print("Scale: . (Low) -> # (High)\n")
    
    for row in grid.grid:
        line_str = ""
        for cell in row:
            s = cell.gross_utility_score
            if s == 0: char = "."
            elif s < 3: char = ":"
            elif s < 6: char = "%"
            else: char = "#" # HOT ZONE
            line_str += f" {char} "
        print(line_str)
        
    print("\nLegend:")
    print(" # : High Utility (Industrial + Water + Road)")
    print(" % : Medium Utility (Road + Water)")
    print(" : : Low Utility (Road only)")
    print(" . : Dead Zone")

if __name__ == "__main__":
    main()
