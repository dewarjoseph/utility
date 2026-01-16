"""
Deal Room

Capital formation and investor management for cooperative projects.
"""

import streamlit as st
from core.theme import get_page_config, inject_theme

st.set_page_config(**get_page_config("Deals"))
inject_theme()

from core.deal_room import (
    DealRoom, CapitalStackBuilder, Deal, InvestmentType, 
    InvestorStatus, DealStatus, PropertyDetails, get_deal_room
)

st.title("Deal Room")
st.caption("Capital formation and investor management for Real Estate Investment Cooperatives.")

# Initialize session state
if 'deal_room' not in st.session_state:
    st.session_state.deal_room = DealRoom()
    # Add sample deal
    deal = st.session_state.deal_room.create_deal(
        "Pacific Avenue Co-op",
        "Mixed-use cooperative with ground floor retail and 12 residential units.",
        "450 Pacific Ave, Santa Cruz, CA"
    )
    deal.status = DealStatus.FUNDRAISING
    deal.financials.acquisition_cost = 2500000
    deal.financials.renovation_cost = 800000
    deal.financials.soft_costs = 200000
    deal.financials.calculate_totals()
    deal.financials.equity_required = 700000
    deal.financials.debt_amount = 2450000
    deal.financials.projected_noi = 280000
    deal.cooperative_name = "Santa Cruz Community Housing Cooperative"
    deal.target_members = 15
    
    # Add sample investors
    st.session_state.deal_room.add_commitment(
        deal.id, "Alice Johnson", "alice@example.com", 50000, InvestmentType.REVENUE_SHARE
    )
    st.session_state.deal_room.update_commitment_status(
        deal.id, deal.commitments[0].id, InvestorStatus.COMMITTED
    )
    st.session_state.deal_room.add_commitment(
        deal.id, "Bob Smith", "bob@example.com", 25000, InvestmentType.REVENUE_SHARE
    )
    st.session_state.deal_room.update_commitment_status(
        deal.id, deal.commitments[1].id, InvestorStatus.FUNDED
    )
    st.session_state.deal_room.add_commitment(
        deal.id, "Carol Davis", "carol@example.com", 35000, InvestmentType.EQUITY
    )

room = st.session_state.deal_room

# Tabs
tab_deals, tab_capital, tab_investors = st.tabs([
    "Active Deals", "Capital Stack", "Investor Ledger"
])

with tab_deals:
    st.header("Active Deals")
    
    if room.deals:
        for deal_id, deal in room.deals.items():
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    st.subheader(deal.name)
                    st.caption(deal.description)
                    if deal.property_details:
                        st.write(f"📍 {deal.property_details.address}")
                
                with col2:
                    st.metric("Target Raise", f"${deal.financials.equity_required:,.0f}")
                
                with col3:
                    st.metric("Raised", f"${deal.total_raised:,.0f}")
                
                with col4:
                    st.metric("Progress", f"{deal.funding_progress:.0f}%")
                
                # Progress bar
                st.progress(min(deal.funding_progress / 100, 1.0))
                
                with st.expander("Deal Details"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Financials")
                        st.metric("Acquisition", f"${deal.financials.acquisition_cost:,.0f}")
                        st.metric("Renovation", f"${deal.financials.renovation_cost:,.0f}")
                        st.metric("Total Project Cost", f"${deal.financials.total_project_cost:,.0f}")
                        st.metric("Projected NOI", f"${deal.financials.projected_noi:,.0f}")
                        
                        if deal.financials.total_project_cost > 0:
                            yoc = deal.financials.projected_noi / deal.financials.total_project_cost
                            st.metric("Yield on Cost", f"{yoc*100:.1f}%")
                    
                    with col2:
                        st.subheader("Cooperative")
                        st.write(f"**Name:** {deal.cooperative_name}")
                        st.write(f"**Target Members:** {deal.target_members}")
                        st.write(f"**Status:** {deal.status.value.replace('_', ' ').title()}")
                        st.write(f"**Investors:** {deal.investor_count}")
                
                st.divider()
    else:
        st.info("No active deals. Create one to get started.")
    
    st.divider()
    st.subheader("Create New Deal")
    
    with st.form("new_deal"):
        col1, col2 = st.columns(2)
        
        with col1:
            deal_name = st.text_input("Project Name")
            deal_address = st.text_input("Property Address")
        
        with col2:
            deal_desc = st.text_area("Description", height=100)
        
        if st.form_submit_button("Create Deal"):
            if deal_name:
                new_deal = room.create_deal(deal_name, deal_desc, deal_address)
                st.success(f"Created deal: {deal_name}")
                st.rerun()
            else:
                st.error("Please enter a project name.")

with tab_capital:
    st.header("Capital Stack Builder")
    st.caption("Build the capital structure for your project.")
    
    # Select deal
    deal_options = list(room.deals.values())
    if deal_options:
        selected_deal = st.selectbox(
            "Select Deal",
            deal_options,
            format_func=lambda d: d.name
        )
        
        if selected_deal:
            total_cost = selected_deal.financials.total_project_cost or 1000000
            
            st.subheader("Build Capital Stack")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Senior Debt**")
                debt_amount = st.number_input(
                    "Loan Amount",
                    value=int(total_cost * 0.65),
                    min_value=0,
                    step=10000
                )
                debt_rate = st.slider("Interest Rate (%)", 5.0, 10.0, 6.5, 0.25) / 100
            
            with col2:
                st.write("**Community Investment**")
                rev_share_amount = st.number_input(
                    "Revenue Share Amount",
                    value=int(total_cost * 0.20),
                    min_value=0,
                    step=5000
                )
                rev_share_pct = st.slider("Revenue Share (%)", 3, 10, 5) / 100
                repay_multiple = st.slider("Repayment Multiple", 1.2, 2.0, 1.5, 0.1)
            
            member_equity = total_cost - debt_amount - rev_share_amount
            
            st.divider()
            st.subheader("Stack Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Senior Debt", f"${debt_amount:,.0f}", f"{debt_amount/total_cost*100:.0f}%")
            col2.metric("Revenue Share", f"${rev_share_amount:,.0f}", f"{rev_share_amount/total_cost*100:.0f}%")
            col3.metric("Member Equity", f"${member_equity:,.0f}", f"{member_equity/total_cost*100:.0f}%")
            col4.metric("Total", f"${total_cost:,.0f}")
            
            if member_equity < 0:
                st.error("Capital stack exceeds project cost.")
            
            if st.button("Apply to Deal"):
                builder = CapitalStackBuilder(total_cost)
                builder.add_senior_debt(debt_amount, debt_rate)
                builder.add_revenue_share(rev_share_amount, rev_share_pct, repay_multiple)
                if member_equity > 0:
                    builder.add_member_equity(member_equity)
                
                selected_deal.capital_stack = builder.build()
                selected_deal.financials.debt_amount = debt_amount
                selected_deal.financials.equity_required = rev_share_amount + max(0, member_equity)
                st.success("Capital stack applied to deal.")
    else:
        st.info("Create a deal first to build a capital stack.")

with tab_investors:
    st.header("Investor Ledger")
    st.caption("Track investor commitments and funding status.")
    
    deal_options = list(room.deals.values())
    if deal_options:
        selected_deal = st.selectbox(
            "Select Deal",
            deal_options,
            format_func=lambda d: d.name,
            key="investor_deal"
        )
        
        if selected_deal and selected_deal.commitments:
            # Summary metrics
            total_committed = sum(
                c.amount for c in selected_deal.commitments 
                if c.status in [InvestorStatus.COMMITTED, InvestorStatus.FUNDED]
            )
            total_funded = sum(
                c.amount for c in selected_deal.commitments 
                if c.status == InvestorStatus.FUNDED
            )
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Committed", f"${total_committed:,.0f}")
            col2.metric("Total Funded", f"${total_funded:,.0f}")
            col3.metric("Investors", len(selected_deal.commitments))
            
            st.divider()
            
            # Investor list
            for commitment in selected_deal.commitments:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        st.write(f"**{commitment.investor_name}**")
                        st.caption(commitment.investor_email)
                    
                    with col2:
                        st.metric("Amount", f"${commitment.amount:,.0f}")
                    
                    with col3:
                        st.write(commitment.investment_type.value.replace("_", " ").title())
                    
                    with col4:
                        status_colors = {
                            InvestorStatus.INTERESTED: "🟡",
                            InvestorStatus.COMMITTED: "🟢",
                            InvestorStatus.FUNDED: "✅",
                            InvestorStatus.WITHDRAWN: "🔴",
                        }
                        st.write(f"{status_colors.get(commitment.status, '')} {commitment.status.value.title()}")
                
                st.divider()
        
        st.subheader("Add Investor")
        
        with st.form("add_investor"):
            col1, col2 = st.columns(2)
            
            with col1:
                inv_name = st.text_input("Investor Name")
                inv_email = st.text_input("Email")
            
            with col2:
                inv_amount = st.number_input("Amount ($)", min_value=1000, value=10000, step=1000)
                inv_type = st.selectbox(
                    "Investment Type",
                    [InvestmentType.REVENUE_SHARE, InvestmentType.EQUITY],
                    format_func=lambda t: t.value.replace("_", " ").title()
                )
            
            if st.form_submit_button("Add Commitment"):
                if inv_name and inv_email:
                    room.add_commitment(
                        selected_deal.id, inv_name, inv_email, inv_amount, inv_type
                    )
                    st.success(f"Added commitment from {inv_name}")
                    st.rerun()
                else:
                    st.error("Please fill in all fields.")
    else:
        st.info("Create a deal first to manage investors.")
