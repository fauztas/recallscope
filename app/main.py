"""
RecallScope — Main Application Entry Point
Phase 11: Deployment preparation (active)
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to sys.path so utils can be imported reliably
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.config import is_groq_configured
from app.utils.data_loader import load_raw_dataset
from app.utils.discovery_view import DISCOVERY_SECTIONS, inject_styles, render_discovery
from app.utils.phase3_view import render_phase3_section
from app.utils.phase4_view import render_phase4_section
from app.utils.relevance_filter import load_relevance_dataset

# Page Configuration
st.set_page_config(
    page_title="RecallScope — AI Discovery Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load datasets
df_raw, validation_report = load_raw_dataset()
df_rel, rel_metrics = load_relevance_dataset()
inject_styles()

PIPELINE_PROGRESS = """
**Pipeline progress**
- [x] **Phase 0: Project Foundation** *(Completed)*
- [x] **Phase 1: Dataset Ingestion & Validation** *(Completed)*
- [x] **Phase 2: Relevance Filtering** *(Completed)*
- [x] **Phase 3: AI Research Classification** *(Completed)*
- [x] **Phase 4: Research Analysis** *(Completed)*
- [x] **Phase 5: Core Discovery Interface** *(Completed)*
- [x] **Phase 6: Ask the Evidence** *(Completed)*
- [x] **Phase 7: Challenge an Insight** *(Completed)*
- [x] **Phase 8: Quality & Integrity Checks** *(Completed)*
- [x] **Phase 9: UI Polish** *(Completed)*
- [x] **Phase 10: End-to-End Testing** *(Completed)*
- [x] **Phase 11: Deployment Preparation** *(Active)*
"""

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("RecallScope")
    st.caption("Vague-memory photo retrieval research")
    app_area = st.radio(
        "Open",
        ["Discovery Engine", "Research pipeline"],
        key="app_area",
    )
    discovery_section = "Research overview"
    if app_area == "Discovery Engine":
        discovery_section = st.radio("Explore", DISCOVERY_SECTIONS, key="discovery_section")
        st.caption("Public evidence and primary interviews stay on separate pages. They do not represent all Google Photos users.")
    else:
        st.caption("Build notes for the research pipeline. The evaluator view is the Discovery Engine.")
        with st.expander("Development status"):
            st.success("Phase 11 — deployment preparation")
            st.markdown(PIPELINE_PROGRESS)


if app_area == "Discovery Engine":
    render_discovery(discovery_section)
    st.stop()


# ==========================================
# MAIN PAGE HEADER & FOUNDATION
# ==========================================
st.title("RecallScope")
st.subheader("Research pipeline")
st.caption("This page keeps the earlier build steps. The evaluator-facing view is the Discovery Engine.")
with st.expander("Development status", expanded=False):
    st.markdown(PIPELINE_PROGRESS)

st.info(
    "**RecallScope** is an evidence-grounded AI discovery engine for investigating vague-memory photo retrieval problems."
)

st.markdown("""
When people know a photo exists in their library but cannot precisely describe it, where does retrieval break down?
RecallScope systematically organizes and analyzes qualitative public evidence to investigate where and why these journeys fail.
""")

st.divider()


# ==========================================
# PROJECT FOUNDATION METRICS (PHASE 0 CARRYOVER)
# ==========================================
st.subheader("System Foundation Status")

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    st.metric(label="Active Pipeline Phase", value="Phase 11", delta="Deployment preparation")
    st.caption("The Discovery Engine is the default view. This page keeps Phases 0–4.")

with col_f2:
    if validation_report.get("is_valid_schema", False):
        st.metric(
            label="Raw Dataset File",
            value=f"{validation_report['total_records']} Records",
            delta="Primary Corpus Loaded"
        )
        st.caption("`data/public_evidence_raw.csv` loaded read-only.")
    else:
        st.metric(label="Raw Dataset File", value="Error", delta="Check data/ folder")
        st.caption(validation_report.get("status_message", "File issue"))

with col_f3:
    api_ready = is_groq_configured()
    if api_ready:
        st.metric(label="API Configuration", value="Configured", delta="Groq key detected")
        st.caption("The Groq key is configured. Its value is not shown.")
    else:
        st.metric(label="API Configuration", value="Not configured", delta="Saved results still open")
        st.caption("Phases 0–2 work without a key. New AI classification waits for GROQ_API_KEY.")

st.divider()


# ==========================================
# PHASE 1: DATASET HEALTH & VALIDATION
# ==========================================
st.subheader("📊 Dataset Health & Validation")
st.caption("Automated quality audit of raw public research evidence without modifying source data.")

# Validation Status Banner
if not validation_report.get("is_valid_schema", False):
    st.error(f"❌ **{validation_report.get('status', 'Error')}**: {validation_report.get('status_message', 'Could not validate dataset.')}")
elif validation_report.get("status") == "Dataset Valid":
    st.success(f"✅ **{validation_report['status']}**: {validation_report['status_message']}")
else:
    st.warning(f"⚠️ **{validation_report['status']}**: {validation_report['status_message']}")

# Dataset Health Metric Cards
mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)

critical_missing = (
    validation_report.get("missing_record_ids", 0)
    + validation_report.get("missing_sources", 0)
    + validation_report.get("missing_original_texts", 0)
    + validation_report.get("missing_source_urls", 0)
)
duplicates_total = (
    validation_report.get("duplicate_record_ids_count", 0)
    + validation_report.get("duplicate_rows_count", 0)
)
flagged_total = len(validation_report.get("flagged_records", []))

with mcol1:
    st.metric("Total Records", validation_report.get("total_records", 0))
with mcol2:
    st.metric("Unique Record IDs", validation_report.get("unique_record_ids", 0))
with mcol3:
    st.metric("Sources", len(validation_report.get("source_distribution", {})))
with mcol4:
    st.metric("Missing Critical Fields", critical_missing)
with mcol5:
    st.metric("Duplicate Records", duplicates_total)
with mcol6:
    st.metric("Flagged for Review", flagged_total)


# Source Distribution Display
st.markdown("#### Source Platform Distribution")
source_dist = validation_report.get("source_distribution", {})

if source_dist:
    cols = st.columns(len(source_dist))
    for i, (source_name, count) in enumerate(source_dist.items()):
        with cols[i]:
            pct = (count / validation_report['total_records']) * 100 if validation_report['total_records'] > 0 else 0
            st.metric(label=source_name, value=f"{count} records", delta=f"{pct:.1f}% of sample")
else:
    st.info("No source distribution data available.")

st.divider()


# ==========================================
# PHASE 1: RAW EVIDENCE PREVIEW
# ==========================================
st.subheader("📋 Raw Public Evidence — Unclassified")
st.caption(
    "This table displays unaltered public research records loaded directly from `data/public_evidence_raw.csv`. "
    "No AI classifications, relevance filtering, or speculative inferences have been applied."
)

if not df_raw.empty:
    # Filtering / Search Controls for Exploration
    fcol1, fcol2 = st.columns([1, 2])
    with fcol1:
        sources_list = ["All Sources"] + sorted(list(df_raw["source"].dropna().unique()))
        selected_source = st.selectbox("Filter by Source:", sources_list, key="raw_source_filter")
    with fcol2:
        search_query = st.text_input("Search raw text (keyword):", placeholder="e.g. cat, search, bike, album...", key="raw_search")

    # Apply interactive filters (in-memory only; does NOT modify CSV)
    filtered_df = df_raw.copy()
    if selected_source != "All Sources":
        filtered_df = filtered_df[filtered_df["source"] == selected_source]
    if search_query.strip():
        filtered_df = filtered_df[
            filtered_df["original_text"].str.contains(search_query.strip(), case=False, na=False)
        ]

    st.markdown(f"**Showing {len(filtered_df)} of {len(df_raw)} records:**")

    # Display Data Table
    st.dataframe(
        filtered_df[["record_id", "source", "date", "original_text", "source_url"]],
        use_container_width=True,
        hide_index=True
    )

    # Detailed Record Inspector Drawer
    with st.expander("🔍 Inspect Individual Record Details"):
        selected_id = st.selectbox("Select Record ID to inspect:", filtered_df["record_id"].tolist(), key="raw_inspector")
        if selected_id:
            record_row = filtered_df[filtered_df["record_id"] == selected_id].iloc[0]
            st.markdown(f"**Record ID:** `{record_row['record_id']}` | **Source:** `{record_row['source']}` | **Date:** `{record_row['date']}`")
            st.markdown("**Verbatim Original Text:**")
            st.markdown(f"> *\"{record_row['original_text']}\"*")
            st.markdown(f"**Public Source Link:** [{record_row['source_url']}]({record_row['source_url']})")
else:
    st.warning("No data records available to display.")

# Review of Flagged Records (if any)
if flagged_total > 0:
    st.divider()
    st.subheader("⚠️ Records Flagged for Review")
    st.markdown("The following records contain potential quality issues (e.g. extremely short text or missing optional fields):")
    for item in validation_report["flagged_records"]:
        with st.expander(f"Record {item['record_id']} — Issues: {', '.join(item['issues'])}"):
            st.write(f"**Row Index:** {item['row_index']}")
            st.write(f"**Issues:** {', '.join(item['issues'])}")
            st.write(f"**Text Preview:** {item['original_text_preview']}")
else:
    st.caption("✅ **Audit Clean:** Zero records were flagged for review in this batch.")

st.divider()


# ==========================================
# PHASE 2: RELEVANCE FILTERING
# ==========================================
st.subheader("🎯 Phase 2 — Relevance Filtering")
st.caption(
    "Each public evidence record is evaluated against the core research question: "
    "*'Where and why do users struggle when trying to retrieve a photo they remember exists, "
    "especially when they cannot precisely describe or locate it?'* "
    "No root cause analysis, product recommendations, or failure-stage classification has been applied at this stage."
)

# ── Phase 2 Metric Cards ──────────────────────────────────────────────────────
p2col1, p2col2, p2col3, p2col4, p2col5, p2col6 = st.columns(6)

with p2col1:
    st.metric("Total Processed", rel_metrics["total_records"])
with p2col2:
    st.metric("✅ Relevant", rel_metrics["relevant_count"])
with p2col3:
    st.metric("❌ Irrelevant", rel_metrics["irrelevant_count"])
with p2col4:
    st.metric("❓ Uncertain", rel_metrics["uncertain_count"])
with p2col5:
    st.metric("🔎 Review Required", rel_metrics["review_required_count"])
with p2col6:
    st.metric("Relevance Rate", f"{rel_metrics['relevance_rate']:.1f}%")

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown("#### Browse & Filter Relevance Decisions")

rf1, rf2, rf3 = st.columns([1, 1, 1])

with rf1:
    label_options = ["All Labels", "Relevant", "Irrelevant", "Uncertain"]
    selected_label = st.selectbox("Filter by Relevance Label:", label_options, key="rel_label_filter")

with rf2:
    rel_sources = ["All Sources"] + sorted(df_rel["source"].dropna().unique().tolist())
    selected_rel_source = st.selectbox("Filter by Source:", rel_sources, key="rel_source_filter")

with rf3:
    show_review_only = st.checkbox("Show Review Required only", value=False, key="rel_review_filter")

# Apply filters
filtered_rel = df_rel.copy()
if selected_label != "All Labels":
    filtered_rel = filtered_rel[filtered_rel["relevance_label"] == selected_label]
if selected_rel_source != "All Sources":
    filtered_rel = filtered_rel[filtered_rel["source"] == selected_rel_source]
if show_review_only:
    filtered_rel = filtered_rel[filtered_rel["review_required"] == True]

st.markdown(f"**Showing {len(filtered_rel)} of {rel_metrics['total_records']} records:**")

# ── Relevance Table ───────────────────────────────────────────────────────────
st.dataframe(
    filtered_rel[["record_id", "source", "relevance_label", "relevance_reason", "evidence_excerpt", "review_required"]],
    use_container_width=True,
    hide_index=True
)

# ── Record Inspector ──────────────────────────────────────────────────────────
with st.expander("🔍 Inspect Individual Relevance Decision"):
    if not filtered_rel.empty:
        inspect_id = st.selectbox(
            "Select Record ID to inspect:",
            filtered_rel["record_id"].tolist(),
            key="rel_inspector"
        )
        if inspect_id:
            r = filtered_rel[filtered_rel["record_id"] == inspect_id].iloc[0]
            st.markdown(f"**Record ID:** `{r['record_id']}` | **Source:** `{r['source']}` | **Date:** `{r['date']}`")

            label_colour = {"Relevant": "🟢", "Irrelevant": "🔴", "Uncertain": "🟡"}.get(r["relevance_label"], "⚪")
            st.markdown(f"**Relevance Decision:** {label_colour} **{r['relevance_label']}**")

            if r["review_required"]:
                st.warning("⚠️ This record is flagged for manual review before Phase 3 classification.")

            st.markdown("**Relevance Reasoning:**")
            st.info(r["relevance_reason"])

            st.markdown("**Evidence Excerpt (verbatim from original text):**")
            st.markdown(f"> *\"{r['evidence_excerpt']}\"*")

            st.markdown("**Full Verbatim Original Text:**")
            st.markdown(f"> *\"{r['original_text']}\"*")

            st.markdown(f"**Public Source Link:** [{r['source_url']}]({r['source_url']})")
    else:
        st.info("No records match the current filters.")

# ── Uncertain Records Summary ─────────────────────────────────────────────────
if rel_metrics["uncertain_count"] > 0:
    st.markdown("#### ❓ Uncertain Records — Awaiting Manual Review")
    st.caption(
        "These records could not be confidently classified as Relevant or Irrelevant. "
        "They stay available for manual review and are not sent for automatic Phase 3 classification."
    )
    for unc in rel_metrics["uncertain_records"]:
        with st.expander(f"{unc['record_id']} — {unc['source']}"):
            st.markdown(f"**Reason for Uncertainty:** {unc['relevance_reason']}")
            st.markdown(f"**Evidence Excerpt:** *\"{unc['evidence_excerpt']}\"*")

# ── Research Integrity Note ───────────────────────────────────────────────────
st.divider()
st.markdown("### 🛡️ Phase 2 Research Integrity Note")
st.info(
    "Relevance filtering determines whether evidence belongs to the research question. "
    "It does not establish prevalence, root cause, or product opportunity. "
    "The current 24-record corpus is interim and not representative of the broader Google Photos population. "
    "Relevance counts are descriptive of this corpus only. "
    "No product conclusion should be drawn from Phase 2."
)

st.divider()


# ==========================================
# PHASE 3: AI RESEARCH CLASSIFICATION
# ==========================================
render_phase3_section(df_rel)

st.divider()


# ==========================================
# PHASE 4: RESEARCH ANALYSIS
# ==========================================
render_phase4_section()

st.divider()


# ==========================================
# RESEARCH INTEGRITY NOTE (PHASE 1 CARRYOVER)
# ==========================================
st.markdown("### 🛡️ Research Integrity & Methodology Note")
st.info("""
- **Immutable Evidence:** Raw public evidence in `data/public_evidence_raw.csv` (and original test batch in `data/public_evidence_raw_batch1.csv`) is preserved strictly as originally collected.
- **Interim Corpus Status:** These 24 records represent an interim evidence corpus under active collection. They are NOT the final research sample and must NOT be interpreted as representative of all Google Photos users.
- **No Silent Deletions:** Quality validation audits records for missing fields, duplicates, or extreme brevity, but flags them for review rather than silently dropping or modifying them.
- **Directional Scope:** Dataset counts describe the collected qualitative sample only. They represent directional research signals, not population prevalence.
""")

st.divider()

# ==========================================
# PLANNED MODULES PREVIEW (PHASE 0 CARRYOVER)
# ==========================================
st.subheader("Discovery Engine")
st.markdown("The evaluator interface is available from the sidebar under **Discovery Engine**.")

pcol1, pcol2 = st.columns(2)

with pcol1:
    st.markdown("""
    - **Research overview:** Corpus counts, sources, and evidence strength.
    - **Failure explorer:** Audited stages, with the original post beside the classification.
    - **Memory and behaviour:** Saved clues, searches, scrolling, and outcomes. Unknown stays Unknown.
    """)

with pcol2:
    st.markdown("""
    - **Patterns and candidate areas:** The approved Phase 4 cards, still unranked.
    - **Contradictions and gaps:** Limits on what this corpus can support.
    - **Ask the Evidence, Challenge an Insight, and Quality & Integrity:** In the Discovery Engine. Groq runs only when Ask or Challenge is clicked.
    """)
