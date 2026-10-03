"""
Configuration and Environment Management for RecallScope
Handles optional environment variables gracefully without requiring API keys during Phase 0.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load local .env if it exists
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)


def get_api_key() -> str:
    """
    Safely retrieve GEMINI_API_KEY from environment variables or Streamlit secrets.
    Returns None if not configured. Never throws an error or requires an API key in Phase 0.
    """
    # 1. Check standard environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    # 2. Check Streamlit secrets if running inside Streamlit
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    return ""


def is_api_key_configured() -> bool:
    """Check if an API key is available without exposing its value."""
    key = get_api_key()
    return bool(key and len(key.strip()) > 0)


def get_groq_api_key() -> str:
    """
    Retrieve GROQ_API_KEY from the environment or Streamlit secrets.
    Returns an empty string when it is missing. Never prints the key.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            secret_value = str(st.secrets["GROQ_API_KEY"]).strip()
            if secret_value:
                return secret_value
    except Exception:
        pass

    return ""


def is_groq_configured() -> bool:
    """Check that a real Groq key is configured, without exposing the value."""
    key = get_groq_api_key()
    if not key:
        return False
    lowered = key.lower()
    placeholder_markers = ("your_groq", "paste_your", "your_api_key", "changeme")
    if any(marker in lowered for marker in placeholder_markers) or lowered.endswith("_here"):
        return False
    return len(key) > 10


def check_dataset_status() -> dict:
    """
    Check availability of research dataset files without loading or altering them.
    Supports primary public_evidence_raw.csv and original test batch1.
    """
    data_dir = BASE_DIR / "data"
    primary_raw = data_dir / "public_evidence_raw.csv"
    batch1_raw = data_dir / "public_evidence_raw_batch1.csv"

    return {
        "data_dir_exists": data_dir.exists(),
        "primary_raw_exists": primary_raw.exists(),
        "primary_raw_path": str(primary_raw) if primary_raw.exists() else None,
        "batch1_exists": batch1_raw.exists(),
        "batch1_path": str(batch1_raw) if batch1_raw.exists() else None,
    }

