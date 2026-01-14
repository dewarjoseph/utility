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

```
utility/
├── core/                    # Core data models and engines
│   ├── models.py            # LandQuantum, Property, UtilizationResult, MismatchResult
│   ├── grid.py              # GridEngine - spatial grid system
│   └── analyzer.py          # DecisionEngine - rule-based utility scoring
├── loaders/                 # Data ingestion
│   ├── osm.py               # OSMLoader - OpenStreetMap data
│   ├── gis.py               # GISLoader - County GIS, LiDAR, FEMA flood data
│   └── socioeconomic.py     # Census/tax/political data
├── inference/               # ML pipeline
│   ├── ml_engine.py         # MLEngine - model training
│   ├── predictor.py         # UtilityPredictor - runtime inference
│   └── mismatch_detector.py # MismatchDetector - GIS/LiDAR discrepancy detection
├── tools/                   # CLI utilities
│   ├── download_gis.py      # Bulk GIS data downloader
│   └── analyze_cache.py     # GIS cache analyzer
├── app.py                   # Streamlit dashboard
├── daemon.py                # Background scanner
├── train_models.py          # ML training CLI
├── data_sink.py             # TrainingLogger
└── retriever.py             # TF-IDF vector search
```

## Key Features

### Mismatch Detection (NEW)
The `inference/mismatch_detector.py` module identifies discrepancies between data sources:
- **Slope Mismatch**: GIS zoning says buildable, but LiDAR shows steep slopes
- **Zoning Opportunity**: Flat land with utilities but restrictive zoning
- **Utility Mismatch**: ML prediction differs from rule-based calculation
- **Flood Terrain Mismatch**: Low elevation not in FEMA flood zone

```python
from inference import MismatchDetector, UtilityPredictor
from loaders import GISLoader
from core import DecisionEngine

detector = MismatchDetector(
    predictor=UtilityPredictor(),
    gis_loader=GISLoader(),
    analyzer=DecisionEngine()
)

mismatches = detector.scan_region(quanta_list, min_severity=0.5)
print(detector.generate_report(mismatches))
```

## Data Output

The daemon logs all analyzed land sectors to `training_dataset.jsonl` in a format ready for ML training.
