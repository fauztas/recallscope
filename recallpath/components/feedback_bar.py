"""Global recovery actions for the candidate step."""

import streamlit as st

from recallpath.utils.diagnostics import note_broaden, note_undo
from recallpath.utils.narrowing import broaden, undo, visible_ids


def render_feedback(session: dict) -> None:
    view = session["view"]
    ranked = session.get("ranked") or []
    hidden = len(view["hidden_ids"])
    visible = len(visible_ids(ranked, view))
    if view["narrowed"] or hidden:
        st.caption(f"Showing {visible} photos. {hidden} hidden for now. Nothing has been deleted.")
    else:
        st.caption("Showing this session's photos, closest first. Nothing has been deleted.")
    if session.get("flash"):
        st.info(session["flash"])
    left, middle, right = st.columns(3)
    with left:
        if st.button("None of these / broaden"):
            result = broaden(view)
            note_broaden(session["diagnostics"], result)
            if result == "already_full":
                repeats = view["repeated_full_set"]
                if repeats >= 2:
                    session["flash"] = (
                        "This is already every photo you added. It may not be in this set. "
                        "You can undo, change the description, or say it is not here."
                    )
                else:
                    session["flash"] = "This is already the full set. The photo may not be among the ones you added."
            else:
                session["flash"] = "Showing the full set again."
            st.rerun()
    with middle:
        if st.button("Undo", disabled=not view["history"]):
            if undo(view):
                note_undo(session["diagnostics"])
                session["flash"] = "Brought back the previous set."
            st.rerun()
    with right:
        if st.button("Not in this collection"):
            from recallpath.utils.diagnostics import mark_absent

            mark_absent(session["diagnostics"])
            session["step"] = "absent"
            session["flash"] = ""
            st.rerun()
