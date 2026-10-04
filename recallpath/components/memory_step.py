"""Memory description and the clue review that follows it."""

import html

import streamlit as st

from recallpath.services.memory_interpreter import interpret_memory
from recallpath.services.groq_client import complete_text
from recallpath.utils.errors import ProviderError, public_detail, public_message

EXAMPLE = (
    "It was from a trip with my cousins. Four of us were sitting outside at a cafe. "
    "There were plants around us and I think I was wearing white."
)


def _chips(items: list, css: str, prefix: str) -> None:
    if not items:
        st.caption("None.")
        return
    chips = []
    for item in items:
        label = html.escape(item.get("text") or "")
        chips.append(f'<span class="rp-chip {css}">{prefix}{label}</span>')
    st.markdown(f'<div class="rp-chips">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_clue_groups(memory: dict) -> None:
    st.markdown("**You said**")
    st.caption("Taken from your description.")
    _chips(memory.get("user_stated") or [], "rp-stated", "")
    st.markdown("**You weren't sure**")
    st.caption("Kept as uncertain. These will not rule a photo out.")
    _chips(memory.get("hedged") or [], "rp-hedged", "")
    st.markdown("**Our interpretation**")
    st.caption("A reading of your words, not a fact you stated.")
    _chips(memory.get("ai_inferred") or [], "rp-inferred", "")


def render_memory(session: dict) -> None:
    st.markdown('<p class="rp-section">Describe what you remember</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-copy">You do not need the date, the place, or the perfect words. Your description is sent to Groq so it can be sorted into clues.</p>',
        unsafe_allow_html=True,
    )
    if "rpw_memory" not in st.session_state:
        st.session_state["rpw_memory"] = session.get("memory_text") or ""
    text = st.text_area(
        "What do you remember?",
        height=150,
        placeholder=EXAMPLE,
        key="rpw_memory",
    )
    session["memory_text"] = text
    columns = st.columns(2)
    with columns[0]:
        if st.button("Back to photos"):
            session["step"] = "library"
            st.rerun()
    with columns[1]:
        if st.button("Read this memory", type="primary", disabled=not text.strip()):
            _read_memory(session, text)
    if session.get("memory_error"):
        st.error(session["memory_error"])
        if session.get("memory_detail"):
            with st.expander("Technical detail"):
                st.write(session["memory_detail"])


def _read_memory(session: dict, text: str) -> None:
    if not session.get("privacy_accepted"):
        session["memory_error"] = "Confirm the privacy notice before anything is sent."
        session["memory_detail"] = ""
        st.rerun()
    try:
        session["memory"] = interpret_memory(text, complete_text)
        session["memory_error"] = ""
        session["memory_detail"] = ""
        session["browsing_without_rank"] = False
        session["analysis_error"] = ""
        session["step"] = "clues"
    except ProviderError as exc:
        session["memory"] = None
        session["memory_error"] = public_message(exc)
        session["memory_detail"] = public_detail(str(exc))
    except Exception:
        session["memory"] = None
        session["memory_error"] = "The description could not be read. No clues were invented."
        session["memory_detail"] = ""
    st.rerun()


def render_clues(session: dict, on_search) -> None:
    if session.get("analysis_error"):
        st.error(session["analysis_error"])
        if session.get("analysis_detail"):
            with st.expander("Technical detail"):
                st.write(session["analysis_detail"])
    memory = session.get("memory") or {}
    st.markdown('<p class="rp-section">Here is what we caught</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-copy">Check this before the photos are sent. Uncertain details stay uncertain.</p>',
        unsafe_allow_html=True,
    )
    render_clue_groups(memory)
    if memory.get("missing"):
        st.caption("Not in the description: " + ", ".join(memory["missing"]))
    columns = st.columns(2)
    with columns[0]:
        if st.button("Edit the description"):
            session["step"] = "memory"
            st.rerun()
    if memory.get("no_useful_clues"):
        st.warning("That description does not yet have a detail that can rank photos. Add something you remember seeing, or look through the photos without a ranking.")
        if st.button("Show photos without ranking"):
            session["browsing_without_rank"] = True
            session["step"] = "results"
            session["analysis_error"] = ""
            st.rerun()
        return
    st.markdown(
        '<div class="rp-notice"><p>Searching sends the photos in this session to Groq so each one can be described. They are still not saved into this project.</p></div>',
        unsafe_allow_html=True,
    )
    if st.button("Search these photos", type="primary"):
        on_search(session)
