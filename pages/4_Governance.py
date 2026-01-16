"""
Governance

Democratic decision-making, bylaws generation, and member management.
"""

import streamlit as st
from core.theme import get_page_config, inject_theme

st.set_page_config(**get_page_config("Governance"))
inject_theme()

from core.governance import QuadraticVotingEngine, ProposalStatus
from core.bylaws import BylawsGenerator, BylawsConfig, EntityType, VotingStructure, BoardElection, SurplusDistribution
from core.revenue_share import RevenueShareLedger

st.title("Cooperative Governance")
st.caption("Democratic decision-making and member management for your cooperative.")

# Initialize session state
if 'voting_engine' not in st.session_state:
    st.session_state.voting_engine = QuadraticVotingEngine()
    for i in range(1, 6):
        st.session_state.voting_engine.add_member(f"member_{i}")

if 'ledger' not in st.session_state:
    st.session_state.ledger = RevenueShareLedger()
    st.session_state.ledger.add_member("m1", "Alice Johnson")
    st.session_state.ledger.add_member("m2", "Bob Smith")
    st.session_state.ledger.add_member("m3", "Carol Davis")
    st.session_state.ledger.record_contribution("m1", 5000, "Initial investment")
    st.session_state.ledger.record_contribution("m2", 10000, "Initial investment")
    st.session_state.ledger.record_contribution("m3", 7500, "Initial investment")

# Tabs
tab_voting, tab_bylaws, tab_members = st.tabs([
    "Quadratic Voting", "Bylaws Generator", "Member Ledger"
])

with tab_voting:
    st.header("Quadratic Voting")
    st.caption("Vote cost increases quadratically: 1 vote = 1 credit, 2 votes = 4 credits, 3 votes = 9 credits.")
    
    engine = st.session_state.voting_engine
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Create Proposal")
        title = st.text_input("Proposal Title", "Community Garden vs Playground")
        description = st.text_area("Description", "How should we use the common area?")
        options = st.text_input("Options (comma-separated)", "Garden, Playground, Both")
        
        if st.button("Create Proposal", type="primary"):
            opts = [o.strip() for o in options.split(",")]
            proposal = engine.create_proposal(
                f"prop_{len(engine.proposals)}",
                title, description, opts
            )
            engine.activate_proposal(proposal.id)
            st.success(f"Created proposal: {title}")
            st.rerun()
    
    with col2:
        st.subheader("Cast Your Vote")
        
        active_proposals = [p for p in engine.proposals.values() 
                          if p.status == ProposalStatus.ACTIVE]
        
        if active_proposals:
            selected = st.selectbox(
                "Select Proposal",
                active_proposals,
                format_func=lambda p: p.title
            )
            
            if selected:
                st.write(f"**{selected.title}**")
                st.write(selected.description)
                
                voter_id = st.selectbox("Your Member ID", 
                    [f"member_{i}" for i in range(1, 6)])
                
                st.divider()
                st.write("**Allocate your 100 voice credits:**")
                st.caption("Cost = votes squared. More votes = exponentially more credits.")
                
                allocations = {}
                total_cost = 0
                
                for option in selected.options:
                    votes = st.slider(
                        f"Votes for '{option}'",
                        0, 10, 0,
                        key=f"vote_{option}"
                    )
                    if votes > 0:
                        allocations[option] = votes
                        cost = votes * votes
                        total_cost += cost
                        st.caption(f"Cost: {cost} credits")
                
                credits_remaining = 100 - total_cost
                
                if credits_remaining >= 0:
                    st.metric("Credits Remaining", credits_remaining)
                else:
                    st.error(f"Over budget by {-credits_remaining} credits")
                
                if st.button("Submit Vote") and credits_remaining >= 0:
                    success = engine.cast_vote(selected.id, voter_id, allocations)
                    if success:
                        st.success("Vote recorded")
                    else:
                        st.error("Failed to record vote")
                
                st.divider()
                if st.button("Tally Results"):
                    result = engine.tally_votes(selected.id)
                    
                    st.subheader("Results")
                    for opt, votes in result.option_votes.items():
                        st.metric(opt, f"{votes} votes")
                    
                    if result.winner:
                        st.success(f"Winner: {result.winner}")
        else:
            st.info("No active proposals. Create one to start voting.")

with tab_bylaws:
    st.header("Bylaws Generator")
    st.caption("Generate legally-compliant cooperative bylaws based on your governance choices.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        coop_name = st.text_input("Cooperative Name", "Santa Cruz Housing Cooperative")
        entity_type = st.selectbox("Entity Type", list(EntityType), 
            format_func=lambda e: e.value)
        state = st.selectbox("State", ["California", "New York", "Minnesota", "Colorado", "Oregon"])
        purpose = st.text_area("Purpose Statement", 
            "To provide permanently affordable cooperative housing for community members.")
    
    with col2:
        voting = st.selectbox("Voting Structure", list(VotingStructure),
            format_func=lambda v: v.value.replace("_", " ").title())
        board_size = st.number_input("Board Size", 3, 15, 5)
        board_election = st.selectbox("Board Election", list(BoardElection),
            format_func=lambda b: b.value.replace("_", " ").title())
        surplus = st.selectbox("Surplus Distribution", list(SurplusDistribution),
            format_func=lambda s: s.value.replace("_", " ").title())
    
    st.divider()
    st.subheader("Anti-Speculation Provisions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        appreciation_cap = st.checkbox("Cap Appreciation", value=True)
        if appreciation_cap:
            cap_pct = st.slider("Annual Cap %", 1, 5, 3) / 100
        else:
            cap_pct = None
    
    with col2:
        transfer_restrictions = st.checkbox("Transfer Restrictions", value=True)
    
    with col3:
        first_refusal = st.checkbox("Right of First Refusal", value=True)
    
    if st.button("Generate Bylaws", type="primary"):
        config = BylawsConfig(
            cooperative_name=coop_name,
            entity_type=entity_type,
            state=state,
            purpose=purpose,
            voting_structure=voting,
            board_size=board_size,
            board_election=board_election,
            surplus_distribution=surplus,
            appreciation_cap=cap_pct,
            transfer_restrictions=transfer_restrictions,
            right_of_first_refusal=first_refusal,
        )
        
        generator = BylawsGenerator()
        bylaws = generator.generate(config)
        
        st.success("Bylaws generated")
        
        with st.expander("View Generated Bylaws", expanded=True):
            st.markdown(bylaws.to_markdown())
        
        st.download_button(
            "Download as Markdown",
            bylaws.to_markdown(),
            file_name=f"{coop_name.replace(' ', '_')}_bylaws.md",
            mime="text/markdown"
        )

with tab_members:
    st.header("Member Ledger")
    st.caption("Track capital contributions, revenue share agreements, and patronage dividends.")
    
    ledger = st.session_state.ledger
    metrics = ledger.get_community_metrics()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Members", metrics['total_members'])
    col2.metric("Total Capital", f"${metrics['total_capital_raised']:,.0f}")
    col3.metric("Avg Investment", f"${metrics['average_investment']:,.0f}")
    
    st.divider()
    st.subheader("Member Accounts")
    
    for member_id, account in ledger.members.items():
        with st.expander(account.name):
            col1, col2, col3 = st.columns(3)
            col1.metric("Capital Balance", f"${account.capital_balance:,.0f}")
            col2.metric("Patronage Credits", f"${account.patronage_credits:,.0f}")
            col3.metric("Net Position", f"${account.net_position:,.0f}")
            
            if account.transactions:
                st.write("**Recent Transactions:**")
                for txn in account.transactions[-3:]:
                    st.write(f"  - {txn.description}: ${txn.amount:,.0f}")
    
    st.divider()
    st.subheader("Patronage Dividend Simulator")
    
    surplus = st.number_input("Annual Surplus to Distribute ($)", 
        value=10000, min_value=0, step=1000)
    
    if st.button("Calculate Dividends"):
        patronage = {m: 1 for m in ledger.members.keys()}
        dividends = ledger.calculate_patronage_dividends(surplus, patronage)
        
        st.success("Dividends calculated")
        for member_id, amount in dividends.items():
            name = ledger.members[member_id].name
            st.write(f"  - {name}: ${amount:,.0f}")
