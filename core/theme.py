"""
Shared theme and styling for all pages.

Provides consistent CSS, color palette, and helper functions.
"""

# Color palette - professional, not generic
COLORS = {
    'primary': '#2563eb',      # Deep blue
    'secondary': '#64748b',    # Slate gray
    'accent': '#0891b2',       # Teal
    'success': '#059669',      # Emerald
    'warning': '#d97706',      # Amber
    'danger': '#dc2626',       # Red
    'background': '#f8fafc',   # Light slate
    'surface': '#ffffff',
    'text': '#1e293b',
    'muted': '#64748b',
}

# Shared CSS for all pages
SHARED_CSS = """
<style>
    /* Hide Streamlit chrome */
    #MainMenu, header, footer, .stDeployButton {
        visibility: hidden; 
        display: none;
    }
    
    /* Page layout */
    .block-container { 
        padding: 1.5rem 2rem; 
        max-width: 1200px;
    }
    
    /* Typography */
    h1 { 
        font-weight: 600; 
        color: #1e293b;
        letter-spacing: -0.025em;
    }
    h2 { 
        font-weight: 500; 
        color: #334155;
        margin-top: 1.5rem;
    }
    h3 { 
        font-weight: 500; 
        color: #475569;
    }
    
    /* Cards and containers */
    .stExpander {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    
    /* Buttons */
    .stButton > button {
        font-weight: 500;
        border-radius: 6px;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-weight: 600;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 500;
    }
    
    /* Remove italic from descriptions */
    .element-container p em {
        font-style: normal;
        color: #64748b;
    }
</style>
"""

def get_page_config(title: str):
    """Get consistent page configuration."""
    return {
        'page_title': f"{title} | Land Utility Engine",
        'page_icon': "🏗️",
        'layout': "wide",
    }

def inject_theme():
    """Inject shared CSS into the page."""
    import streamlit as st
    st.markdown(SHARED_CSS, unsafe_allow_html=True)

def section_header(title: str, description: str = None):
    """Render a consistent section header."""
    import streamlit as st
    st.header(title)
    if description:
        st.caption(description)
