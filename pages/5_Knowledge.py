"""
Knowledge Base Page - RAG-powered document search and API data.

Provides municipal code search and integrated external data display.
"""

import streamlit as st

st.set_page_config(
    page_title="Knowledge Base - Gross Utility",
    page_icon="📚",
    layout="wide"
)

st.markdown("""
<style>
    #MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
    .block-container { padding: 1rem 2rem; }
</style>
""", unsafe_allow_html=True)

from core.rag import RAGPipeline, Document, DocumentType, SAMPLE_ZONING_CODE
from core.api_layer import get_api_layer

st.title("📚 Knowledge Base")
st.markdown("*Search municipal codes and access integrated property data.*")

# Initialize session state
if 'rag_pipeline' not in st.session_state:
    st.session_state.rag_pipeline = RAGPipeline()
    # Pre-load sample zoning code
    doc = Document(
        id="sample_zoning",
        title="Sample Municipal Zoning Code",
        doc_type=DocumentType.ZONING_CODE,
        source_url=None,
        jurisdiction="Sample City",
        content=SAMPLE_ZONING_CODE
    )
    st.session_state.rag_pipeline.ingest_document(doc)

if 'api_layer' not in st.session_state:
    st.session_state.api_layer = get_api_layer()

# Tabs
tab_search, tab_api, tab_docs = st.tabs([
    "🔍 Document Search", "🌐 API Data", "📄 Documents"
])

with tab_search:
    st.header("Search Municipal Codes")
    st.markdown("Ask questions about zoning regulations, building codes, and ordinances.")
    
    pipeline = st.session_state.rag_pipeline
    stats = pipeline.get_stats()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", stats['documents'])
    col2.metric("Chunks", stats['chunks'])
    col3.metric("Jurisdictions", len(stats['jurisdictions']))
    
    st.write("---")
    
    query = st.text_input(
        "Ask a question", 
        placeholder="What are the ADU requirements?",
        key="rag_query"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        top_k = st.number_input("Results", 1, 10, 3)
    
    if st.button("🔍 Search", type="primary") and query:
        with st.spinner("Searching..."):
            results = pipeline.query(query, top_k=top_k)
        
        if results:
            st.success(f"Found {len(results)} relevant sections")
            
            for i, result in enumerate(results, 1):
                chunk = result.chunk
                score = result.score
                
                with st.expander(
                    f"**{i}. {chunk.section_path or 'Document'}** (Score: {score:.2f})",
                    expanded=(i == 1)
                ):
                    st.markdown(chunk.content)
                    
                    if result.parent_content and result.parent_content != chunk.content:
                        st.write("---")
                        st.caption("**Full Section Context:**")
                        st.markdown(result.parent_content[:1000] + "..." 
                                   if len(result.parent_content) > 1000 
                                   else result.parent_content)
        else:
            st.info("No results found. Try a different query.")
    
    st.write("---")
    st.subheader("💡 Sample Questions")
    
    sample_questions = [
        "What is the maximum building height in R-1?",
        "What are the setback requirements?",
        "Tell me about accessory dwelling units",
        "What are the parking requirements?",
        "What uses are allowed in commercial zones?",
    ]
    
    cols = st.columns(2)
    for i, q in enumerate(sample_questions):
        with cols[i % 2]:
            if st.button(q, key=f"sample_{i}"):
                st.session_state.rag_query = q
                st.rerun()

with tab_api:
    st.header("Integrated Property Data")
    st.markdown("Get zoning, construction costs, climate risk, and solar potential for any location.")
    
    api = st.session_state.api_layer
    
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input("Latitude", value=36.9741, format="%.4f")
    with col2:
        longitude = st.number_input("Longitude", value=-122.0308, format="%.4f")
    
    col1, col2 = st.columns(2)
    with col1:
        roof_sqft = st.number_input("Roof Area (sqft)", value=2000, min_value=100)
    with col2:
        building_sqft = st.number_input("Building Size (sqft)", value=10000, min_value=500)
    
    if st.button("🌐 Fetch All Data", type="primary"):
        with st.spinner("Fetching data from all sources..."):
            data = api.get_all_data(
                latitude, longitude, 
                roof_sqft=roof_sqft, 
                sqft=building_sqft
            )
        
        st.success("Data retrieved!")
        
        # Zoning
        st.subheader("🏗️ Zoning Data")
        zoning = data['zoning']
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Zone", zoning.zone_code)
        col2.metric("Max Height", f"{zoning.max_height_ft} ft")
        col3.metric("Max FAR", zoning.max_far)
        col4.metric("Lot Coverage", f"{zoning.max_lot_coverage*100:.0f}%")
        
        st.caption(f"**{zoning.zone_name}** - Allowed uses: {', '.join(zoning.allowed_uses)}")
        
        # Construction Costs
        st.subheader("💰 Construction Costs")
        construction = data['construction']
        col1, col2, col3 = st.columns(3)
        col1.metric("Cost/sqft", f"${construction.cost_per_sqft:.0f}")
        col2.metric("Total Estimate", f"${construction.total_estimate:,.0f}")
        col3.metric("Location Factor", f"{construction.location_factor:.2f}x")
        
        # Climate Risk
        st.subheader("🌍 Climate Risk")
        climate = data['climate']
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("🌊 Flood", f"{climate.flood_factor}/10")
        col2.metric("🔥 Fire", f"{climate.fire_factor}/10")
        col3.metric("🌡️ Heat", f"{climate.heat_factor}/10")
        col4.metric("💨 Wind", f"{climate.wind_factor}/10")
        col5.metric("📊 Overall", f"{climate.overall_risk}/10")
        
        st.caption(f"Estimated annual insurance: **${climate.insurance_estimate:,.0f}**")
        
        # Solar
        st.subheader("☀️ Solar Potential")
        solar = data['solar']
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Annual kWh", f"{solar.annual_kwh:,.0f}")
        col2.metric("System Size", f"{solar.system_capacity_kw:.1f} kW")
        col3.metric("Panels", solar.panel_count)
        col4.metric("Annual Savings", f"${solar.estimated_savings:,.0f}")

with tab_docs:
    st.header("Document Management")
    st.markdown("Upload and manage municipal code documents.")
    
    pipeline = st.session_state.rag_pipeline
    
    # Show existing documents
    if pipeline.documents:
        st.subheader("Indexed Documents")
        for doc_id, doc in pipeline.documents.items():
            with st.expander(f"📄 {doc.title}"):
                col1, col2 = st.columns(2)
                col1.write(f"**Type:** {doc.doc_type.value}")
                col1.write(f"**Jurisdiction:** {doc.jurisdiction}")
                col2.write(f"**Chunks:** {len(doc.chunks)}")
                col2.write(f"**ID:** {doc.id}")
    
    st.write("---")
    st.subheader("Add New Document")
    
    col1, col2 = st.columns(2)
    with col1:
        doc_title = st.text_input("Document Title", "City Zoning Ordinance")
        doc_jurisdiction = st.text_input("Jurisdiction", "City of Example")
    with col2:
        doc_type = st.selectbox("Document Type", list(DocumentType),
            format_func=lambda d: d.value.replace("_", " ").title())
    
    doc_content = st.text_area(
        "Document Content",
        height=200,
        placeholder="Paste the full text of the document here..."
    )
    
    if st.button("📥 Ingest Document"):
        if doc_title and doc_content:
            new_doc = Document(
                id=f"doc_{len(pipeline.documents)}",
                title=doc_title,
                doc_type=doc_type,
                source_url=None,
                jurisdiction=doc_jurisdiction,
                content=doc_content
            )
            
            chunk_count = pipeline.ingest_document(new_doc)
            st.success(f"Ingested '{doc_title}' with {chunk_count} chunks!")
            st.rerun()
        else:
            st.error("Please provide both title and content.")
