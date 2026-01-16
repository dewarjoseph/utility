"""
Scenario Analysis Page - What-if scenarios and stress testing.

Provides Monte Carlo simulation and sensitivity analysis for pro formas.
"""

import streamlit as st

st.set_page_config(
    page_title="Scenario Analysis - Gross Utility",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
    .block-container { padding: 1rem 2rem; }
</style>
""", unsafe_allow_html=True)

from core.sensitivity import SensitivityAnalyzer
from core.proforma import ProFormaEngine, ProFormaInputs
from loaders.environmental import get_environmental_loader

st.title("📊 Scenario Analysis")
st.markdown("*Stress test your project with what-if scenarios and Monte Carlo simulation.*")

# Sidebar inputs
with st.sidebar:
    st.header("Project Parameters")
    
    lot_size = st.number_input("Lot Size (sqft)", value=10000, min_value=1000)
    buildable_sqft = st.number_input("Buildable Area (sqft)", value=15000, min_value=1000)
    num_units = st.number_input("Number of Units", value=10, min_value=1)
    
    st.markdown("---")
    st.header("Financial Assumptions")
    
    interest_rate = st.slider("Interest Rate (%)", 4.0, 10.0, 6.5, 0.25) / 100
    ltv_ratio = st.slider("LTV Ratio (%)", 50, 80, 65) / 100

# Calculate base pro forma
engine = ProFormaEngine()
inputs = ProFormaInputs(
    lot_size_sqft=lot_size,
    buildable_sqft=buildable_sqft,
    num_units=num_units,
)
base_proforma = engine.calculate(inputs)

# Display base metrics
st.header("📈 Base Case Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Cost", f"${base_proforma.total_development_cost:,.0f}")
col2.metric("NOI", f"${base_proforma.net_operating_income:,.0f}")
col3.metric("Yield on Cost", f"{base_proforma.yield_on_cost*100:.1f}%")
col4.metric("Community Dividend", f"${base_proforma.community_dividend_annual:,.0f}")

st.markdown("---")

# Tabs for different analyses
tab_scenarios, tab_montecarlo, tab_environmental = st.tabs([
    "🎚️ What-If Scenarios", "🎲 Monte Carlo", "🌍 Environmental Risk"
])

with tab_scenarios:
    st.header("What-If Scenario Analysis")
    
    analyzer = SensitivityAnalyzer()
    loan_amount = base_proforma.total_development_cost * ltv_ratio
    
    # Interest rate scenarios
    st.subheader("Interest Rate Sensitivity")
    rate_change = st.slider("Rate Change (%)", -2.0, 3.0, 1.0, 0.25)
    new_rate = interest_rate + (rate_change / 100)
    
    result = analyzer.analyze_interest_rate(
        interest_rate, new_rate, loan_amount, base_proforma.net_operating_income
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Base Cash Flow", f"${result.base_value:,.0f}")
    with col2:
        delta_color = "normal" if result.adjusted_value >= result.base_value else "inverse"
        st.metric("Adjusted Cash Flow", f"${result.adjusted_value:,.0f}", 
                  f"{result.impact_pct:+.1f}%", delta_color=delta_color)
    
    st.info(f"💡 {result.recommendation}")
    
    # Construction cost scenarios
    st.subheader("Construction Cost Sensitivity")
    cost_change = st.slider("Cost Change (%)", -20, 30, 0, 5)
    
    cost_result = analyzer.analyze_construction_cost(
        base_proforma.hard_costs, cost_change, 0.06
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Base Hard Costs", f"${cost_result.base_value:,.0f}")
    with col2:
        st.metric("Adjusted Hard Costs", f"${cost_result.adjusted_value:,.0f}",
                  f"{cost_change:+d}%")
    
    st.info(f"💡 {cost_result.recommendation}")

with tab_montecarlo:
    st.header("Monte Carlo Simulation")
    st.markdown("Simulate 1,000 random scenarios to understand the range of possible outcomes.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        cost_vol = st.slider("Cost Volatility (%)", 5, 25, 10) / 100
    with col2:
        rent_vol = st.slider("Rent Volatility (%)", 5, 20, 8) / 100
    with col3:
        vacancy_vol = st.slider("Vacancy Volatility (%)", 1, 10, 3) / 100
    
    if st.button("🎲 Run Simulation", type="primary"):
        with st.spinner("Running 1,000 iterations..."):
            mc_result = analyzer.run_monte_carlo(
                base_proforma.net_operating_income,
                cost_volatility=cost_vol,
                rent_volatility=rent_vol,
                vacancy_volatility=vacancy_vol,
                iterations=1000
            )
        
        st.success("Simulation complete!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Expected NOI", f"${mc_result.mean_noi:,.0f}")
        col2.metric("Std Deviation", f"${mc_result.std_noi:,.0f}")
        col3.metric("Probability Positive", f"{mc_result.probability_positive:.0f}%")
        
        st.subheader("Distribution of Outcomes")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Worst Case", f"${mc_result.worst_case:,.0f}")
        col2.metric("5th Percentile", f"${mc_result.percentile_5:,.0f}")
        col3.metric("Median", f"${mc_result.percentile_50:,.0f}")
        col4.metric("95th Percentile", f"${mc_result.percentile_95:,.0f}")
        col5.metric("Best Case", f"${mc_result.best_case:,.0f}")

with tab_environmental:
    st.header("Environmental Risk Assessment")
    
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input("Latitude", value=36.9741, format="%.4f")
    with col2:
        longitude = st.number_input("Longitude", value=-122.0308, format="%.4f")
    
    env_loader = get_environmental_loader()
    risk_profile = env_loader.get_risk_profile(latitude, longitude, buildable_sqft * 0.3)
    
    st.subheader("Risk Factors")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("🌊 Flood Risk", f"{risk_profile.flood.factor}/10", 
                risk_profile.flood.level.name)
    col2.metric("🔥 Fire Risk", f"{risk_profile.fire.factor}/10",
                risk_profile.fire.level.name)
    col3.metric("🌡️ Heat Risk", f"{risk_profile.heat.factor}/10")
    col4.metric("📊 Overall", f"{risk_profile.overall_score}/10")
    
    st.subheader("Financial Impact")
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Insurance Premium Impact", f"+{risk_profile.insurance_impact_pct:.0f}%")
    col2.metric("FEMA Zone", risk_profile.flood.fema_zone)
    col3.metric("☀️ Solar Potential", f"{risk_profile.solar_potential_kwh:,.0f} kWh/year")
    
    # Calculate solar revenue
    solar_rate = 0.12  # $/kWh
    solar_annual = risk_profile.solar_potential_kwh * solar_rate
    st.success(f"💡 Potential solar revenue: **${solar_annual:,.0f}/year** at ${solar_rate}/kWh")
    
    if risk_profile.fire.wui_zone:
        st.warning("⚠️ Property is in Wildland-Urban Interface zone. Defensible space requirements apply.")
    
    if risk_profile.flood.factor >= 5:
        st.warning(f"⚠️ Elevated flood risk. Consider flood insurance (FEMA Zone {risk_profile.flood.fema_zone}).")
