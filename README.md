# Land Utility Engine - MVP

Automated ground truth analysis for land investment and conservation planning.

## Quick Start

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Launch the Application
```powershell
streamlit run app.py
```

### 3. Using the Dashboard

**Sidebar Controls:**
- Click "▶️ Start Daemon" to begin automated land scanning
- The daemon will fetch real OpenStreetMap data and analyze land utility
- Click "⏹️ Stop Daemon" to pause data collection

**Main Dashboard:**
- **Neural Vector Space**: See how the AI clusters similar land types
- **Geospatial Heatmap**: View utility scores on an interactive map
- **Deep Inspector**: Click any data point to see the reasoning waterfall

## Architecture

- `app.py` - Unified MVP application (daemon + dashboard)
- `daemon.py` - Background worker (now integrated into app.py)
- `analyzer.py` - Decision engine with utility scoring
- `grid_engine.py` - Spatial grid system
- `osm_loader.py` - OpenStreetMap data ingestion
- `data_sink.py` - Training data logger
- `retriever.py` - TF-IDF vector search

## Data Output

The daemon logs all analyzed land sectors to `training_dataset.jsonl` in a format ready for ML training.
