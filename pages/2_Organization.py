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

# Initialize Managers
gm = GovernanceManager()
pm = ProjectManager()

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
tab_inc, tab_gov, tab_agent = st.tabs(["📝 Incorporation Studio", "🗳️ Command Center", "🤖 Agent Operations"])

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

        # Member Management (Simple for now)
        with st.expander("Member Management"):
            new_member = st.text_input("Add Member ID/Name")
            if st.button("Add Member"):
                active_org.voting_engine.add_member(new_member)
                gm.save_organization(active_org)
                st.success(f"Added member {new_member}")

            st.write(f"Total Members: {len(active_org.voting_engine.members)}")

        st.divider()

        # Proposals
        col_list, col_create = st.columns([2, 1])

        with col_create:
            st.subheader("New Proposal")
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

            for p in draft_props:
                with st.container(border=True):
                    st.write(f"📝 **DRAFT: {p.title}**")
                    st.caption(p.description)
                    if st.button("🚀 Launch Vote", key=f"launch_{p.id}"):
                        active_org.voting_engine.activate_proposal(p.id)
                        gm.save_organization(active_org)
                        st.rerun()

            for p in active_props:
                with st.container(border=True):
                    st.write(f"🗳️ **{p.title}**")
                    st.caption(p.description)

                    # Voting Interface
                    voter_id = st.selectbox("Vote as Member", options=list(active_org.voting_engine.members.keys()), key=f"voter_{p.id}")

                    if voter_id:
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
                            else:
                                st.error("Insufficient credits or invalid vote.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: AGENT OPERATIONS
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

            # Logic: Must have collected points and average score >= threshold
            # OR just show all for demo purposes if no stats yet
            if proj.points_collected > 0 and avg_score >= threshold:
                high_value_projects.append(proj)
            elif proj.points_collected > 0:
                pass # Skip low value projects
            else:
                # Include new projects that haven't been scanned yet so user can see them
                high_value_projects.append(proj)

        if not high_value_projects:
            st.info("No land projects found.")
        else:
            for proj in high_value_projects:
                with st.expander(f"📍 {proj.name} ({proj.status})"):
                    st.write(proj.description)
                    st.caption(f"ID: {proj.id}")

                    # Agent Action: Auto-Draft Proposal
                    if st.button("🤖 Draft Lobbying Proposal", key=f"agent_{proj.id}"):
                        title = f"Lobbying Campaign: {proj.name}"
                        desc = (
                            f"Proposal to allocate resources to lobby for the development of {proj.name}. "
                            f"Targeting sustainable development in accordance with our mission: {active_org.name}. "
                            f"Project ID: {proj.id}"
                        )
                        options = ["Approve Funding", "Reject", "Request More Info"]

                        prop = active_org.voting_engine.create_proposal(
                            proposal_id=f"lobby_{proj.id[:8]}",
                            title=title,
                            description=desc,
                            options=options
                        )
                        gm.save_organization(active_org)
                        st.success(f"Agent drafted proposal: {title}")
                        st.rerun()
