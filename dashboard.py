import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
from sklearn.decomposition import PCA
import numpy as np

# Page Config
st.set_page_config(page_title="Land Utility Engine | Neural Inspector", layout="wide")

st.title("Land Utility Engine: Neural Inspector")
st.markdown("### Deep Learning & Gross Utility Inference Dashboard")

# 1. Data Connector
@st.cache_data(ttl=5) # Cache data for 5 seconds to simulate "Live"
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

    # Flatten the JSON structure for Analytics
    df_raw = pd.DataFrame(data)
    
    # Extract nested fields
    # Label
    df_raw["utility_score"] = df_raw["expert_label"].apply(lambda x: x.get("gross_utility_score"))
    df_raw["trace"] = df_raw["expert_label"].apply(lambda x: x.get("reasoning_trace"))
    
    # Features (The "Neural Nodes")
    df_raw["feat_water"] = df_raw["features_raw"].apply(lambda x: x.get("has_water"))
    df_raw["feat_road"] = df_raw["features_raw"].apply(lambda x: x.get("has_road"))
    df_raw["feat_industrial"] = df_raw["features_raw"].apply(lambda x: x.get("is_industrial"))
    
    # Locations
    df_raw["lat"] = df_raw["location"].apply(lambda x: x.get("lat"))
    df_raw["lon"] = df_raw["location"].apply(lambda x: x.get("lon"))
    
    return df_raw

df = load_data()

if df.empty:
    st.warning("Waiting for Daemon to log data to 'training_dataset.jsonl'...")
    st.stop()

# 2. Key Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Scanned Micro-Sectors", len(df))
high_util_count = len(df[df["utility_score"] > 5])
col2.metric("High Utility Candidates", high_util_count)
col3.metric("Avg Utility Score", f"{df['utility_score'].mean():.2f}")

# 3. Neural Vector Space (PCA)
st.markdown("---")
st.subheader("🧠 Neural Vector Space (PCA Projection)")
st.markdown("Visualizing how the inference engine clusters land based on raw features.")

# Extract Feature Matrix
feature_cols = ["feat_water", "feat_road", "feat_industrial"]
X = df[feature_cols].values

if len(df) > 3:
    # Run PCA to squash dimensions to 2D
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
        color_continuous_scale="Viridis"
    )
    st.plotly_chart(fig_pca, use_container_width=True)
else:
    st.info("Not enough data points for Vector Analysis yet.")

# 4. Geospatial Intelligence
st.markdown("---")
st.subheader("🌍 Geospatial Utility Heatmap")
fig_map = px.scatter_mapbox(
    df, 
    lat="lat", 
    lon="lon", 
    color="utility_score",
    size="utility_score",
    color_continuous_scale="Magma", 
    zoom=13,
    mapbox_style="open-street-map",
    title="Real-World Utility Distribution"
)
st.plotly_chart(fig_map, use_container_width=True)

# 5. Inference Inspector
st.markdown("---")
st.subheader("🔍 Deep Inference Inspector")
st.markdown("Examine the 'Cognitive Trace' of specific datapoints.")

selected_idx = st.selectbox("Select a Sample ID to Inspect:", df.index)
sample = df.loc[selected_idx]

cols = st.columns(2)
with cols[0]:
    st.write("**Feature Activations**")
    st.json({
        "Water": sample["feat_water"],
        "Road": sample["feat_road"],
        "Industrial": sample["feat_industrial"]
    })

with cols[1]:
    st.write("**Inference Output**")
    st.metric("Gross Utility Score", sample["utility_score"])
    st.write("**Reasoning Trace:**")
    for t in sample["trace"]:
        st.code(t, language="text")
