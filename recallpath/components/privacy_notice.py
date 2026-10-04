"""Privacy copy shown before any photo is analysed."""

import streamlit as st

DISCLOSURE = """
<p class="rp-kicker">Before anything is analysed</p>
<p>The description you type, and the photos you add, are sent to <strong>Groq</strong> — the AI service configured for this prototype — so it can sort your memory and describe the photos.</p>
<p>Photos stay in this browser session only. They are not saved into this project, its research files, or a database. Use <strong>Remove my photos</strong> to clear them here.</p>
<p>Groq's own terms still apply to what is sent. This prototype does not control Groq's logs.</p>
"""


def render_privacy(session: dict) -> None:
    st.markdown(f'<div class="rp-notice">{DISCLOSURE}</div>', unsafe_allow_html=True)
    accepted = st.checkbox(
        "I understand my photos and description will be sent to Groq for analysis.",
        key="rpw_privacy",
    )
    session["privacy_accepted"] = bool(accepted)
