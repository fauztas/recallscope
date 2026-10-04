"""RecallPath settings.

Model ids live only in this module. Other modules read TEXT_MODEL and VISION_MODEL.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")

MAX_PHOTOS = 12
MAX_EDGE_PX = 1280
JPEG_QUALITY = 82
TEXT_TIMEOUT_SECONDS = 45.0
VISION_TIMEOUT_SECONDS = 70.0
TEXT_MAX_TOKENS = 1500
VISION_MAX_TOKENS = 1200

_PLACEHOLDERS = ("your_groq", "paste_your", "your_api_key", "changeme")


def _setting(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


TEXT_MODEL = _setting("RECALLPATH_TEXT_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = _setting("RECALLPATH_VISION_MODEL", "qwen/qwen3.8-27b")


def max_images_per_request() -> int:
    """Vision batches never exceed 3 images, even if the environment asks for more."""
    raw = os.getenv("RECALLPATH_MAX_IMAGES_PER_REQUEST", "").strip()
    if raw.isdigit():
        return max(1, min(3, int(raw)))
    return 3


def get_groq_api_key() -> str:
    """Return the configured key, or an empty string. Never log the value."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        return api_key
    try:
        import streamlit as st

        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            secret_value = str(st.secrets["GROQ_API_KEY"]).strip()
            if secret_value:
                return secret_value
    except Exception:
        return ""
    return ""


def is_groq_configured() -> bool:
    key = get_groq_api_key()
    if not key or len(key) <= 10:
        return False
    lowered = key.lower()
    if any(marker in lowered for marker in _PLACEHOLDERS) or lowered.endswith("_here"):
        return False
    return True
