"""Visual candidate grid and recognition actions."""

import streamlit as st

from recallpath.components.feedback_bar import render_feedback
from recallpath.components.memory_step import render_clue_groups
from recallpath.utils.diagnostics import (
    format_duration,
    mark_found,
    note_closer,
    note_inspection,
    note_not_sure,
    note_not_this,
)
from recallpath.utils.narrowing import hide_photo, mark_closer, visible_ids
from recallpath.utils.scoring import recognition_clues_from_photo


def _photo_map(session: dict) -> dict:
    return {photo["id"]: photo for photo in session["photos"]}


def _ranked_map(session: dict) -> dict:
    return {item["photo_id"]: item for item in session.get("ranked") or []}


def render_candidates(session: dict, now: float) -> None:
    if session.get("analysis_error"):
        st.warning(session["analysis_error"])
        if session.get("analysis_detail"):
            with st.expander("Technical detail"):
                st.write(session["analysis_detail"])
    if not session.get("browsing_without_rank") and session.get("memory"):
        with st.expander("Clues used for this search", expanded=False):
            render_clue_groups(session["memory"])
    render_feedback(session)
    photos = _photo_map(session)
    ranked = _ranked_map(session)
    shown = [ranked[photo_id] for photo_id in visible_ids(session["ranked"], session["view"]) if photo_id in ranked]
    open_id = session.get("open_photo_id")
    if open_id and open_id in photos and open_id in ranked:
        _render_detail(session, photos[open_id], ranked[open_id], now)
    if not shown:
        st.warning("Every photo is hidden for now. Choose None of these / broaden, or Undo, to bring them back.")
        return
    columns = st.columns(2)
    for index, item in enumerate(shown):
        photo = photos.get(item["photo_id"])
        if photo is None:
            continue
        with columns[index % 2]:
            _render_card(session, photo, item, now)


def _render_card(session: dict, photo: dict, item: dict, now: float) -> None:
    with st.container(border=True):
        st.image(photo["bytes"], use_container_width=True)
        if item["group"] == "closer":
            st.markdown('<span class="rp-pill">Closer</span>', unsafe_allow_html=True)
        elif item["group"] == "unchecked":
            st.markdown('<span class="rp-pill">Not checked</span>', unsafe_allow_html=True)
        st.markdown(f'<p class="rp-reason">{_escape(item["reason"])}</p>', unsafe_allow_html=True)
        _actions(session, photo, item, now, compact=True)
        with st.expander("Why this is here"):
            for line in item["explanation"]:
                st.write(line)


def _render_detail(session: dict, photo: dict, item: dict, now: float) -> None:
    st.image(photo["bytes"], use_container_width=True)
    st.markdown(f'<p class="rp-reason">{_escape(item["reason"])}</p>', unsafe_allow_html=True)
    _actions(session, photo, item, now, compact=False)
    if st.button("Close photo"):
        session["open_photo_id"] = None
        st.rerun()


def _actions(session: dict, photo: dict, item: dict, now: float, compact: bool) -> None:
    photo_id = photo["id"]
    suffix = "card" if compact else "detail"
    first, second = st.columns(2)
    with first:
        if st.button("This is the photo", key=f"rpw_found_{suffix}_{photo_id}", type="primary"):
            mark_found(session["diagnostics"], photo_id, now)
            session["open_photo_id"] = photo_id
            session["step"] = "success"
            session["flash"] = ""
            st.rerun()
    with second:
        if st.button("This looks closer", key=f"rpw_closer_{suffix}_{photo_id}"):
            clues = recognition_clues_from_photo(photo)
            if clues:
                mark_closer(session["view"], photo_id, clues)
                note_closer(session["diagnostics"])
                session["flash"] = "Looking for photos that share more with that one. The others are still recoverable."
            else:
                session["flash"] = "That photo does not have a clear reading yet, so nothing else was hidden."
            st.rerun()
    third, fourth = st.columns(2)
    with third:
        if st.button("Not this", key=f"rpw_hide_{suffix}_{photo_id}"):
            hide_photo(session["view"], photo_id)
            note_not_this(session["diagnostics"])
            if session.get("open_photo_id") == photo_id:
                session["open_photo_id"] = None
            session["flash"] = "Hidden for now. Undo or broaden brings it back."
            st.rerun()
    with fourth:
        if st.button("Not sure", key=f"rpw_unsure_{suffix}_{photo_id}"):
            note_not_sure(session["diagnostics"])
            session["flash"] = "Nothing was ruled out."
            st.rerun()
    if compact and st.button("View", key=f"rpw_view_{photo_id}"):
        if session.get("open_photo_id") != photo_id:
            note_inspection(session["diagnostics"])
        session["open_photo_id"] = photo_id
        st.rerun()


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_session_log(diagnostics: dict) -> None:
    with st.expander("Session log"):
        st.caption("Recorded for this session only. Not a research result.")
        found = diagnostics.get("found")
        found_label = {True: "Found", False: "Not found", None: "Still looking"}.get(found, "Still looking")
        st.write(f"Target: {found_label}")
        st.write(f"Time to target: {format_duration(diagnostics.get('time_to_target_seconds'))}")
        st.write(f"Narrowing actions: {diagnostics.get('narrowing_interactions', 0)}")
        st.write(f"Photos opened: {diagnostics.get('candidate_inspections', 0)}")
        st.write(f"Not sure: {diagnostics.get('not_sure_count', 0)}")
        st.write(f"None of these / broaden: {diagnostics.get('broaden_count', 0)}")
        st.write(f"Undo: {diagnostics.get('undo_count', 0)}")
