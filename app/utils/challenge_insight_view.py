"""
RecallScope — Challenge an Insight section

Renders the challenge form. Groq is called only when the evaluator clicks
Challenge this insight.
"""

from typing import Any, Dict, List

import streamlit as st

from app.utils.challenge_insight import EXAMPLE_INSIGHTS, _research_questions, challenge_insight
from app.utils.config import is_groq_configured


def render_challenge_insight(records: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Show the challenge tool. This function does not call Groq by itself."""
    st.markdown("### Challenge an Insight")
    st.write("Test a proposed insight against the evidence before treating it as a finding.")
    st.info(
        "This tool looks for evidence on both sides so a preferred idea is not simply confirmed. "
        "That is how it resists confirmation bias. It searches the saved corpus for support and for evidence "
        "that weakens or limits the insight. It is not a hypothesis-confirmation tool."
    )
    if is_groq_configured():
        st.caption("The model is ready. The key is not shown. A request is sent only when you click Challenge this insight.")
    else:
        st.warning("The model key is not configured. The tool will not invent an assessment.")

    st.markdown("**Example insights**")
    for index, example in enumerate(EXAMPLE_INSIGHTS):
        if st.button(example, key=f"challenge_example_{index}", use_container_width=True):
            st.session_state["challenge_text"] = example
            st.rerun()

    insight = st.text_area(
        "Proposed insight",
        key="challenge_text",
        height=90,
        placeholder="Type an insight to test against the saved evidence.",
    )
    if st.button("Challenge this insight", type="primary", key="challenge_submit"):
        with st.spinner("Comparing the insight with the saved evidence..."):
            st.session_state["challenge_result"] = challenge_insight(insight, records, analysis)

    result = st.session_state.get("challenge_result")
    if not result:
        st.caption("No insight has been challenged in this session.")
        return
    _render_report(result)


def _render_report(result: Dict[str, Any]) -> None:
    st.markdown("#### A. Proposed insight")
    st.write(result.get("proposed_insight") or "No insight was entered.")

    if result.get("error"):
        st.error(result["error"])

    st.markdown("#### B. Assessment")
    st.write(result.get("assessment") or "Insufficient evidence")
    if result.get("assessment_reason"):
        st.write(result["assessment_reason"])
    st.caption("This assessment describes the saved interim corpus. It is not a population claim.")

    _render_side(
        "C. Evidence supporting the insight",
        result.get("supporting") or [],
        "No saved record was placed on the supporting side.",
    )
    _render_side(
        "D. Evidence challenging the insight",
        result.get("challenging") or [],
        "No saved record was placed on the challenging side.",
    )

    st.markdown("#### E. Evidence gaps / uncertainty")
    st.write(result.get("evidence_gaps") or "The current corpus cannot establish this insight.")
    st.caption(result.get("corpus_limitation", ""))
    uncertain = result.get("uncertain_record_ids") or []
    if uncertain:
        st.caption(
            "Uncertain context, not used as support or contradiction: " + ", ".join(uncertain)
        )

    st.markdown("#### F. What should we investigate next?")
    st.caption("These are research questions, not product recommendations.")
    questions = _research_questions(
        result.get("next_research_questions"),
        result.get("proposed_insight") or "",
    )
    for question in questions:
        st.markdown(f"- {question}")

    st.markdown("#### G. Traceability")
    st.caption(result.get("retrieval_method", ""))
    retrieved = result.get("retrieved_record_ids") or []
    st.write("Record IDs retrieved before the model assessment: " + (", ".join(retrieved) or "None"))


def _render_side(title: str, cards: List[Dict[str, Any]], empty_message: str) -> None:
    st.markdown(f"#### {title}")
    if not cards:
        st.write(empty_message)
        return
    for card in cards:
        with st.container(border=True):
            st.markdown(f"**{card['record_id']}** — {card.get('source', '')}")
            if card.get("needs_human_review"):
                st.warning(f"{card['record_id']} is flagged for human review.")
            st.caption(
                f"Audited stage: {card.get('primary_failure_stage', '')} · "
                f"Evidence strength: {card.get('evidence_strength', '')}"
            )
            st.write(card.get("excerpt", ""))
            st.write(card.get("reason", ""))
            if card.get("source_url"):
                st.markdown(f"[Open original source]({card['source_url']})")
