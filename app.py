import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import PCA
import numpy as np
import subprocess
import time
import logging

# Configure logging - outputs to console where streamlit is running
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app")

# Page Config
st.set_page_config(page_title="Land Utility Engine | MVP", layout="wide", initial_sidebar_state="expanded")

# Initialize session state for daemon control
if 'daemon_process' not in st.session_state:
    st.session_state.daemon_process = None
if 'daemon_cycles' not in st.session_state:
    st.session_state.daemon_cycles = 0

# Check if daemon is running
def is_daemon_running():
    if st.session_state.daemon_process is not None:
        poll = st.session_state.daemon_process.poll()
        return poll is None
    return False

# Sidebar - Daemon Control
with st.sidebar:
    st.title("🎛️ Control Panel")
    
    st.subheader("Daemon Status")
    daemon_running = is_daemon_running()
    
    if daemon_running:
        st.success("🟢 RUNNING")
        
        if os.path.exists("daemon_status.json"):
            try:
                with open("daemon_status.json", "r") as f:
                    status = json.load(f)
                    st.session_state.daemon_cycles = status.get("cycles", 0)
            except:
                pass
        
        st.metric("Cycles Completed", st.session_state.daemon_cycles)
        
        if st.button("⏹️ Stop Daemon", type="primary"):
            if st.session_state.daemon_process:
                st.session_state.daemon_process.terminate()
                st.session_state.daemon_process = None
            st.rerun()
    else:
        st.error("🔴 STOPPED")
        if st.button("▶️ Start Daemon", type="primary"):
            st.session_state.daemon_process = subprocess.Popen(
                ["python", "daemon.py"],
                cwd=os.getcwd()
            )
            st.session_state.daemon_cycles = 0
            time.sleep(1)
            st.rerun()
    
    st.markdown("---")
    st.subheader("Configuration")
    auto_refresh = st.checkbox("Auto-refresh Dashboard", value=True)
    if auto_refresh:
        st.info("Dashboard refreshes every 5 seconds")
    
    st.markdown("---")
    if st.button("🤖 Train ML Models"):
        with st.spinner("Training models..."):
            result = subprocess.run(["python", "train_models.py"], capture_output=True, text=True)
            st.success("Training complete!")

# Main Dashboard
st.title("🌍 Land Utility Engine: Neural Inspector")
st.markdown("### Automated Ground Truth Analysis for Investment & Conservation")

# Auto-refresh logic
if auto_refresh and daemon_running:
    time.sleep(5)
    st.rerun()

# Data Connector
@st.cache_data(ttl=5)
def load_data():
    data = []
    file_path = "training_dataset.jsonl"
    
    if not os.path.exists(file_path):
        return pd.DataFrame()

    with open(file_path, "r") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except:
                continue
    
    if not data:
        return pd.DataFrame()

    df_raw = pd.DataFrame(data)
    
    df_raw["utility_score"] = df_raw["expert_label"].apply(lambda x: x.get("gross_utility_score"))
    df_raw["trace"] = df_raw["expert_label"].apply(lambda x: x.get("reasoning_trace"))
    
    df_raw["feat_water"] = df_raw["features_raw"].apply(lambda x: x.get("has_water"))
    df_raw["feat_road"] = df_raw["features_raw"].apply(lambda x: x.get("has_road"))
    df_raw["feat_industrial"] = df_raw["features_raw"].apply(lambda x: x.get("is_industrial"))
    
    df_raw["lat"] = df_raw["location"].apply(lambda x: x.get("lat"))
    df_raw["lon"] = df_raw["location"].apply(lambda x: x.get("lon"))
    
    return df_raw

df = load_data()

if df.empty:
    st.warning("⏳ Waiting for Daemon to generate data... Start the daemon from the sidebar.")
    st.stop()

# Tabs for navigation
tab1, tab2 = st.tabs(["📊 Analytics Dashboard", "🤖 ML Performance"])

with tab1:
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Scanned Sectors", len(df))
    high_util_count = len(df[df["utility_score"] > 5])
    col2.metric("⭐ High Utility", high_util_count)
    col3.metric("📈 Avg Score", f"{df['utility_score'].mean():.2f}")
    col4.metric("🔄 Daemon Cycles", st.session_state.daemon_cycles)

    # Neural Vector Space (PCA)
    st.markdown("---")
    st.subheader("🧠 Neural Vector Space (PCA Projection)")
    st.markdown("Visualizing how the inference engine clusters land based on raw features.")

    feature_cols = ["feat_water", "feat_road", "feat_industrial"]
    X = df[feature_cols].values

    if len(df) > 3:
        pca = PCA(n_components=2)
        components = pca.fit_transform(X)
        
        df["pca_x"] = components[:, 0]
        df["pca_y"] = components[:, 1]
        
        fig_pca = px.scatter(
            df, 
            x="pca_x", 
            y="pca_y", 
            color="utility_score",
            hover_data=["trace"],
            title="Feature Space Clustering (Color = Utility Score)",
            color_continuous_scale="Viridis",
            height=400
        )
        st.plotly_chart(fig_pca, width="stretch")
    else:
        st.info("Not enough data points for Vector Analysis yet.")

    # Geospatial Intelligence
    st.markdown("---")
    st.subheader("🗺️ Geospatial Utility Heatmap")
    fig_map = px.scatter_map(
        df, 
        lat="lat", 
        lon="lon", 
        color="utility_score",
        size="utility_score",
        color_continuous_scale="Magma", 
        zoom=13,
        title="Real-World Utility Distribution",
        height=500
    )
    st.plotly_chart(fig_map, width="stretch")

    # Deep Inference Inspector
    st.markdown("---")
    st.subheader("🔍 Deep Inference Inspector")
    st.markdown("Examine the cognitive reasoning process for specific land sectors.")

    selected_idx = st.selectbox("Select a Sample ID to Inspect:", df.index, key="inspector_select")
    sample = df.loc[selected_idx]

    cols = st.columns([1, 2])

    with cols[0]:
        st.markdown("#### 📋 Feature Activations")
        
        water_val = bool(sample["feat_water"])
        road_val = bool(sample["feat_road"])
        industrial_val = bool(sample["feat_industrial"])
        
        st.metric("💧 Water Infrastructure", "✓ Yes" if water_val else "✗ No")
        st.metric("🛣️ Road Access", "✓ Yes" if road_val else "✗ No")
        st.metric("🏭 Industrial Zoning", "✓ Yes" if industrial_val else "✗ No")
        
        st.markdown("---")
        st.metric("🎯 Final Utility Score", f"{sample['utility_score']:.1f}")

    with cols[1]:
        st.markdown("#### 📊 Reasoning Waterfall")
        
        trace_items = sample["trace"]
        
        measures = ["relative"]
        x_labels = ["Base"]
        y_values = [0]
        
        for item in trace_items:
            if "(+" in item or "(-" in item:
                value_str = item.split("(")[1].split(")")[0]
                value = float(value_str)
                label = item.split("(")[0].strip()
                
                x_labels.append(label)
                y_values.append(value)
                measures.append("relative")
        
        x_labels.append("Total")
        y_values.append(sample["utility_score"])
        measures.append("total")
        
        fig_waterfall = go.Figure(go.Waterfall(
            name="Utility Calculation",
            orientation="v",
            measure=measures,
            x=x_labels,
            y=y_values,
            textposition="outside",
            text=[f"{v:+.1f}" if v != 0 else "" for v in y_values],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "green"}},
            decreasing={"marker": {"color": "red"}},
            totals={"marker": {"color": "blue"}}
        ))
        
        fig_waterfall.update_layout(
            title="Cognitive Trace: How the Score was Built",
            showlegend=False,
            height=400
        )
        
        st.plotly_chart(fig_waterfall, width="stretch")

with tab2:
    st.subheader("🤖 ML Model Performance")
    
    if os.path.exists("best_model.pkl"):
        import joblib
        from inference import MLEngine
        
        engine = MLEngine()
        
        st.success("✓ Trained model found!")
        
        # Feature Importance
        st.markdown("### Feature Importance")
        importances = engine.get_feature_importance()
        
        if importances:
            imp_df = pd.DataFrame(list(importances.items()), columns=['Feature', 'Importance'])
            imp_df = imp_df.sort_values('Importance', ascending=False).head(10)
            
            fig_imp = px.bar(
                imp_df,
                x='Importance',
                y='Feature',
                orientation='h',
                title="Top 10 Most Important Features",
                color='Importance',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_imp, width="stretch")
        
        # Model Metrics
        st.markdown("### Model Performance")
        col1, col2, col3 = st.columns(3)
        col1.metric("Best Model", engine.best_model_name if engine.best_model_name else "Unknown")
        col2.metric("R² Score", f"{engine.best_score:.4f}" if engine.best_score > -np.inf else "N/A")
        col3.metric("Training Samples", len(df))
        
    else:
        st.info("No trained model found. Click 'Train ML Models' in the sidebar to begin.")
        st.markdown("**Requirements:**")
        st.markdown("- At least 50 data samples")
        st.markdown("- XGBoost and LightGBM installed (`pip install -r requirements.txt`)")

# Footer
st.markdown("---")
st.caption("Land Utility Engine MVP | Automated Ground Truth Analysis")
