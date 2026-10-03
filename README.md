# RecallScope

**AI-Powered Discovery Engine for Google Photos Retrieval Research**

RecallScope is an evidence-grounded AI discovery engine for investigating vague-memory photo retrieval problems.

When people know a photo exists in their library but cannot precisely describe it, where does retrieval break despite them remembering parts of the photo or experience? RecallScope analyzes genuine public evidence to investigate where and why these journeys fail.

---

## Current Status

- **Phase:** `Phase 11 — Deployment Preparation` (Active). Phases 0–10 are complete.
- **Status:** The Discovery Engine is the evaluator-facing view. Quality & Integrity remains **8 PASS, 2 WARNING, 0 FAILURES**. Those warnings are intentional. Research files are unchanged. The model runs only when Ask or Challenge is clicked.
- **Primary Research Dataset:** `data/public_evidence_raw.csv` (24 genuine public records, preserved read-only).
- **Relevance Dataset:** `data/public_evidence_relevance.csv` (preserved read-only).
- **Classification Dataset:** `data/public_evidence_classified.csv` (created by Phase 3; not a replacement for the raw evidence).
- **Research Analysis:** `data/research_analysis.json` (calculated from the audited classifications).
- **Test Batch Dataset:** `data/public_evidence_raw_batch1.csv` (10-record initial test batch, preserved untouched).
- **API Key:** The app reads `GROQ_API_KEY` from the environment, a local `.env` file, or Streamlit secrets. Do not commit `.env` or a real key.

This corpus is an **interim public-evidence corpus**. It is not representative of all Google Photos users. Counts in the app are not population prevalence.

## What the Discovery Engine does

RecallScope studies public posts about finding a photo someone remembers but cannot describe precisely. The saved workflow is:

Public evidence → relevance filtering → AI structured classification → cross-record pattern analysis → evidence-grounded exploration → challenge and contradiction testing.

The model structures relevant posts, looks for candidate patterns, answers questions from retrieved records, and searches for evidence that supports and weakens a proposed insight. It does not invent missing user details, treat Unknown as No, make a final product decision, or turn a corpus count into population prevalence. Every finding can be traced from a record ID to the original wording and source URL.

---

## Project Structure

```text
Faujiyah/
├── app/
│   ├── main.py                     # Main Streamlit application entry point
│   └── utils/
│       ├── __init__.py
│       ├── config.py               # Safe environment & dataset configuration
│       └── data_loader.py          # Reusable dataset loading and quality validation
├── data/
│   ├── public_evidence_raw.csv     # Primary raw public evidence (24 records, immutable)
│   └── public_evidence_raw_batch1.csv # Original test batch (10 records, immutable)
├── docs/
│   ├── problemStatement.txt        # Original project brief
│   ├── problemStatement.md         # Master context document
│   ├── architecture.md             # Technical architecture blueprint
│   ├── implementation-plan.md      # 12-phase implementation plan
│   └── edge-case.md                # Edge case & research integrity guide
├── .env.example                    # Template for future environment variables
├── .gitignore                      # Git ignore file
├── requirements.txt                # Python project dependencies
└── README.md                       # Project overview and setup instructions
```

---

## Beginner Guide: How to Run RecallScope Locally

### Step 1: Open a terminal in the project folder
Open a terminal in the folder that contains `app/`, `data/`, and `requirements.txt`. Paths inside the app are relative to that folder, so the same command works on another computer.

### Step 2: Install dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Add your own Groq key
Copy `.env.example` to `.env` in the project folder and replace the placeholder:

```text
GROQ_API_KEY=your_groq_api_key_here
```

Use your own key. Do not commit `.env`. Browsing saved research still works if the key is missing. Ask the Evidence and Challenge an Insight then say the key is not configured and do not invent an answer. The key is never shown in the interface.

### Step 4: Start Streamlit
From the project folder:

```powershell
streamlit run app/main.py
```

### Step 5: Open the local page
Streamlit prints a local URL, usually:

```text
http://localhost:8501
```

To stop the application, press `Ctrl + C` in the terminal.

## Deployment

RecallScope is not publicly deployed yet. The simplest host for this Streamlit app is Streamlit Community Cloud. That host needs a GitHub account and a repository. Those steps are manual and have not been done from this project.

When you are ready:

1. Create a GitHub account if you do not have one.
2. Create a new repository. Do not upload `.env`.
3. Push this project folder. Confirm `.env` is not in the repository.
4. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
5. Create an app with main file path `app/main.py`.
6. In the app secrets, add only your own key:

```toml
GROQ_API_KEY = "paste-your-own-key-here"
```

7. Deploy, then open the URL Streamlit gives you and confirm the Discovery Engine loads.

The saved research pages work from the files in `data/`. A missing key does not hide those pages.
