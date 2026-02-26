"""
Knowledge Base - RAG-powered semantic search for municipal codes and organizational bylaws.
"""

import streamlit as st
import json
from core.rag import get_rag_pipeline, Document, DocumentType, SAMPLE_ZONING_CODE

# Initialize RAG Pipeline (Singleton in session state)
if 'rag_pipeline' not in st.session_state:
    st.session_state.rag_pipeline = get_rag_pipeline()
    # Pre-load sample data
    doc = Document(
        id="sample_zoning",
        title="Sample Zoning Code",
        doc_type=DocumentType.ZONING_CODE,
        source_url=None,
        jurisdiction="Santa Cruz",
        content=SAMPLE_ZONING_CODE
    )
    st.session_state.rag_pipeline.ingest_document(doc)

rag = st.session_state.rag_pipeline

st.set_page_config(
    page_title="Knowledge Base",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Civic Knowledge Base")
st.markdown("Semantic search for municipal codes, bylaws, and voting records.")

tab_search, tab_ingest = st.tabs(["🔍 Search", "📥 Ingest Documents"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: SEARCH
# ═══════════════════════════════════════════════════════════════════════════
with tab_search:
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Ask a question about zoning or bylaws", placeholder="e.g. What are the height limits for ADUs?")
    with col2:
        top_k = st.slider("Results", 1, 10, 3)

    if query:
        results = rag.query(query, top_k=top_k)

        if not results:
            st.warning("No relevant documents found.")
        else:
            st.subheader("Results")
            for i, res in enumerate(results):
                with st.expander(f"**{i+1}. Score: {res.score:.2f}** - {res.chunk.section_path}", expanded=i==0):
                    st.markdown(f"**Content:**\n\n{res.chunk.content}")
                    if res.parent_content:
                        st.divider()
                        st.caption("Full Section Context:")
                        st.text(res.parent_content)

                    st.caption(f"Source: {res.chunk.document_id} | Type: {res.chunk.metadata.get('doc_type')}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: INGEST
# ═══════════════════════════════════════════════════════════════════════════
with tab_ingest:
    st.header("Upload Documents")

    with st.form("ingest_form"):
        doc_title = st.text_input("Document Title")
        doc_type = st.selectbox("Document Type", options=[t.value for t in DocumentType])
        jurisdiction = st.text_input("Jurisdiction", value="General")
        content = st.text_area("Content (Paste text here)", height=300)

        if st.form_submit_button("Ingest Document"):
            if not content:
                st.error("Please provide content.")
            else:
                doc = Document(
                    id=f"doc_{len(rag.documents)+1}",
                    title=doc_title,
                    doc_type=DocumentType(doc_type),
                    source_url=None,
                    jurisdiction=jurisdiction,
                    content=content
                )
                chunk_count = rag.ingest_document(doc)
                st.success(f"Successfully ingested '{doc_title}' into {chunk_count} chunks.")

    st.divider()
    st.subheader("Index Statistics")
    st.write(rag.get_stats())
