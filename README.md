# 🛰️ Land Utility Engine

**Automated land utility analysis for industrial site selection and investment planning.**

Analyze geographic areas for optimal industrial use — desalination plants, silicon wafer fabrication, warehouses, and more.

## ✨ Features

- **Multi-Source Data Integration**: OSM, USGS, Census (elevation, roads, power, rail, ports, coastline)
- **Synergy-Based Scoring**: Advanced scoring with interaction terms and diminishing returns
- **Use-Case Profiles**: Optimized scoring for desalination, silicon fab, warehouse, manufacturing
- **Interactive Dashboard**: Streamlit-based visualization with map, charts, and point inspection
- **Background Worker**: Asynchronous scanning with job queue

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the dashboard
streamlit run app.py
```

## 📊 Dashboard

1. **Create Project**: Enter address or coordinates, select use case profile, set radius
2. **Start Worker**: Click "🔄 Start Worker" in sidebar to begin scanning
3. **Explore Data**: View points on map, analyze feature distributions, inspect scores

## 🏭 Use-Case Profiles

| Profile | Optimized For |
|---------|---------------|
| 🌊 Desalination Plant | Coastal access, power grid, industrial zoning |
| 💎 Silicon Wafer Fab | Power, water, low seismic risk |
| 📦 Warehouse/Distribution | Highway, rail, port access |
| 🏭 Light Manufacturing | Industrial zoning, road access |

## 🔧 Architecture

```
utility/
├── core/               # Core logic
│   ├── project.py      # Project & settings management
│   ├── job_queue.py    # Background job queue
│   ├── worker.py       # Background scanner
│   └── scoring.py      # Synergy-based scoring engine
├── loaders/            # Data ingestion
│   ├── osm.py          # OpenStreetMap land use
│   ├── elevation.py    # USGS elevation data
│   ├── infrastructure.py  # Power, rail, ports, coast
│   ├── demographics.py # Population, labor market
│   └── unified.py      # Unified data fetcher
├── pages/              # Streamlit pages
│   └── 1_Dashboard.py  # Main analysis dashboard
├── app.py              # Application entry point
└── requirements.txt    # Python dependencies
```

## 🔬 Synergy Scoring

The engine uses synergy-based scoring with interaction terms:

```
score = diminish(base + Σ(feature_weights) + Σ(synergy_bonuses))
```

**Example (Desalination Profile):**
- Coastal Access: +4.0
- Power Nearby: +3.0
- Industrial Zone: +2.5
- *Synergy*: Coastal + Industrial → +2.5
- *Synergy*: Coastal + Power → +2.0

## 📁 Data Sources

| Source | Data |
|--------|------|
| OpenStreetMap | Land use, roads, water, power, rail, ports |
| USGS | Elevation |
| Census (est.) | Population, labor force |

## 📝 License

MIT
