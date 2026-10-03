"""
RecallScope — Ask the Evidence section

Renders the question form. Groq is called only when the evaluator clicks Ask.
"""

from typing import Any, Dict, List

import streamlit as st

from app.utils.ask_evidence import EXAMPLE_QUESTIONS, ask_evidence
from app.utils.config import is_groq_configured


def render_ask_evidence(records: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Show the grounded question tool. This function does not call Groq by itself."""
    st.markdown("### Ask the Evidence")
    st.write("Ask a question about the saved posts. An answer is prepared only after you click Ask.")
    st.info(
        "Ask the Evidence answers questions using only the saved RecallScope research corpus. "
        "It is designed to expose evidence, uncertainty and contradictions rather than generate unsupported conclusions."
    )
    if is_groq_configured():
        st.caption("The model is ready. The key is not shown. A request is sent only when you click Ask.")
    else:
        st.warning("The model key is not configured. Ask will not invent an answer.")

    st.markdown("**Example questions**")
    columns = st.columns(2)
    for index, example in enumerate(EXAMPLE_QUESTIONS):
        if columns[index % 2].button(example, key=f"ask_example_{index}", use_container_width=True):
            st.session_state["ask_question"] = example
            st.rerun()

    question = st.text_area(
        "Research question",
        key="ask_question",
        height=90,
        placeholder="Ask about the saved evidence, not about Google Photos in general.",
    )
    if st.button("Ask", type="primary", key="ask_submit"):
        with st.spinner("Reading the saved evidence..."):
            st.session_state["ask_result"] = ask_evidence(question, records, analysis)

    result = st.session_state.get("ask_result")
    if not result:
        st.caption("No question has been sent in this session.")
        return
    _render_result(result)


def _render_result(result: Dict[str, Any]) -> None:
    st.markdown("#### Evidence-grounded answer")
    if result.get("error"):
        st.error(result["error"])
        st.caption("No answer was invented.")
    if result.get("evidence_is_insufficient"):
        st.warning(result["short_answer"])
    elif result.get("short_answer"):
        st.write(result["short_answer"])
    if result.get("evidence_is_mixed"):
        st.warning("The evidence is mixed. Read the limiting records before treating the answer as a single conclusion.")

    st.markdown("**Evidence summary**")
    st.write(result.get("evidence_summary") or "No summary was returned.")
    st.markdown("**Supporting record IDs:** " + (", ".join(result.get("supporting_record_ids") or []) or "None"))
    if result.get("limiting_record_ids"):
        st.markdown("**Limiting or contradictory record IDs:** " + ", ".join(result["limiting_record_ids"]))
    st.markdown(f"**Evidence strength:** {result.get('evidence_strength_note') or 'Not available.'}")
    st.caption(result.get("corpus_limitation", ""))
    st.markdown("**Records used**")
    st.caption("Each card is copied from the saved post. It includes the record ID and a link to the original source when one was saved.")
    st.caption(result.get("retrieval_method", ""))
    if result.get("retrieved_record_ids"):
        st.caption("Records retrieved before the answer: " + ", ".join(result["retrieved_record_ids"]))

    _render_cards("Verbatim evidence used in the answer", result.get("supporting_excerpts") or [])
    _render_cards("Contradictory or limiting evidence", result.get("limiting_excerpts") or [])


def _render_cards(title: str, cards: List[Dict[str, str]]) -> None:
    if not cards:
        return
    st.markdown(f"#### {title}")
    for card in cards:
        with st.expander(f"{card['record_id']} — {card['source']} — {card['evidence_strength']}"):
            st.markdown(
                f"**Date:** {card['date']}  \n"
                f"**Failure stage:** {card['primary_failure_stage']}"
            )
            st.markdown(f"> {card['excerpt']}")
            url = card.get("source_url", "")
            if str(url).startswith("http://") or str(url).startswith("https://"):
                st.markdown(f"[Open source URL]({url})")
            elif url:
                st.markdown(f"**Source URL:** `{url}`")
