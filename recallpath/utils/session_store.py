"""In-memory session shape for RecallPath. Nothing here is written to disk."""

from recallpath.utils.diagnostics import fresh_diagnostics
from recallpath.utils.narrowing import new_view


def fresh_session() -> dict:
    return {
        "step": "library",
        "photos": [],
        "privacy_accepted": False,
        "uploader_nonce": 0,
        "memory_text": "",
        "memory": None,
        "memory_error": "",
        "analysis_error": "",
        "analysis_detail": "",
        "flash": "",
        "library_notes": [],
        "ranked": [],
        "view": new_view(),
        "diagnostics": fresh_diagnostics(),
        "open_photo_id": None,
        "browsing_without_rank": False,
    }
