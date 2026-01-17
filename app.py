"""
Land Utility Engine - Main Application

Multi-page Streamlit application for managing land utility analysis projects.
"""

import streamlit as st
import os
import threading
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Land Utility Engine",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit chrome
st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
    .block-container { padding: 1rem 2rem; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════
from core.project import ProjectManager, Project, ProjectStatus
from core.job_queue import JobQueue, JobStatus

# Initialize managers
pm = ProjectManager()
queue = JobQueue()

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════
st.sidebar.title("🛰️ Land Utility Engine")
st.sidebar.markdown("---")

# Worker status
active_jobs = queue.get_active_jobs()
if active_jobs:
    st.sidebar.success(f"✅ {len(active_jobs)} active job(s)")
else:
    st.sidebar.info("💤 No active jobs")

# Quick stats
stats = queue.get_queue_stats()
all_projects = pm.list_projects()
st.sidebar.metric("Projects", len(all_projects))

st.sidebar.markdown("---")

# Worker management (Singleton-like in session state)
if "worker_thread" not in st.session_state:
    st.session_state.worker_thread = None

# Worker control
if st.sidebar.button("🔄 Start Worker"):
    if st.session_state.worker_thread is None or not st.session_state.worker_thread.is_alive():
        from core.worker import Worker
        
        def run_worker():
            worker = Worker()
            worker.run()
            
        thread = threading.Thread(target=run_worker, daemon=True)
        thread.start()
        st.session_state.worker_thread = thread
        st.sidebar.success("Worker started (Threaded)!")
    else:
        st.sidebar.info("Worker is already running.")
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ═══════════════════════════════════════════════════════════════════════════
st.title("🛰️ Land Utility Engine")
st.markdown("Analyze land utility potential across any geographic area.")

# Tabs
tab_projects, tab_new, tab_queue = st.tabs(["📁 Projects", "➕ New Project", "📋 Job Queue"])

# ═══════════════════════════════════════════════════════════════════════════
# PROJECTS TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_projects:
    st.header("📁 Your Projects")
    
    projects = pm.list_projects()
    
    if not projects:
        st.info("👋 No projects yet. Create your first project in the 'New Project' tab!")
    else:
        for project in projects:
            with st.expander(f"**{project.name}** ({project.id})", expanded=project.status == ProjectStatus.SCANNING):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.caption(project.description or "No description")
                    st.write(f"📍 Center: ({project.bounds.center_latitude:.4f}, {project.bounds.center_longitude:.4f})")
                    st.write(f"📐 Area: {project.bounds.area_sq_km:.2f} sq km")
                    st.write(f"📊 Points: {project.points_collected}")
                
                with col2:
                    # Status badge
                    if project.status == ProjectStatus.SCANNING:
                        st.success("🔄 Scanning")
                    elif project.status == ProjectStatus.COMPLETED:
                        st.info("✅ Complete")
                    elif project.status == ProjectStatus.QUEUED:
                        st.warning("⏳ Queued")
                    elif project.status == ProjectStatus.ERROR:
                        st.error(f"❌ Error: {project.error_message}")
                    else:
                        st.caption(f"Status: {project.status}")
                
                with col3:
                    # Actions
                    if st.button("🗺️ Open", key=f"open_{project.id}"):
                        st.session_state.selected_project = project.id
                        st.switch_page("pages/1_Dashboard.py")
                    
                    if project.status not in [ProjectStatus.SCANNING, ProjectStatus.QUEUED]:
                        if st.button("▶️ Start Scan", key=f"start_{project.id}"):
                            job_id = queue.enqueue(project.id)
                            project.status = ProjectStatus.QUEUED
                            project.save()
                            st.success(f"Queued as job #{job_id}")
                            st.rerun()
                    
                    if st.button("🗑️ Delete", key=f"delete_{project.id}"):
                        pm.delete_project(project.id)
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# NEW PROJECT TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_new:
    st.header("Create New Project")
    
    # Address search outside form for instant feedback
    st.subheader("Location")
    address_input = st.text_input(
        "Search by address", 
        placeholder="e.g., 123 Pacific Ave, Santa Cruz, CA",
        help="Enter an address and we'll find the coordinates"
    )
    
    # Initialize coordinates in session state
    if "new_proj_lat" not in st.session_state:
        st.session_state.new_proj_lat = 36.9741
        st.session_state.new_proj_lon = -122.0308
        st.session_state.new_proj_address = ""
    
    # Geocode if address provided
    if address_input and address_input != st.session_state.new_proj_address:
        from loaders.geocoder import get_geocoder
        geocoder = get_geocoder()
        result = geocoder.geocode(address_input)
        if result:
            st.session_state.new_proj_lat = result.latitude
            st.session_state.new_proj_lon = result.longitude
            st.session_state.new_proj_address = address_input
            st.success(f"Found: {result.display_name[:80]}...")
        else:
            st.error("Address not found. Try a different format.")
    
    # Show current location
    st.caption(f"Current: ({st.session_state.new_proj_lat:.4f}, {st.session_state.new_proj_lon:.4f})")
    
    with st.form("new_project_form"):
        name = st.text_input("Project Name", placeholder="e.g., Santa Cruz Downtown")
        description = st.text_area("Description (optional)", placeholder="What are you analyzing?")
        
        # Manual coordinate adjustment
        with st.expander("Adjust coordinates manually"):
            col1, col2 = st.columns(2)
            with col1:
                center_lat = st.number_input("Latitude", value=st.session_state.new_proj_lat, format="%.4f")
            with col2:
                center_lon = st.number_input("Longitude", value=st.session_state.new_proj_lon, format="%.4f")
        
        if 'center_lat' not in dir():
            center_lat = st.session_state.new_proj_lat
            center_lon = st.session_state.new_proj_lon
        
        radius_km = st.slider("Analysis radius (km)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
        
        # Use-case profile selector
        st.subheader("Analysis Type")
        use_cases = {
            "general": ("🏭 General Industrial", "Balanced scoring for general industrial development"),
            "desalination_plant": ("🌊 Desalination Plant", "Optimized for coastal water facilities - prioritizes ocean access, power, industrial zoning"),
            "silicon_wafer_fab": ("💎 Silicon Wafer Fab", "Semiconductor manufacturing - prioritizes power, clean water, seismic stability"),
            "warehouse_distribution": ("📦 Warehouse/Distribution", "Logistics centers - prioritizes highway, rail, port access"),
            "light_manufacturing": ("🏭 Light Manufacturing", "General manufacturing - balanced industrial scoring"),
        }
        
        use_case = st.selectbox(
            "What are you analyzing for?",
            options=list(use_cases.keys()),
            format_func=lambda x: use_cases[x][0],
            help="Different use cases have different scoring weights and synergies"
        )
        st.caption(use_cases[use_case][1])
        
        st.subheader("Settings")
        col1, col2 = st.columns(2)
        with col1:
            max_points = st.number_input("Max points to collect", 
                                          value=500, min_value=50, max_value=10000, step=50,
                                          help="More points = better coverage but slower")
        with col2:
            high_value_threshold = st.slider("High value threshold", 
                                              min_value=5.0, max_value=9.0, value=7.0, step=0.5,
                                              help="Score above this is high value")
        
        auto_start = st.checkbox("Start scanning immediately", value=True)
        
        submitted = st.form_submit_button("Create Project", width="stretch")
        
        if submitted:
            if not name:
                st.error("Please enter a project name")
            else:
                # Create project
                project = pm.create_project(
                    name=name,
                    center_lat=center_lat,
                    center_lon=center_lon,
                    radius_km=radius_km,
                    description=description
                )
                
                # Apply settings
                project.settings.max_total_points = max_points
                project.settings.high_value_threshold = high_value_threshold
                project.settings.use_case = use_case  # Save selected use case
                project.save()
                
                st.success(f"✅ Created project: {project.name}")
                
                if auto_start:
                    job_id = queue.enqueue(project.id)
                    project.status = ProjectStatus.QUEUED
                    project.save()
                    st.info(f"📋 Queued as job #{job_id}")
                
                st.balloons()
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# JOB QUEUE TAB
# ═══════════════════════════════════════════════════════════════════════════
with tab_queue:
    st.header("📋 Job Queue")
    
    jobs = queue.get_active_jobs()
    
    if not jobs:
        st.info("No active jobs. Create a project and start scanning!")
    else:
        for job in jobs:
            project = pm.get_project(job.project_id)
            project_name = project.name if project else job.project_id
            
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**Job #{job.id}** - {project_name}")
                    st.progress(job.progress_percent / 100, text=job.progress_message)
                
                with col2:
                    if job.status == JobStatus.RUNNING:
                        st.success("🔄 Running")
                    elif job.status == JobStatus.PENDING:
                        st.warning("⏳ Pending")
                
                with col3:
                    if job.status == JobStatus.RUNNING:
                        if st.button("⏸️ Pause", key=f"pause_{job.id}"):
                            queue.pause(job.id)
                            st.rerun()
                    if st.button("🛑 Cancel", key=f"cancel_{job.id}"):
                        queue.cancel(job.id)
                        if project:
                            project.status = ProjectStatus.CREATED
                            project.save()
                        st.rerun()
                
                st.markdown("---")
    
    # Queue stats
    st.subheader("📊 Queue Statistics")
    stats = queue.get_queue_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending", stats.get("pending", 0))
    col2.metric("Running", stats.get("running", 0))
    col3.metric("Completed", stats.get("completed", 0))
    col4.metric("Failed", stats.get("failed", 0))

# ═══════════════════════════════════════════════════════════════════════════
# AUTO REFRESH
# ═══════════════════════════════════════════════════════════════════════════
if st.sidebar.checkbox("🔄 Auto-refresh", value=False):
    import time
    time.sleep(5)
    st.rerun()
