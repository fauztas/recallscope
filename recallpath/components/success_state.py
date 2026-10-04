"""End states for a found photo and a photo that is not in the session."""

import streamlit as st

from recallpath.components.candidate_grid import render_session_log
from recallpath.utils.diagnostics import fresh_diagnostics
from recallpath.utils.narrowing import new_view


def render_success(session: dict) -> None:
    photo = _selected(session)
    st.markdown('<p class="rp-section">This is the one</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-copy">You recognised it from the photos, without needing a perfect search phrase.</p>',
        unsafe_allow_html=True,
    )
    if photo is not None:
        st.image(photo["bytes"], use_container_width=True)
    render_session_log(session["diagnostics"])
    _follow_up(session)


def render_absent(session: dict) -> None:
    st.markdown('<p class="rp-section">Not in these photos</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-copy">Then it is not in the photos added for this session. You can add different photos or describe another memory.</p>',
        unsafe_allow_html=True,
    )
    render_session_log(session["diagnostics"])
    _follow_up(session)


def _selected(session: dict):
    photo_id = session["diagnostics"].get("found_photo_id")
    for photo in session["photos"]:
        if photo["id"] == photo_id:
            return photo
    return None


def _follow_up(session: dict) -> None:
    left, right = st.columns(2)
    with left:
        if st.button("Describe a different photo"):
            session["step"] = "memory"
            session["memory_text"] = ""
            session["memory"] = None
            session["memory_error"] = ""
            session["memory_detail"] = ""
            session["analysis_error"] = ""
            session["analysis_detail"] = ""
            session["flash"] = ""
            session["ranked"] = []
            session["view"] = new_view()
            session["diagnostics"] = fresh_diagnostics()
            session["open_photo_id"] = None
            session["browsing_without_rank"] = False
            if "rpw_memory" in st.session_state:
                del st.session_state["rpw_memory"]
            st.rerun()
    with right:
        if st.button("Back to these photos"):
            session["step"] = "results"
            st.rerun()
