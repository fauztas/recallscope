"""RecallPath presentation. Scoped to this app and not applied through a shared Streamlit config."""

STYLES = """
<style>
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  [data-testid="stToolbar"],
  footer,
  #MainMenu {
    display: none;
  }
  .stApp {
    background: #f4efe8;
    color: #1f1a17;
  }
  .stApp header[data-testid="stHeader"] {
    background: transparent;
  }
  .main .block-container {
    max-width: 1040px;
    padding-top: 1.2rem;
    padding-bottom: 4rem;
  }
  .rp-mark {
    font-size: 1.7rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin: 0;
  }
  .rp-tag {
    color: #6d6258;
    margin: 0.1rem 0 0;
  }
  .rp-fine {
    color: #8a7d72;
    font-size: 0.85rem;
    margin: 0.35rem 0 0.8rem;
  }
  .rp-notice {
    background: #fffdf9;
    border: 1px solid #eadfD2;
    border-radius: 18px;
    padding: 0.9rem 1rem 0.2rem;
    margin-bottom: 0.6rem;
  }
  .rp-kicker {
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #8a5a3a;
    font-weight: 700;
    margin: 0 0 0.35rem;
  }
  .rp-section {
    font-size: 1.35rem;
    font-weight: 680;
    letter-spacing: -0.02em;
    margin: 0.2rem 0 0.3rem;
  }
  .rp-copy {
    color: #4e453f;
    margin-top: 0;
  }
  .rp-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.3rem 0 0.8rem;
  }
  .rp-chip {
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    font-size: 0.92rem;
    line-height: 1.35;
  }
  .rp-stated { background: #e5f2e6; color: #1d4a28; }
  .rp-hedged { background: #f8efd4; color: #6a4b12; }
  .rp-inferred { background: #ece6f6; color: #4c3b72; }
  .rp-pill {
    display: inline-block;
    background: #b4532a;
    color: white;
    border-radius: 999px;
    padding: 0.12rem 0.55rem;
    font-size: 0.78rem;
    font-weight: 700;
  }
  .rp-reason {
    color: #3f3732;
    min-height: 2.6rem;
  }
  .stApp, .stApp p, .stApp label, .stApp li {
    color: #1f1a17;
  }
  [data-testid="stCaptionContainer"],
  [data-testid="stCaptionContainer"] * {
    color: #5e554e !important;
  }
  [data-testid="stCheckbox"] label,
  [data-testid="stCheckbox"] p {
    color: #1f1a17 !important;
  }
  textarea, input[type="text"] {
    color: #1f1a17 !important;
    background: #fffdf9 !important;
  }
  [data-testid="stFileUploader"] section {
    background: #fffdf9 !important;
    border: 1px dashed #c8b8a6 !important;
  }
  [data-testid="stFileUploader"] section,
  [data-testid="stFileUploader"] section * {
    color: #1f1a17 !important;
  }
  button[data-testid="stBaseButton-secondary"] {
    background: #fffdf9 !important;
    color: #1f1a17 !important;
    border: 1px solid #d9cfc3 !important;
  }
  button[data-testid="stBaseButton-secondary"]:disabled {
    color: rgba(31, 26, 23, 0.45) !important;
    background: #f3eee8 !important;
  }
  button[data-testid="stBaseButton-primary"] {
    background: #b4532a !important;
    color: #ffffff !important;
    border: 1px solid #b4532a !important;
  }
  button[data-testid="stBaseButton-primary"] * {
    color: #ffffff !important;
  }
  button[data-testid="stBaseButton-primary"]:disabled {
    opacity: 0.45 !important;
  }
  div.stButton > button {
    border-radius: 999px;
    width: 100%;
  }
  @media (max-width: 800px) {
    div[data-testid="stHorizontalBlock"] {
      flex-wrap: wrap;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
      width: 100% !important;
      flex: 1 1 100% !important;
      min-width: 100% !important;
    }
  }
</style>
"""
