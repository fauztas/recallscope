"""Photo library step."""

import streamlit as st

from recallpath.components.privacy_notice import render_privacy
from recallpath.utils.config import MAX_PHOTOS, is_groq_configured
from recallpath.utils.images import add_photos


def render_upload(session: dict) -> None:
    st.markdown('<p class="rp-section">Add a few photos</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rp-copy">Choose a small set from the collection you want to search. Twelve is the maximum for one session.</p>',
        unsafe_allow_html=True,
    )
    if not is_groq_configured():
        st.warning("The Groq key is not configured. You can still add photos. They will not be analysed, and no results will be invented.")
    render_privacy(session)
    uploads = st.file_uploader(
        "Photos",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key=f"rpw_upload_{session['uploader_nonce']}",
        label_visibility="collapsed",
    )
    if st.button("Add photos", disabled=not uploads):
        incoming = [{"filename": item.name, "data": item.getvalue()} for item in uploads]
        session["library_notes"] = add_photos(session["photos"], incoming)
        session["uploader_nonce"] += 1
        session["ranked"] = []
        st.rerun()
    for note in session.get("library_notes") or []:
        st.caption(note)
    count = len(session["photos"])
    st.caption(f"{count} of {MAX_PHOTOS} photos in this session.")
    if session["photos"]:
        columns = st.columns(2)
        for index, photo in enumerate(list(session["photos"])):
            with columns[index % 2]:
                st.image(photo["bytes"], use_container_width=True)
                st.caption(photo["filename"])
                if st.button("Remove", key=f"rpw_remove_{photo['id']}"):
                    session["photos"] = [item for item in session["photos"] if item["id"] != photo["id"]]
                    session["ranked"] = []
                    st.rerun()
    ready = bool(session["photos"]) and session["privacy_accepted"]
    if st.button("Describe the photo", type="primary", disabled=not ready):
        session["step"] = "memory"
        session["flash"] = ""
        st.rerun()
    if session["photos"] and not session["privacy_accepted"]:
        st.caption("Confirm the notice above before continuing. Photos are not sent until you do.")
