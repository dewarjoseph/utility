"""
Dashboard - Visualize analysis results, view project details, and take action.
"""

import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from core.project import ProjectManager, Project
from core.governance import GovernanceManager

# Initialize managers
pm = ProjectManager()
gm = GovernanceManager()

st.set_page_config(
    page_title="Land Utility Dashboard",
    page_icon="🗺️",
    layout="wide"
)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
st.sidebar.title("🗺️ Dashboard")

projects = pm.list_projects()
project_options = {p.id: p.name for p in projects}

selected_project_id = st.sidebar.selectbox(
    "Select Project",
    options=list(project_options.keys()),
    format_func=lambda x: project_options[x],
    index=0 if projects else None
)

if not selected_project_id:
    st.info("No projects found. Create one in the Home page.")
    st.stop()

project = pm.get_project(selected_project_id)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Status:** {project.status}")
st.sidebar.markdown(f"**Points:** {project.points_collected}")
if project.stats:
    st.sidebar.metric("Avg Score", f"{project.stats.get('average_score', 0):.1f}/10")
    st.sidebar.metric("Max Score", f"{project.stats.get('max_score', 0):.1f}/10")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════════
st.title(f"📍 {project.name}")
st.caption(project.description)

tab_map, tab_data, tab_action = st.tabs(["🗺️ Map Analysis", "📊 Data Explorer", "🏛️ Take Action"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: MAP ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
with tab_map:
    # Load data
    data_path = project.training_data_path
    if not data_path.exists():
        st.warning("No data collected yet. Start a scan from the Home page.")
    else:
        try:
            # Read JSONL file
            data = []
            with open(data_path, "r") as f:
                for line in f:
                    data.append(json.loads(line))

            if not data:
                st.warning("Dataset is empty.")
            else:
                # Convert to DataFrame
                rows = []
                for item in data:
                    row = {
                        "lat": item["location"]["lat"],
                        "lon": item["location"]["lon"],
                        "score": item["expert_label"]["gross_utility_score"],
                    }
                    # Add features
                    row.update(item["features_raw"])
                    rows.append(row)

                df = pd.DataFrame(rows)

                # Map Visualization
                fig = px.scatter_mapbox(
                    df,
                    lat="lat",
                    lon="lon",
                    color="score",
                    size="score",
                    color_continuous_scale="Viridis",
                    size_max=15,
                    zoom=12,
                    mapbox_style="carto-positron",
                    hover_data=list(df.columns)
                )
                fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error loading data: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: DATA EXPLORER
# ═══════════════════════════════════════════════════════════════════════════
with tab_data:
    if 'df' in locals():
        st.subheader("Distribution of Scores")
        fig_hist = px.histogram(df, x="score", nbins=20, title="Utility Score Distribution")
        st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("Feature Correlations")
        # Compute correlation with score
        numeric_df = df.select_dtypes(include=['float64', 'int64', 'bool'])
        corr = numeric_df.corr()['score'].sort_values(ascending=False)
        st.bar_chart(corr.drop('score'))

        with st.expander("View Raw Data"):
            st.dataframe(df)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: TAKE ACTION (New for Phase 2)
# ═══════════════════════════════════════════════════════════════════════════
with tab_action:
    st.header("🏛️ Civic Action")
    st.markdown("Transition from analysis to action by proposing this project to your organization.")
    
    # 1. Select Organization
    orgs = gm.list_organizations()
    if not orgs:
        st.warning("No organizations found. Please create one in the 'Organization' page first.")
    else:
        selected_org_id = st.selectbox(
            "Propose to Organization",
            options=[o.id for o in orgs],
            format_func=lambda x: next((o.name for o in orgs if o.id == x), x)
        )
        target_org = gm.get_organization(selected_org_id)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Proposal Preview")
            prop_title = st.text_input("Proposal Title", value=f"Develop: {project.name}")
            
            # Auto-generate Statement of Purpose
            mission_statement = "advancing community welfare" # Default
            # In a real app, we'd pull this from the Bylaws/Charter of the org
            
            default_desc = (
                f"Proposal to acquire/develop the site analyzed in '{project.name}'.\n\n"
                f"**Statement of Purpose:**\n"
                f"This project aligns with {target_org.name}'s mission by {mission_statement}.\n"
                f"Based on analysis of {project.points_collected} points with an average score of "
                f"{project.stats.get('average_score', 0):.1f}."
            )
            prop_desc = st.text_area("Proposal Description", value=default_desc, height=200)
        
        with col2:
            st.subheader("💰 Financial & Impact Snapshot")

            if st.button("🔄 Generate Estimates"):
                from core.proforma import get_proforma_engine
                from core.scoring import get_scorer, UseCase

                # Financials
                pe = get_proforma_engine()
                financials = pe.generate_for_project(project)
                st.session_state['financial_est'] = financials

                # Community Score
                scorer = get_scorer(UseCase.COMMUNITY_CENTER)
                # Use average features from collected data as proxy for "site" features
                # In reality, we'd pick the *best* point.
                if 'df' in locals() and not df.empty:
                    # Get features of highest scoring point
                    best_point = df.loc[df['score'].idxmax()].to_dict()
                    impact_score = scorer.score(best_point)
                    st.session_state['impact_est'] = impact_score
                else:
                    st.session_state['impact_est'] = 0.0

            if 'financial_est' in st.session_state:
                fin = st.session_state['financial_est']
                st.metric("Est. Development Cost", f"${fin['total_development_cost']:,.0f}")
                st.metric("Est. Annual Dividend", f"${fin['community_dividend_annual']:,.0f}")
                st.metric("Projected ROI", f"{fin['yield_on_cost']*100:.1f}%")

            if 'impact_est' in st.session_state:
                st.metric("Community Benefit Score", f"{st.session_state['impact_est']:.1f}/10")
        
        st.divider()
        
        if st.button("🚀 Submit Proposal to Organization", type="primary"):
            # Create Proposal
            financial_summary = st.session_state.get('financial_est', {})
            impact_score = st.session_state.get('impact_est', 0.0)

            proposal = target_org.voting_engine.create_proposal(
                proposal_id=f"prop_{project.id[:6]}_{len(target_org.voting_engine.proposals)}",
                title=prop_title,
                description=prop_desc,
                options=["Approve", "Reject", "Request Revision"],
                project_id=project.id,
                financial_summary=financial_summary,
                community_benefit_score=impact_score
            )

            gm.save_organization(target_org)
            st.success(f"Proposal '{prop_title}' submitted to {target_org.name}!")
            st.info("Go to the **Organization** page to view and vote.")
