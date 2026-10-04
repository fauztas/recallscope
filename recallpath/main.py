"""RecallPath — find a remembered photo by recognising it."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import time

import streamlit as st

from recallpath.components.candidate_grid import render_candidates, render_session_log
from recallpath.components.memory_step import render_clues, render_memory
from recallpath.components.success_state import render_absent, render_success
from recallpath.components.upload_step import render_upload
from recallpath.services.image_analyser import analyse_photos, groq_vision_complete
from recallpath.services.retriever import rank_collection
from recallpath.utils.config import max_images_per_request
from recallpath.utils.diagnostics import note_search_started
from recallpath.utils.errors import ProviderError, public_detail, public_message
from recallpath.utils.narrowing import new_view
from recallpath.utils.session_store import fresh_session
from recallpath.utils.styles import STYLES


def _reset() -> None:
    for key in list(st.session_state.keys()):
        if key == "rp" or str(key).startswith("rpw_"):
            del st.session_state[key]
    st.session_state.rp = fresh_session()
    st.rerun()


def _header() -> None:
    left, right = st.columns([4, 1])
    with left:
        st.markdown(
            """
            <p class="rp-mark">RecallPath</p>
            <p class="rp-tag">Find a photo from what you remember</p>
            <p class="rp-fine">A prototype for trying a search idea. Not a Google product.</p>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Remove my photos"):
            _reset()


def _search(session: dict) -> None:
    if not session.get("privacy_accepted"):
        session["analysis_error"] = "Confirm the privacy notice before photos are sent."
        session["analysis_detail"] = ""
        return
    progress = st.progress(0.0)
    label = st.empty()

    def on_progress(done: int, total: int) -> None:
        fraction = 0 if not total else done / total
        progress.progress(min(max(fraction, 0.0), 1.0))
        label.caption(f"Looking at the photos… {done} of {total}")

    try:
        outcome = analyse_photos(
            session["photos"],
            groq_vision_complete,
            batch_size=max_images_per_request(),
            on_progress=on_progress,
        )
    except ProviderError as exc:
        session["analysis_error"] = public_message(exc)
        session["analysis_detail"] = public_detail(str(exc))
        st.rerun()
        return
    except Exception:
        session["analysis_error"] = "The photos could not be analysed. No descriptions were invented."
        session["analysis_detail"] = ""
        st.rerun()
        return

    ready = any(
        isinstance(photo.get("analysis"), dict) and photo["analysis"].get("analysis_status") in {"ok", "weak", "failed"}
        for photo in session["photos"]
    )
    session["analysis_error"] = outcome.get("message") or ""
    session["analysis_detail"] = public_detail(outcome.get("detail") or "")
    if not ready and outcome.get("halt"):
        st.rerun()
        return
    note_search_started(session["diagnostics"], time.time())
    session["browsing_without_rank"] = False
    session["view"] = new_view()
    session["open_photo_id"] = None
    session["step"] = "results"
    session["flash"] = ""
    st.rerun()


def _refresh_ranking(session: dict) -> None:
    if session.get("browsing_without_rank"):
        session["ranked"] = rank_collection({"no_useful_clues": True}, session["photos"], [])
        return
    session["ranked"] = rank_collection(
        session.get("memory") or {},
        session["photos"],
        session["view"].get("recognition_clues") or [],
    )


def main() -> None:
    st.set_page_config(
        page_title="RecallPath",
        page_icon="🖼️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(STYLES, unsafe_allow_html=True)
    if "rp" not in st.session_state:
        st.session_state.rp = fresh_session()
    session = st.session_state.rp
    _header()
    step = session.get("step") or "library"
    if step == "library":
        render_upload(session)
    elif step == "memory":
        render_memory(session)
    elif step == "clues":
        render_clues(session, _search)
    elif step == "results":
        _refresh_ranking(session)
        render_candidates(session, time.time())
        render_session_log(session["diagnostics"])
        if st.button("Change the description"):
            session["step"] = "memory"
            st.rerun()
    elif step == "success":
        render_success(session)
    elif step == "absent":
        render_absent(session)
    else:
        session["step"] = "library"
        st.rerun()


if __name__ == "__main__":
    main()
