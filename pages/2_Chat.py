"""
Gross Utility Chat Interface

Conversational interface for natural language project creation and analysis.
"""

import streamlit as st

st.set_page_config(
    page_title="Chat - Gross Utility",
    page_icon="💬",
    layout="wide"
)

# Hide Streamlit chrome
st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
    .block-container { padding: 1rem 2rem; }
    .chat-message { padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; }
    .user-message { background-color: #e3f2fd; }
    .assistant-message { background-color: #f5f5f5; }
</style>
""", unsafe_allow_html=True)

from core.chat import ChatSession, Intent
from core.project import ProjectManager
from loaders.geocoder import get_geocoder

# Initialize session state
if 'chat_session' not in st.session_state:
    st.session_state.chat_session = ChatSession()
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

st.title("💬 Gross Utility Chat")
st.markdown("*Tell me what you want to build, and I'll help you analyze it.*")

# Display chat history
for msg in st.session_state.chat_messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])
        
        # Render dynamic components if present
        if msg.get('component') == 'ProjectCreationCard' and msg.get('data'):
            data = msg['data']
            with st.expander("📋 Project Details", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Location:** {data.get('address', 'N/A')}")
                    st.write(f"**Name:** {data.get('project_name', 'Untitled')}")
                with col2:
                    st.write(f"**Use Case:** {data.get('use_case', 'General')}")
                    st.write(f"**Radius:** {data.get('radius_km', 2.0)} km")
                
                if st.button("✅ Create Project", key=f"create_{len(st.session_state.chat_messages)}"):
                    # Create the project
                    pm = ProjectManager()
                    geocoder = get_geocoder()
                    
                    # Geocode the address
                    result = geocoder.geocode(data.get('address', ''))
                    if result:
                        project = pm.create_project(
                            name=data.get('project_name', 'Untitled'),
                            center_lat=result.latitude,
                            center_lon=result.longitude,
                            radius_km=data.get('radius_km', 2.0),
                            description=f"Created via chat. Use case: {data.get('use_case', 'general')}"
                        )
                        st.success(f"✅ Created project: {project.name}")
                        st.balloons()
                    else:
                        st.error("Could not geocode the address. Please try a different format.")

        elif msg.get('component') == 'ZoningMapCard' and msg.get('data'):
            from loaders.zoning import get_zoning_loader
            from loaders.geocoder import get_geocoder
            
            address = msg['data'].get('address')
            if address:
                geocoder = get_geocoder()
                result = geocoder.geocode(address)
                if result:
                    loader = get_zoning_loader()
                    zoning = loader.get_zoning(result.latitude, result.longitude, 10000)
                    
                    with st.expander("🏗️ Zoning Information", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Zone", zoning.zone_name)
                            st.metric("Max Height", f"{zoning.constraints.max_height_ft} ft")
                        with col2:
                            st.metric("Max FAR", f"{zoning.constraints.max_far}")
                            st.metric("Lot Coverage", f"{zoning.constraints.max_lot_coverage*100:.0f}%")
                        
                        st.write("**Allowed Uses:**")
                        for use in zoning.allowed_uses:
                            st.write(f"  • {use}")

        elif msg.get('component') == 'ProFormaWidget':
            from core.proforma import ProFormaEngine
            
            with st.expander("💰 Pro Forma Calculator", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    lot_size = st.number_input("Lot Size (sqft)", value=10000, min_value=1000)
                    far = st.number_input("FAR", value=1.5, min_value=0.1, max_value=5.0)
                with col2:
                    cost_per_sqft = st.number_input("Cost/sqft", value=250, min_value=100)
                
                if st.button("Calculate", key="calc_proforma"):
                    engine = ProFormaEngine()
                    result = engine.quick_estimate(lot_size, far, cost_per_sqft)
                    
                    st.write("### Results")
                    cols = st.columns(3)
                    cols[0].metric("Est. Cost", f"${result['estimated_cost']:,.0f}")
                    cols[1].metric("Est. Value", f"${result['estimated_value']:,.0f}")
                    cols[2].metric("Est. Profit", f"${result['estimated_profit']:,.0f}")

# Chat input
if prompt := st.chat_input("Tell me about your project..."):
    # Add user message
    st.session_state.chat_messages.append({'role': 'user', 'content': prompt})
    
    # Process with chat session
    session = st.session_state.chat_session
    response = session.process_message(prompt)
    
    # Add assistant response
    st.session_state.chat_messages.append({
        'role': 'assistant',
        'content': response.content,
        'component': response.component,
        'data': response.component_data
    })
    
    st.rerun()

# Sidebar with quick actions
with st.sidebar:
    st.markdown("### Quick Actions")
    
    if st.button("🆕 New Conversation"):
        st.session_state.chat_session = ChatSession()
        st.session_state.chat_messages = []
        st.rerun()
    
    if st.button("📁 View Projects"):
        st.switch_page("app.py")
    
    st.markdown("---")
    st.markdown("### Examples")
    st.markdown("""
    Try saying:
    - *"Analyze a lot on Pacific Ave for a food co-op"*
    - *"What's the zoning for 123 Main Street?"*
    - *"Calculate a pro forma for a 15000 sqft building"*
    """)
