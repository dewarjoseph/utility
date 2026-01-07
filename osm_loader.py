import json
import urllib.request
import urllib.error
import time

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

def fetch_santa_cruz_data(lat, lon, radius_meters=1000):
    """
    Query Overpass API for features around a point.
    Query asks for:
    - highway=* (Roads)
    - natural=water or waterway=* (Water)
    - landuse=industrial (Zoning)
    """
    query = f"""
    [out:json];
    (
      way["highway"](around:{radius_meters},{lat},{lon});
      node["natural"="water"](around:{radius_meters},{lat},{lon});
      way["waterway"](around:{radius_meters},{lat},{lon});
      way["landuse"="industrial"](around:{radius_meters},{lat},{lon});
      way["landuse"="residential"](around:{radius_meters},{lat},{lon});
    );
    (._;>;);
    out body;
    """
    
    try:
        print(f"   [Net] Requesting OSM Data for {lat}, {lon}...")
        # Note: In a real app we'd use requests, but urllib is stdlib safer here
        req = urllib.request.Request(OVERPASS_URL, data=query.encode('utf-8'))
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"   [Net] Success! Fetched {len(data.get('elements', []))} elements.")
            return data
    except Exception as e:
        print(f"   [!] Network/API Error: {e}")
        print("   [!] FALLING BACK TO MOCK SANTA CRUZ DATA (Offline Mode)")
        return _get_mock_osm_data(lat, lon)

def _get_mock_osm_data(lat, lon):
    # Simulate a small grid of industrial + water + road
    # Create some "nodes" relative to the center
    # 0.001 deg is roughly 100m
    
    mock_elements = []
    
    # A "Road" running East-West
    for i in range(20):
        mock_elements.append({
            "type": "node",
            "lat": lat, 
            "lon": lon + (i * 0.0005),
            "tags": {"highway": "primary"}
        })
    
    # A "Water Pipe" (Service road / waterway) running North-South
    for i in range(10):
        mock_elements.append({
            "type": "node",
            "lat": lat + (i * 0.0005), 
            "lon": lon + 0.002,
            "tags": {"waterway": "stream"}
        })
        
    # An Industrial Zone block
    mock_elements.append({
        "type": "node",
        "lat": lat + 0.002,
        "lon": lon + 0.002,
        "tags": {"landuse": "industrial"}
    })
    
    return {"elements": mock_elements}

def parse_osm_data(data):
    # Flatten specific "nodes" of interest
    features = []
    
    for el in data.get("elements", []):
        if "lat" in el and "lon" in el:
            tags = el.get("tags", {})
            
            ftype = None
            if "highway" in tags: ftype = "highway"
            if "waterway" in tags or tags.get("natural") == "water": ftype = "water"
            if tags.get("landuse") == "industrial": ftype = "industrial"
            if tags.get("landuse") == "residential": ftype = "residential"
            
            if ftype:
                features.append({
                    "type": ftype,
                    "lat": el["lat"],
                    "lon": el["lon"]
                })
    return features
