"""
Organization & Governance Dashboard

Manage your non-profit organizations, generate legal documents, and govern through democratic voting.
"""

import streamlit as st
import json
from datetime import datetime
from core.bylaws import (
    EntityType, BylawsConfig, get_bylaws_generator, get_filing_generator,
    BoardElection, VotingStructure, SurplusDistribution
)
from core.governance import GovernanceManager, ProposalStatus
from core.project import ProjectManager, ProjectStatus
from core.deal_room import get_deal_room, DealStatus, InvestmentType, InvestorStatus
from core.revenue_share import get_revenue_ledger
from core.sensitivity import get_sensitivity_analyzer

# Initialize Managers
gm = GovernanceManager()
pm = ProjectManager()

# Session State Persistence for Demo (In real app, these would be databases)
if 'deal_room' not in st.session_state:
    st.session_state.deal_room = get_deal_room()
if 'revenue_ledger' not in st.session_state:
    st.session_state.revenue_ledger = get_revenue_ledger()

deal_room = st.session_state.deal_room
ledger = st.session_state.revenue_ledger

st.set_page_config(
    page_title="Organization Manager",
    page_icon="🏛️",
    layout="wide"
)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
st.sidebar.title("🏛️ Organization")

# Select Active Organization
orgs = gm.list_organizations()
selected_org_id = st.sidebar.selectbox(
    "Select Organization",
    options=[o.id for o in orgs],
    format_func=lambda x: next((o.name for o in orgs if o.id == x), x)
)

active_org = gm.get_organization(selected_org_id) if selected_org_id else None

if active_org:
    st.sidebar.info(f"**Active:** {active_org.name}\n\nType: {active_org.type}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Agent Status")
if active_org:
    st.sidebar.success("Agent Active")
else:
    st.sidebar.warning("No Organization Selected")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ═══════════════════════════════════════════════════════════════════════════
tab_inc, tab_gov, tab_deals, tab_treasury, tab_agent = st.tabs([
    "📝 Incorporation", "🗳️ Governance", "🤝 Deal Room", "💰 Treasury", "🤖 Agent"
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: INCORPORATION STUDIO
# ═══════════════════════════════════════════════════════════════════════════
with tab_inc:
    st.header("📝 Incorporation Studio")
    st.markdown("Draft legal documents and form your organization.")

    with st.expander("Create New Organization", expanded=not active_org):
        with st.form("create_org_form"):
            col1, col2 = st.columns(2)
            with col1:
                org_name = st.text_input("Organization Name", placeholder="e.g. Community Land Trust")
                org_type = st.selectbox(
                    "Entity Type",
                    options=[e for e in EntityType],
                    format_func=lambda x: x.value
                )
                state = st.text_input("State of Incorporation", value="Delaware")

            with col2:
                purpose = st.text_area("Mission / Purpose", placeholder="Describe the charitable or social welfare purpose...")
                board_size = st.number_input("Initial Board Size", min_value=3, value=5)

            st.subheader("Incorporator Details")
            inc_name = st.text_input("Incorporator Name")
            inc_addr = st.text_input("Incorporator Address")

            submitted = st.form_submit_button("Generate Documents & Form Organization")

            if submitted:
                if not org_name or not purpose:
                    st.error("Name and Purpose are required.")
                else:
                    # 1. Create Organization in System
                    new_org = gm.create_organization(org_name, org_type.value)

                    # 2. Generate Documents
                    config = BylawsConfig(
                        cooperative_name=org_name,
                        entity_type=org_type,
                        state=state,
                        purpose=purpose,
                        board_size=board_size,
                        incorporator_name=inc_name,
                        incorporator_address=inc_addr
                    )

                    bg = get_bylaws_generator()
                    fg = get_filing_generator()

                    bylaws = bg.generate(config)
                    filing = fg.generate(config)

                    # Store generated docs in session state for download
                    st.session_state['generated_bylaws'] = bylaws.to_markdown()
                    st.session_state['generated_filing'] = filing

                    st.success(f"Organization '{org_name}' created successfully!")
                    st.rerun()

    # Display Generated Documents (if just created or selected)
    if 'generated_bylaws' in st.session_state:
        st.divider()
        st.subheader("📄 Generated Documents")

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "📥 Download Bylaws (Markdown)",
                data=st.session_state['generated_bylaws'],
                file_name="bylaws.md",
                mime="text/markdown"
            )
            with st.expander("Preview Bylaws"):
                st.markdown(st.session_state['generated_bylaws'])

        with col2:
            filing_packet = st.session_state.get('generated_filing')
            if filing_packet:
                st.download_button(
                    "📥 Download Articles of Inc.",
                    data=filing_packet.articles_of_incorporation,
                    file_name="articles.md",
                    mime="text/markdown"
                )

                json_data = json.dumps(filing_packet.filing_data, indent=2)
                st.download_button(
                    "📥 Download Filing Data (JSON)",
                    data=json_data,
                    file_name="filing_data.json",
                    mime="application/json"
                )

                with st.expander("Filing Instructions"):
                    st.markdown(filing_packet.instructions)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: COMMAND CENTER (GOVERNANCE)
# ═══════════════════════════════════════════════════════════════════════════
with tab_gov:
    if not active_org:
        st.info("Please select or create an organization first.")
    else:
        st.header(f"🗳️ Governance: {active_org.name}")

        # Member Management
        with st.expander("Member Management", expanded=False):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader("Add Member")
                new_member = st.text_input("Member ID/Name")
                member_class = st.selectbox("Class", options=["General Member", "Founder", "Investor"])
                if st.button("Add Member"):
                    active_org.voting_engine.add_member(new_member, verified=False)
                    # Add to ledger too
                    ledger.add_member(new_member, new_member)
                    gm.save_organization(active_org)
                    st.success(f"Added {new_member}")
                    st.rerun()

            with col2:
                st.subheader("Verify Members")
                st.caption("Only verified members can cast votes.")

                # List members
                members = active_org.voting_engine.members
                if not members:
                    st.info("No members yet.")
                else:
                    for m_id, is_ver in members.items():
                        c1, c2, c3 = st.columns([2, 1, 1])
                        c1.write(f"👤 {m_id}")
                        c2.caption("Verified" if is_ver else "Unverified")
                        if c3.button("Toggle", key=f"tog_{m_id}"):
                            active_org.voting_engine.add_member(m_id, verified=not is_ver)
                            gm.save_organization(active_org)
                            st.rerun()

        st.divider()

        # Lobbying Ledger (Phase 2)
        with st.expander("Lobbying Ledger (501c4 Compliance)"):
            if "ledger_entries" not in st.session_state:
                st.session_state.ledger_entries = []

            col1, col2 = st.columns(2)
            with col1:
                l_prop = st.selectbox("Related Proposal", options=[p.title for p in active_org.voting_engine.proposals.values()])
                l_hours = st.number_input("Hours Spent", min_value=0.0, step=0.5)
                l_cost = st.number_input("Direct Cost ($)", min_value=0.0, step=10.0)
                l_desc = st.text_input("Activity Description")

                if st.button("Log Activity"):
                    entry = {
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "proposal": l_prop,
                        "hours": l_hours,
                        "cost": l_cost,
                        "desc": l_desc
                    }
                    st.session_state.ledger_entries.append(entry)
                    st.success("Logged!")

            with col2:
                if st.session_state.ledger_entries:
                    st.dataframe(st.session_state.ledger_entries)
                    total_hours = sum(x['hours'] for x in st.session_state.ledger_entries)
                    total_cost = sum(x['cost'] for x in st.session_state.ledger_entries)
                    st.metric("Total Hours", f"{total_hours:.1f}")
                    st.metric("Total Cost", f"${total_cost:,.2f}")

        st.divider()

        # Proposals
        col_list, col_create = st.columns([2, 1])

        with col_create:
            st.subheader("New Generic Proposal")
            with st.form("new_proposal"):
                title = st.text_input("Title")
                desc = st.text_area("Description")
                options_str = st.text_area("Options (one per line)", value="Yes\nNo")

                if st.form_submit_button("Draft Proposal"):
                    options = [o.strip() for o in options_str.split('\n') if o.strip()]
                    prop = active_org.voting_engine.create_proposal(
                        proposal_id=f"prop_{len(active_org.voting_engine.proposals)+1}",
                        title=title,
                        description=desc,
                        options=options
                    )
                    gm.save_organization(active_org)
                    st.success("Proposal created!")
                    st.rerun()

        with col_list:
            st.subheader("Active Proposals")
            proposals = active_org.voting_engine.proposals.values()
            active_props = [p for p in proposals if p.status == ProposalStatus.ACTIVE]
            draft_props = [p for p in proposals if p.status == ProposalStatus.DRAFT]

            if not active_props and not draft_props:
                st.info("No active proposals.")

            # Drafts
            if draft_props:
                st.caption("Drafts")
                for p in draft_props:
                    with st.container(border=True):
                        st.write(f"📝 **DRAFT: {p.title}**")
                        st.caption(p.description)

                        # Show financial snapshot if available (from auto-generation)
                        if p.financial_summary:
                            fin = p.financial_summary
                            c1, c2 = st.columns(2)
                            c1.metric("Est. Cost", f"${fin.get('total_development_cost', 0):,.0f}")
                            c2.metric("ROI", f"{fin.get('yield_on_cost', 0)*100:.1f}%")

                        if st.button("🚀 Launch Vote", key=f"launch_{p.id}"):
                            active_org.voting_engine.activate_proposal(p.id)
                            gm.save_organization(active_org)
                            st.rerun()

            # Active
            if active_props:
                st.caption("Voting Active")
                for p in active_props:
                    with st.container(border=True):
                        st.write(f"🗳️ **{p.title}**")
                        st.caption(p.description)

                        # Show Community Impact
                        if p.community_benefit_score:
                            st.progress(p.community_benefit_score/10.0, text=f"Community Impact Score: {p.community_benefit_score:.1f}/10")

                        # Sensitivity Analysis (Phase 3)
                        if p.financial_summary:
                            with st.expander("📉 Stress Test (Sensitivity Analysis)"):
                                sa = get_sensitivity_analyzer()
                                # Adapt dict to flat inputs
                                base_inputs = {
                                    "interest_rate": 0.05,
                                    "loan_amount": p.financial_summary.get('total_development_cost', 0) * 0.7,
                                    "noi": p.financial_summary.get('net_operating_income', 0),
                                    "construction_cost": p.financial_summary.get('total_development_cost', 0),
                                    "gross_income": p.financial_summary.get('gross_potential_income', 0)
                                }
                                scenarios = sa.generate_scenario_matrix(base_inputs)

                                # Show top 3 risks
                                for s in scenarios[:3]:
                                    st.markdown(f"**{s.scenario.name}**")
                                    st.caption(s.recommendation)
                                    color = "red" if s.impact_pct < 0 else "green"
                                    st.markdown(f":{color}[Impact: {s.impact_pct:+.1f}%]")

                        # Voting Interface
                        voter_id = st.selectbox("Vote as Member", options=list(active_org.voting_engine.members.keys()), key=f"voter_{p.id}")

                        if voter_id:
                            # Check verification
                            if not active_org.voting_engine.members.get(voter_id):
                                st.error("⚠️ Member not verified. Contact admin.")
                            else:
                                alloc = active_org.voting_engine.get_voter_allocation(p.id, voter_id)
                                st.write(f"Credits Remaining: {alloc.credits_remaining}")

                                votes = {}
                                total_cost = 0
                                for opt in p.options:
                                    v = st.number_input(f"Votes for '{opt}'", min_value=0, max_value=10, key=f"v_{p.id}_{opt}")
                                    votes[opt] = v
                                    total_cost += v*v

                                st.write(f"Total Cost: {total_cost}")

                                if st.button("Cast Vote", key=f"cast_{p.id}"):
                                    if active_org.voting_engine.cast_vote(p.id, voter_id, votes):
                                        gm.save_organization(active_org)
                                        st.success("Vote cast!")
                                        st.rerun()
                                    else:
                                        st.error("Insufficient credits.")

                        # Close Vote (If Admin)
                        if st.button("End Voting & Tally", key=f"close_{p.id}"):
                            result = active_org.voting_engine.close_proposal(p.id)
                            gm.save_organization(active_org)
                            st.success(f"Vote Closed! Winner: {result.winner}")

                            # Auto-create Deal if passed (Phase 3)
                            if result.passed and result.winner == "Approve" and p.project_id:
                                deal = deal_room.create_deal(
                                    name=p.title,
                                    description=p.description
                                )
                                # Copy financials
                                if p.financial_summary:
                                    deal.financials.total_project_cost = p.financial_summary.get('total_development_cost', 0)
                                    deal.financials.equity_required = deal.financials.total_project_cost * 0.3 # Assume 30% equity
                                st.info("🎉 Deal created in Deal Room!")
                            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: DEAL ROOM (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════
with tab_deals:
    st.header("🤝 Deal Room")
    st.markdown("Manage active investments and capital formation.")

    deals = deal_room.get_all_deals()
    if not deals:
        st.info("No active deals. Pass a proposal to create a deal.")
    else:
        for deal_data in deals:
            deal_id = deal_data['id']
            deal = deal_room.deals[deal_id]

            with st.expander(f"💼 {deal.name} ({deal.status.value})"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Equity Goal", f"${deal.financials.equity_required:,.0f}")
                c2.metric("Raised", f"${deal.total_raised:,.0f}")
                c3.progress(deal.funding_progress / 100, text=f"{deal.funding_progress:.1f}% Funded")

                # Investor List
                st.subheader("Investors")
                if deal.commitments:
                    for c in deal.commitments:
                        st.text(f"{c.investor_name}: ${c.amount:,.0f} ({c.status.value})")
                else:
                    st.caption("No investors yet.")

                # Add Commitment
                with st.form(f"invest_{deal_id}"):
                    inv_name = st.text_input("Investor Name")
                    inv_amt = st.number_input("Amount", min_value=1000.0)
                    if st.form_submit_button("Record Commitment"):
                        deal_room.add_commitment(deal_id, inv_name, "test@example.com", inv_amt)
                        st.success("Commitment added!")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: TREASURY (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════
with tab_treasury:
    st.header("💰 Treasury & Dividends")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Member Accounts")
        members = ledger.members.values()
        if not members:
            st.info("No member accounts found.")
        else:
            data = [m.to_dict() for m in members]
            st.dataframe(data)

    with col2:
        st.subheader("Actions")

        # Record Revenue
        with st.form("rev_form"):
            rev_amt = st.number_input("Record Incoming Revenue ($)", min_value=0.0)
            if st.form_submit_button("Process Revenue"):
                payments = ledger.process_revenue(rev_amt)
                st.success(f"Processed! Payments: {payments}")
                st.rerun()

        # Distribute Dividends
        with st.form("div_form"):
            surplus = st.number_input("Declare Surplus ($)", min_value=0.0)
            if st.form_submit_button("Distribute Patronage"):
                # Simple patronage: equal share for now
                patronage = {m_id: 1.0 for m_id in ledger.members}
                divs = ledger.calculate_patronage_dividends(surplus, patronage)
                st.success(f"Distributed: {divs}")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5: AGENT OPERATIONS (Existing)
# ═══════════════════════════════════════════════════════════════════════════
with tab_agent:
    if not active_org:
        st.info("Select an organization to enable agent operations.")
    else:
        st.header("🤖 Agent Operations")
        st.markdown(f"Automated monitoring for **{active_org.name}**.")

        st.subheader("Land Project Scanner")

        # Get High Value Projects
        projects = pm.list_projects()
        high_value_projects = []

        for proj in projects:
            # Check if project has collected data and meets high-value threshold
            avg_score = proj.stats.get('average_score', 0)
            threshold = proj.settings.high_value_threshold

            if proj.points_collected > 0 and avg_score >= threshold:
                high_value_projects.append(proj)
            elif proj.points_collected > 0:
                pass
            else:
                high_value_projects.append(proj)

        if not high_value_projects:
            st.info("No land projects found.")
        else:
            for proj in high_value_projects:
                with st.expander(f"📍 {proj.name} ({proj.status})"):
                    st.write(proj.description)
                    st.caption(f"ID: {proj.id}")

                    if st.button("🤖 Draft Lobbying Proposal", key=f"agent_{proj.id}"):
                        title = f"Lobbying Campaign: {proj.name}"
                        desc = f"Proposal for {proj.name}. Mission aligned."
                        options = ["Approve Funding", "Reject"]

                        prop = active_org.voting_engine.create_proposal(
                            proposal_id=f"lobby_{proj.id[:8]}",
                            title=title,
                            description=desc,
                            options=options,
                            project_id=proj.id
                        )
                        gm.save_organization(active_org)
                        st.success(f"Agent drafted proposal: {title}")
                        st.rerun()
