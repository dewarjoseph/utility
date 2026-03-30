# 🛰️ Land Utility Engine

**Automated land utility analysis for industrial site selection and investment planning.**

Analyze geographic areas for optimal industrial use — desalination plants, silicon wafer fabrication, warehouses, and more. A comprehensive enterprise-grade platform combining advanced GIS integrations, machine learning utility predictions, RAG-powered knowledge bases, and decentralized deal room governance.

---

## ✨ Enterprise Features

- **Multi-Source Data Integration**: Automated data fetching from OSM, USGS, First Street Foundation, and US Census (elevation, roads, power, rail, ports, coastline, demographic data, climate risk).
- **Synergy-Based Scoring & Inference**: Advanced rule-based scoring alongside a Predictive ML Strategy engine that finds optimal feature synergies with diminishing returns handling.
- **Asynchronous Processing Engine**: Threaded background workers utilizing a SQLite-backed job queue for resilient background scanning without blocking the main UI.
- **Interactive Multi-page Dashboard**: A powerful Streamlit-based web application featuring interactive mapping, charting, point inspection, and real-time updates.
- **RAG Knowledge Base**: Integrated document retrieval allowing for natural language querying over municipal codes and organizational documents.
- **Deal Room & Governance**: Built-in modules for managing decentralized autonomous organizations (DAOs), investment deals, and community voting with robust proforma generation and Monte Carlo risk sensitivity.

---

## 📸 Platform Capabilities & Screenshots

Here is a visual tour of the platform's core workflows and capabilities.

### 1. Main Dashboard & Project Setup
The entry point for site selection. Users create projects, define bounding areas (address, coordinates, radius), and start asynchronous background workers to scan the region. Visualizes scanned utility points and key land characteristics on interactive maps.
![Main Dashboard View](docs/images/main_dashboard.png)

### 2. Multi-page Architecture & Navigation
The platform is organized logically to support the full lifecycle of project development, from initial GIS scans to project scenarios, and all the way to DAO deal room execution.
![Navigation Menu & Architecture](docs/images/navigation_menu.png)

### 3. Scenario Analysis & Predictive ML Strategy
Simulate different land configurations, assess varying utility scenarios, and use the integrated Machine Learning engine to predict optimal outcomes for use cases like Data Centers, Desalination Plants, or Warehousing.
![Scenario Analysis View](docs/images/scenario_analysis.png)
![Predictive ML Strategy View](docs/images/predictive_strategy.png)

### 4. Organization & Deal Room
Manage non-profit entities, view active investment deals, and coordinate capital allocation. Includes tools for member verification and viewing active syndications for land acquisition.
![Deal Room Interface](docs/images/deal_room.png)

### 5. Governance & Voting
Participate in organizational decisions. View active proposals, read detailed proformas for land development, and vote on community initiatives using the integrated decentralized governance module. Includes sensitivity analysis using Monte Carlo simulations.
![Governance Voting Interface](docs/images/governance_voting.png)

### 6. RAG Knowledge Base
An intelligent search interface allowing users to query local municipal codes, zoning laws, and organizational bylaws using Retrieval-Augmented Generation (RAG).
![RAG Knowledge Base](docs/images/knowledge_base.png)

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone <repo_url>
cd <repo_directory>

# Install dependencies
pip install -r requirements.txt

# Launch the dashboard
streamlit run app.py
```

---

## 🔧 Architecture & Modules

The platform is built on a modular architecture separating core logic, data ingestion, and the Streamlit UI.

### The Core UI Workflow (`app.py`, `pages/`)
Built with Streamlit (`>=1.34.0`), utilizing multi-page applications. Features secure HTML/CSS injection for themes, interactive Folium maps, and real-time refresh functionality.
- **`app.py`**: The application entry point and project manager.
- **`pages/1_Dashboard.py`**: The main mapping and scoring interface.
- **`pages/2_Organization.py` / `pages/6_Deals.py`**: Non-profit management and active investment deal tracking.
- **`pages/3_Scenarios.py` / `pages/4_Governance.py`**: Tools to draft proposals and vote on development investments.
- **`pages/5_Knowledge.py` / `pages/3_Knowledge_Base.py`**: RAG-powered vector search over relevant documents.

### The Asynchronous Engine (`core/worker.py`, `core/job_queue.py`)
Handles heavy GIS processing asynchronously to prevent blocking the UI.
- **`JobQueue`**: A thread-safe, SQLite-backed persistent queue for managing background tasks.
- **`Worker`**: A threaded execution engine that pulls tasks from the queue, fetches data via loaders, calculates utility scores, and batches results to disk (JSON/SQLite). Optimizes memory by accumulating points before saving.

### The Data Layer (`loaders/`, `core/api_layer.py`)
Responsible for fetching, caching, and normalizing geographical and demographic data.
- **`UnifiedDataFetcher`**: Orchestrates parallel batch requests across multiple APIs (Elevation, Demographics, Infrastructure) using `ThreadPoolExecutor`.
- **`OSMLoader`**: Integrates with OpenStreetMap, using bounding-box queries to avoid N+1 bottlenecks and in-memory feature distance calculations.
- **`SocioeconomicLoader`**: Connects to the US Census Bureau API for demographic and economic insights.
- **`api_layer.py`**: Manages external API integrations (Gridics, 1build, First Street Foundation, Google Solar), featuring graceful fallbacks to mock data if keys are absent.

### Advanced Modules (`core/`, `inference/`)
- **RAG Knowledge Base (`core/rag.py`)**: Vectorizes documents using deterministic embeddings and retrieves relevant context based on cosine similarity for natural language queries.
- **Governance & Deals (`core/governance.py`, `core/deal_room.py`)**: Manages the persistence of community votes, proposals, investment tracking, and treasury management (`core/revenue_share.py`).
- **Proforma & Risk (`core/proforma.py`, `core/sensitivity.py`)**: Generates financial projections for site development and runs Monte Carlo simulations for stress testing against market volatility.
- **ML Engine (`inference/ml_engine.py`)**: Trains models on per-project datasets (`training_dataset.jsonl`) to dynamically infer underlying property utility metrics.

---

## 🏭 Use-Case Profiles

| Profile | Optimized For | Technical Requirements Met |
|---------|---------------|---------------------------|
| 🌊 Desalination Plant | Coastal access, power grid, industrial zoning | Haversine distance to coastlines, robust power infrastructure via OSM |
| 💎 Silicon Wafer Fab | Power, water, low seismic risk | Stable terrain (USGS Elevation/Slope), reliable utility connections |
| 📦 Warehouse/Distribution | Highway, rail, port access | Routing logistics via OSM roads/railways, regional labor market (Census) |
| 🏭 Light Manufacturing | Industrial zoning, road access | Zoning compliance (Gridics APIs), proximity to local workforce |

## 📁 Additional Documentation

For deeper dives into specific technical implementations, please see the `docs/` folder:
- [Bulk Download Guide](docs/BULK_DOWNLOAD_GUIDE.md)
- [GIS Integration Specification](docs/GIS_INTEGRATION.md)
- [LiDAR Setup Instructions](docs/LIDAR_SETUP.md)

## 📝 License

MIT