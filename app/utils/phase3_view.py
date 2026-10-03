"""
RecallScope — Phase 3 Streamlit section

Displays saved AI classifications. Reading this page does not call the LLM.
"""

import pandas as pd
import streamlit as st

from app.classify_pipeline import load_classified_dataset, run_classification_pipeline
from app.utils.config import is_groq_configured


TABLE_COLUMNS = [
    "record_id",
    "source",
    "photo_type",
    "primary_failure_stage",
    "secondary_failure_stage",
    "retrieval_outcome",
    "evidence_strength",
    "confidence",
    "needs_human_review",
]


def _stage_sort_key(label: str) -> str:
    text = str(label)
    return text if text[:1] == "F" else f"Z {text}"


def render_phase3_section(df_relevance: pd.DataFrame) -> None:
    """Render the Phase 3 audit view from the saved classification file."""
    st.subheader("Phase 3 — AI Research Classification")
    st.caption(
        "Relevant public evidence is classified into structured research observations. "
        "Opening this page reuses the saved file and does not call the AI again."
    )

    classified, metrics = load_classified_dataset()

    if is_groq_configured():
        st.caption("Groq API key: configured. The key is not displayed.")
    else:
        st.warning(
            "GROQ_API_KEY is not configured. Saved classifications can still be reviewed. "
            "New classification was not started."
        )

    if st.button("Classify relevant records that are not yet saved", key="phase3_classify_button"):
        if not is_groq_configured():
            st.error("GROQ_API_KEY is missing. No classifications were invented.")
        else:
            with st.spinner("Classifying only relevant records that do not already have a saved result..."):
                try:
                    summary = run_classification_pipeline()
                    if summary.get("newly_classified", 0) == 0:
                        st.success("Saved classifications were reused. No new AI calls were made.")
                    else:
                        st.success(
                            f"Saved {summary['newly_classified']} new classification"
                            f"{'' if summary['newly_classified'] == 1 else 's'}."
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(
                        "AI classification could not be completed "
                        f"({type(exc).__name__}). Any classifications already saved are still available. "
                        "Missing values were not invented."
                    )

    eligible = int((df_relevance["relevance_label"] == "Relevant").sum()) if not df_relevance.empty else 0
    uncertain = df_relevance[df_relevance["relevance_label"] == "Uncertain"] if not df_relevance.empty else df_relevance

    st.markdown("#### Classification Overview")
    overview_1, overview_2, overview_3, overview_4 = st.columns(4)
    overview_1.metric("Eligible for AI classification", metrics.get("eligible_count", eligible))
    overview_2.metric("Successfully classified", metrics.get("successful_count", 0))
    overview_3.metric("Needs human review", metrics.get("human_review_count", 0))
    overview_4.metric("Uncertain records kept separate", int(len(uncertain)))

    if not metrics.get("available"):
        st.info(
            "Phase 3 output has not been created yet. Relevant records can be classified with the button above. "
            "Uncertain records are not sent for automatic classification."
        )
    else:
        strength_distribution = metrics.get("evidence_strength_distribution", {})
        stage_distribution = metrics.get("failure_stage_distribution", {})

        st.markdown("#### Evidence-strength distribution")
        if strength_distribution:
            strength_columns = st.columns(len(strength_distribution))
            for index, (label, count) in enumerate(strength_distribution.items()):
                strength_columns[index].metric(str(label), int(count))
        else:
            st.info("No evidence-strength values are available yet.")

        st.markdown("#### Failure-stage distribution")
        st.caption("Counts use the primary failure stage of successfully classified records in this corpus.")
        if stage_distribution:
            stage_frame = pd.DataFrame(
                [{"failure_stage": stage, "records": count} for stage, count in stage_distribution.items()]
            ).sort_values("failure_stage", key=lambda series: series.map(_stage_sort_key))
            st.bar_chart(stage_frame.set_index("failure_stage"), horizontal=True)
            st.dataframe(stage_frame, use_container_width=True, hide_index=True)
        else:
            st.info("No failure-stage values are available yet.")

        st.markdown("#### Filters")
        filter_columns = st.columns(5)
        stage_options = ["All stages"] + sorted(classified["primary_failure_stage"].dropna().unique().tolist(), key=_stage_sort_key)
        source_options = ["All sources"] + sorted(classified["source"].dropna().unique().tolist())
        photo_options = ["All photo types"] + sorted(classified["photo_type"].dropna().unique().tolist())
        strength_options = ["All strengths"] + sorted(classified["evidence_strength"].dropna().unique().tolist())
        review_options = ["All review statuses", "Needs human review", "No human review"]

        selected_stage = filter_columns[0].selectbox("Failure stage", stage_options, key="phase3_stage_filter")
        selected_source = filter_columns[1].selectbox("Source", source_options, key="phase3_source_filter")
        selected_photo = filter_columns[2].selectbox("Photo type", photo_options, key="phase3_photo_filter")
        selected_strength = filter_columns[3].selectbox("Evidence strength", strength_options, key="phase3_strength_filter")
        selected_review = filter_columns[4].selectbox("Human-review status", review_options, key="phase3_review_filter")

        filtered = classified.copy()
        if selected_stage != "All stages":
            filtered = filtered[filtered["primary_failure_stage"] == selected_stage]
        if selected_source != "All sources":
            filtered = filtered[filtered["source"] == selected_source]
        if selected_photo != "All photo types":
            filtered = filtered[filtered["photo_type"] == selected_photo]
        if selected_strength != "All strengths":
            filtered = filtered[filtered["evidence_strength"] == selected_strength]
        if selected_review == "Needs human review":
            filtered = filtered[filtered["needs_human_review"] == True]
        elif selected_review == "No human review":
            filtered = filtered[filtered["needs_human_review"] == False]

        st.markdown("#### Structured Evidence Table")
        st.caption(f"Showing {len(filtered)} of {len(classified)} classified records.")
        if filtered.empty:
            st.info("No records match these criteria.")
        else:
            st.dataframe(filtered[TABLE_COLUMNS], use_container_width=True, hide_index=True)

        st.markdown("#### Individual Record Inspector")
        if filtered.empty:
            st.info("Select a broader filter to inspect a record.")
        else:
            selected_id = st.selectbox(
                "Select a classified record",
                filtered["record_id"].tolist(),
                key="phase3_inspector",
            )
            record = filtered[filtered["record_id"] == selected_id].iloc[0]
            _render_record(record)

    if not uncertain.empty:
        st.markdown("#### Uncertain records preserved for review")
        st.caption(
            "These records were not automatically classified. They remain in the Phase 2 relevance file "
            "and are not treated as strong evidence."
        )
        for _, row in uncertain.iterrows():
            with st.expander(f"{row['record_id']} — {row['source']} — Uncertain, not auto-classified"):
                st.markdown(f"**Relevance reason:** {row['relevance_reason']}")
                st.markdown("**Verbatim original text:**")
                st.text_area(
                    f"Original text for {row['record_id']}",
                    value=str(row["original_text"]),
                    height=140,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"uncertain_text_{row['record_id']}",
                )

    st.markdown("#### Research Integrity Note")
    st.info(
        "AI classifications are research interpretations, not ground truth. "
        "Original evidence remains available for auditing. "
        "Unknown is retained where evidence is insufficient. "
        "Frequencies from this corpus are directional and are NOT population prevalence."
    )


def _render_record(record: pd.Series) -> None:
    original_column, interpretation_column = st.columns(2)

    with original_column:
        st.markdown("##### A) Original public evidence")
        st.caption("Verbatim source evidence. This text was not written by the AI.")
        st.markdown(
            f"**Record ID:** `{record['record_id']}`  \n"
            f"**Source:** {record['source']}  \n"
            f"**Date:** {record['date']}"
        )
        st.text_area(
            "Verbatim original text",
            value=str(record["original_text"]),
            height=220,
            disabled=True,
            key=f"original_{record['record_id']}",
        )
        source_url = str(record["source_url"])
        if source_url.startswith("http://") or source_url.startswith("https://"):
            st.markdown(f"**Source URL:** [{source_url}]({source_url})")
        else:
            st.markdown(f"**Source URL:** `{source_url}`")

    with interpretation_column:
        st.markdown("##### B) AI-generated interpretation")
        st.caption("Research interpretation produced by the model. This is not the original evidence.")
        st.markdown(f"**Retrieval intent:** {record['retrieval_intent']}")
        st.markdown(f"**Remembered clues:** {record['remembered_clues']}")
        st.markdown(f"**Search behavior:** {record['search_or_browse_behavior']}")
        st.markdown(
            f"**Failure stage:** {record['primary_failure_stage']}  \n"
            f"**Secondary failure stage:** {record['secondary_failure_stage']}"
        )
        st.markdown(f"**Failure reason:** {record['failure_reason']}")
        st.markdown(f"**Outcome:** {record['retrieval_outcome']}")
        st.markdown(f"**Candidate-overload signal:** {record['candidate_overload_signal']}")
        st.markdown(f"**Recognition-difficulty signal:** {record['recognition_difficulty_signal']}")
        st.markdown(
            f"**Evidence strength:** {record['evidence_strength']}  \n"
            f"**Confidence:** {record['confidence']}"
        )
        review_label = "Needs human review" if bool(record["needs_human_review"]) else "No human review requested"
        st.markdown(f"**Review status:** {review_label}")
        if str(record.get("human_review_reason", "")).strip():
            st.markdown(f"**Human-review reason:** {record['human_review_reason']}")

    with st.expander("Additional structured fields for this record"):
        st.markdown(f"**Retrieval scenario:** {record['retrieval_scenario']}")
        st.markdown(f"**Photo type:** {record['photo_type']}")
        st.markdown(f"**Missing or forgotten clues:** {record['missing_or_forgotten_clues']}")
        st.markdown(f"**Reformulation behavior:** {record['reformulation_behavior']}")
        st.markdown(f"**Manual browsing behavior:** {record['manual_browsing_behavior']}")
        st.markdown(f"**Workaround:** {record['workaround']}")
        st.markdown(f"**Query-difficulty signal:** {record['query_difficulty_signal']}")
        st.markdown(f"**Manual-scroll signal:** {record['manual_scroll_signal']}")
        st.markdown(f"**Evidence-strength reason:** {record['evidence_strength_reason']}")
        st.markdown(f"**AI interpretation:** {record['ai_interpretation']}")
        st.markdown(
            f"**Phase 2 review required:** {record['review_required']}  \n"
            f"**Classification status:** {record['classification_status']}  \n"
            f"**Provider / model:** {record['llm_provider']} / {record['llm_model']}"
        )
        if str(record.get("classification_error", "")).strip():
            st.markdown(f"**Classification error:** {record['classification_error']}")
