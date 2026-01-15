"""
Project Dashboard - View and analyze a specific project.
"""

import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
from pathlib import Path

st.set_page_config(page_title="Project Dashboard", page_icon="🗺️", layout="wide")

# Hide chrome
st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
    .block-container { padding: 0.5rem 1rem; }
</style>
""", unsafe_allow_html=True)

from core.project import ProjectManager, Project, ProjectStatus
from core.job_queue import JobQueue, JobStatus

pm = ProjectManager()
queue = JobQueue()

# ═══════════════════════════════════════════════════════════════════════════
# PROJECT SELECTION
# ═══════════════════════════════════════════════════════════════════════════
projects = pm.list_projects()

if not projects:
    st.warning("No projects found. Create a project first!")
    if st.button("← Back to Main"):
        st.switch_page("app.py")
    st.stop()

# Select project - handle case where saved project was deleted
project_options = {p.id: f"{p.name} ({p.id})" for p in projects}
project_ids = list(project_options.keys())

# Validate saved project still exists
saved_project = st.session_state.get('selected_project')
if saved_project and saved_project in project_ids:
    default_idx = project_ids.index(saved_project)
else:
    default_idx = 0
    # Clear stale reference
    if saved_project:
        st.session_state.pop('selected_project', None)

selected_id = st.sidebar.selectbox(
    "Select Project",
    options=project_ids,
    format_func=lambda x: project_options[x],
    index=default_idx
)

project = pm.get_project(selected_id)
if not project:
    st.error("Project not found")
    st.stop()

st.session_state.selected_project = project.id

# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════
col1, col2, col3 = st.columns([4, 1, 1])

with col1:
    st.title(f"🗺️ {project.name}")

with col2:
    if project.status == ProjectStatus.SCANNING:
        st.success("🔄 Scanning")
    elif project.status == ProjectStatus.COMPLETED:
        st.info("✅ Complete")
    elif project.status == ProjectStatus.QUEUED:
        st.warning("⏳ Queued")
    else:
        st.caption(project.status)

with col3:
    if project.status not in [ProjectStatus.SCANNING, ProjectStatus.QUEUED]:
        if st.button("▶️ Start"):
            job_id = queue.enqueue(project.id)
            project.status = ProjectStatus.QUEUED
            project.save()
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=5)
def load_project_data(project_id: str, training_path: str):
    if not os.path.exists(training_path):
        return pd.DataFrame()
    
    data = []
    with open(training_path, "r") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except:
                continue
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Extract nested fields
    df["score"] = df["expert_label"].apply(lambda x: x.get("gross_utility_score", 0) if isinstance(x, dict) else 0)
    df["lat"] = df["location"].apply(lambda x: x.get("lat", 0) if isinstance(x, dict) else 0)
    df["lon"] = df["location"].apply(lambda x: x.get("lon", 0) if isinstance(x, dict) else 0)
    
    # Features
    if "features_raw" in df.columns:
        df["has_water"] = df["features_raw"].apply(lambda x: x.get("has_water", False) if isinstance(x, dict) else False)
        df["has_road"] = df["features_raw"].apply(lambda x: x.get("has_road", False) if isinstance(x, dict) else False)
        df["is_industrial"] = df["features_raw"].apply(lambda x: x.get("is_industrial", False) if isinstance(x, dict) else False)
    
    # Colors
    df["color_r"] = ((10 - df["score"]) / 10 * 255).astype(int).clip(0, 255)
    df["color_g"] = (df["score"] / 10 * 255).astype(int).clip(0, 255)
    df["color_b"] = 100
    
    df = df.reset_index(drop=True)
    df["id"] = df.index
    df["score_str"] = df["score"].apply(lambda x: f"{x:.1f}")
    
    return df

df = load_project_data(project.id, str(project.training_data_path))

if df.empty:
    st.info("No data yet. Start scanning to collect data points.")
    
    st.subheader("Project Area")
    st.write(f"Center: ({project.bounds.center_latitude:.4f}, {project.bounds.center_longitude:.4f})")
    st.write(f"Area: {project.bounds.area_sq_km:.2f} sq km")
    
    view = pdk.ViewState(
        latitude=project.bounds.center_latitude,
        longitude=project.bounds.center_longitude,
        zoom=13,
    )
    
    st.pydeck_chart(pdk.Deck(
        layers=[],
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    ), height=400)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# INITIALIZE ALL STATE (before any rendering)
# ═══════════════════════════════════════════════════════════════════════════
# Handle edge case: if only 1 point, set max_idx to at least 1 to avoid slider error
max_idx = max(1, len(df) - 1)
single_point_mode = len(df) == 1

# Initialize slider value if not set or if out of range
if "slider_val" not in st.session_state:
    st.session_state.slider_val = 0
st.session_state.slider_val = max(0, min(st.session_state.slider_val, len(df) - 1))

# Initialize jump input to match slider
if "jump_val" not in st.session_state:
    st.session_state.jump_val = st.session_state.slider_val

# Current index is always from slider (single source of truth)
current_idx = st.session_state.slider_val

# Get current point data (available to all components)
current_point = df.iloc[current_idx]

# ═══════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Points", len(df))
m2.metric("High Value", len(df[df["score"] >= project.settings.high_value_threshold]))
m3.metric("Avg Score", f"{df['score'].mean():.2f}")
m4.metric("Area", f"{project.bounds.area_sq_km:.1f} km²")
m5.metric("Status", project.status.value if hasattr(project.status, 'value') else str(project.status))

# ═══════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════
tab_map, tab_analysis, tab_settings = st.tabs(["🗺️ Map", "📊 Analysis", "⚙️ Settings"])

with tab_map:
    # Callbacks update the single source of truth (slider_val)
    def go_prev():
        st.session_state.slider_val = max(0, st.session_state.slider_val - 1)
    
    def go_next():
        st.session_state.slider_val = min(max_idx, st.session_state.slider_val + 1)
    
    def jump_to():
        st.session_state.slider_val = st.session_state.jump_val
    
    # Layout
    map_col, detail_col = st.columns([3, 1])
    
    with detail_col:
        st.subheader("Point Details")
        
        # Navigation
        c1, c2 = st.columns(2)
        c1.button("Prev", on_click=go_prev, disabled=(current_idx <= 0))
        c2.button("Next", on_click=go_next, disabled=(current_idx >= max_idx))
        
        # Jump input - key controls value via session state
        st.number_input(
            "Go to #", 
            min_value=0, 
            max_value=max_idx,
            key="jump_val",
            on_change=jump_to
        )
        
        st.divider()
        
        # Score with use-case indicator
        st.metric("Score", f"{current_point['score']:.1f}")
        st.caption(f"({current_point['lat']:.5f}, {current_point['lon']:.5f})")
        
        # Show use case if set
        use_case_labels = {
            "general": "General",
            "desalination_plant": "🌊 Desalination",
            "silicon_wafer_fab": "💎 Silicon Fab",
            "warehouse_distribution": "📦 Warehouse",
            "light_manufacturing": "🏭 Manufacturing",
        }
        uc = project.settings.use_case if hasattr(project.settings, 'use_case') else "general"
        st.caption(f"Profile: {use_case_labels.get(uc, uc)}")
        
        st.divider()
        
        # Features - grouped by category
        st.markdown("**Features:**")
        features = current_point.get("features_raw", {})
        if isinstance(features, dict):
            # Infrastructure
            infra_keys = ["has_water", "has_road", "has_power_nearby", "rail_nearby", 
                         "port_nearby", "highway_nearby", "coastal_access"]
            for key in infra_keys:
                if key in features:
                    val = features[key]
                    icon = "✅" if val else "❌"
                    st.text(f"{icon} {key.replace('_', ' ').replace('has ', '').title()}")
            
            # Land use  
            land_keys = ["is_industrial", "is_residential", "is_commercial", "is_agricultural"]
            for key in land_keys:
                if key in features and features[key]:
                    st.text(f"🏷️ {key.replace('is_', '').title()}")
            
            # Environmental
            if features.get("flood_risk"):
                st.text("⚠️ Flood Risk")
            if features.get("high_elevation"):
                st.text("⛰️ High Elevation")
            if features.get("urban_area"):
                st.text("🏙️ Urban Area")
    
    with map_col:
        # Slider - show point count or info if only 1 point
        if single_point_mode:
            st.info("Only 1 point collected so far...")
        else:
            st.slider(
                f"Point {current_idx}/{len(df)-1}", 
                min_value=0, 
                max_value=len(df)-1,
                key="slider_val"
            )
        
        # Prepare map data with current selection
        df_map = df.copy()
        df_map["alpha"] = (df_map["id"] == current_idx).apply(lambda x: 255 if x else 100)
        
        # Layers
        main_layer = pdk.Layer(
            "ScatterplotLayer",
            df_map,
            get_position=["lon", "lat"],
            get_fill_color=["color_r", "color_g", "color_b", "alpha"],
            get_radius=5,
            radius_min_pixels=4,
            radius_max_pixels=15,
            pickable=True,  # Enable for tooltip
        )
        
        highlight_layer = pdk.Layer(
            "ScatterplotLayer",
            df.iloc[[current_idx]],
            get_position=["lon", "lat"],
            get_fill_color=[255, 255, 0, 230],
            get_radius=15,
            radius_min_pixels=18,
            radius_max_pixels=40,
        )
        
        view = pdk.ViewState(
            latitude=float(current_point["lat"]),
            longitude=float(current_point["lon"]),
            zoom=15,
        )
        
        st.pydeck_chart(
            pdk.Deck(
                layers=[main_layer, highlight_layer],
                initial_view_state=view,
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                tooltip={"text": "Point #{id}\nScore: {score_str}"}
            ),
            height=480
        )
        st.caption("Green=High | Red=Low | Yellow=Selected | Hover for info")

with tab_analysis:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Score Distribution")
        fig_hist = px.histogram(df, x="score", nbins=20, 
                                color_discrete_sequence=["#00bfff"])
        fig_hist.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_hist, width="stretch")
    
    with col2:
        st.subheader("📈 Score Over Time")
        df_time = df.copy()
        df_time["ma"] = df_time["score"].rolling(window=20, min_periods=1).mean()
        fig_line = px.line(df_time, y="ma", 
                           labels={"index": "Sample #", "ma": "Avg Score"})
        fig_line.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_line, width="stretch")
    
    # Feature breakdown - comprehensive
    st.subheader("🏷️ Feature Analysis")
    
    # Build feature stats from features_raw
    feature_stats = []
    
    # Define features to analyze
    features_to_check = [
        ("has_water", "💧 Water Access"),
        ("has_road", "🛣️ Road Access"),
        ("has_power_nearby", "⚡ Power Grid"),
        ("rail_nearby", "🚂 Rail Access"),
        ("highway_nearby", "🛤️ Highway"),
        ("coastal_access", "🌊 Coastal"),
        ("is_industrial", "🏭 Industrial"),
        ("is_commercial", "🏢 Commercial"),
        ("is_residential", "🏠 Residential"),
        ("urban_area", "🏙️ Urban"),
    ]
    
    for feat_key, feat_name in features_to_check:
        # Check in features_raw column
        has_feature = []
        for idx, row in df.iterrows():
            features = row.get("features_raw", {})
            if isinstance(features, dict):
                has_feature.append(features.get(feat_key, False))
            else:
                has_feature.append(False)
        
        count = sum(has_feature)
        if count > 0:
            # Calculate avg score when feature is present
            mask = pd.Series(has_feature)
            avg_score = df.loc[mask, "score"].mean() if mask.sum() > 0 else 0
            feature_stats.append({
                "Feature": feat_name,
                "Count": count,
                "% of Points": f"{count/len(df)*100:.1f}%",
                "Avg Score": f"{avg_score:.2f}"
            })
    
    if feature_stats:
        st.dataframe(pd.DataFrame(feature_stats), width="stretch", hide_index=True)
    else:
        st.info("No feature data available yet")
    
    # Synergy info
    st.subheader("🔗 Synergy Bonuses")
    uc = project.settings.use_case if hasattr(project.settings, 'use_case') else "general"
    
    synergy_info = {
        "general": [
            ("💧 Water + 🏭 Industrial", "+1.0"),
            ("🛣️ Road + ⚡ Power", "+0.5"),
        ],
        "desalination_plant": [
            ("🌊 Coastal + 🏭 Industrial", "+2.5"),
            ("🌊 Coastal + ⚡ Power", "+2.0"),
            ("📉 Low Elevation + 🌊 Coastal", "+1.5"),
            ("⚡ Power + 🏭 Industrial", "+1.0"),
        ],
        "silicon_wafer_fab": [
            ("⚡ Power + 🏭 Industrial", "+2.0"),
            ("💧 Water + 🏭 Industrial", "+1.5"),
            ("🛤️ Highway + 🏭 Manufacturing Workforce", "+1.0"),
        ],
        "warehouse_distribution": [
            ("🛤️ Highway + 🚂 Rail", "+2.5"),
            ("🛤️ Highway + ⚓ Port", "+2.0"),
            ("🏭 Industrial + 🛤️ Highway", "+1.0"),
        ],
        "light_manufacturing": [
            ("🏭 Industrial + ⚡ Power", "+1.5"),
            ("🛣️ Road + 🛤️ Highway", "+1.0"),
        ],
    }
    
    synergies = synergy_info.get(uc, synergy_info["general"])
    for combo, bonus in synergies:
        st.text(f"{combo} → {bonus}")

with tab_settings:
    st.subheader("⚙️ Project Settings")
    
    # Use-case profile
    use_case_info = {
        "general": ("🏭 General Industrial", "Balanced scoring for general industrial development"),
        "desalination_plant": ("🌊 Desalination Plant", "Optimized for coastal water facilities"),
        "silicon_wafer_fab": ("💎 Silicon Wafer Fab", "Semiconductor manufacturing"),
        "warehouse_distribution": ("📦 Warehouse/Distribution", "Logistics and distribution centers"),
        "light_manufacturing": ("🏭 Light Manufacturing", "General manufacturing facilities"),
    }
    
    uc = project.settings.use_case if hasattr(project.settings, 'use_case') else "general"
    uc_name, uc_desc = use_case_info.get(uc, ("Unknown", ""))
    
    st.write("**Analysis Profile:**")
    st.info(f"{uc_name}\n\n{uc_desc}")
    
    st.markdown("---")
    st.write("**Thresholds:**")
    col1, col2 = st.columns(2)
    col1.metric("High Value", f"≥ {project.settings.high_value_threshold}")
    col2.metric("Low Value", f"≤ {project.settings.low_value_threshold}")
    
    st.markdown("---")
    st.write("**Bounds:**")
    st.write(f"Lat: {project.bounds.min_latitude:.4f} to {project.bounds.max_latitude:.4f}")
    st.write(f"Lon: {project.bounds.min_longitude:.4f} to {project.bounds.max_longitude:.4f}")
    st.write(f"Area: {project.bounds.area_sq_km:.2f} km²")
    
    st.markdown("---")
    st.write("**Fallback Scoring Rules:**")
    st.caption("Used if synergy scoring unavailable")
    for rule in project.settings.scoring_rules[:3]:  # Show first 3 only
        st.text(f"{'✅' if rule.enabled else '❌'} {rule.name}: {rule.points_when_true:+.1f} / {rule.points_when_false:+.1f}")

# ═══════════════════════════════════════════════════════════════════════════
# AUTO REFRESH
# ═══════════════════════════════════════════════════════════════════════════
# Auto-refresh - defaults to FALSE, user must enable
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

if st.sidebar.checkbox("Auto-refresh", value=st.session_state.auto_refresh, key="auto_refresh"):
    import time
    time.sleep(3)
    st.rerun()
