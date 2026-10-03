# RecallScope — Technical Architecture Document

> **Document Type:** System Architecture & Technical Design  
> **Target Audience:** Beginner Developer / Product Manager  
> **Status:** Approved Blueprint for Implementation  
> **Design Philosophy:** Simplest Reliable Architecture (No over-engineering, fast iteration, high traceability)

---

## 1. Project Architecture Overview

RecallScope is an exploratory research tool designed to analyze approximately 200–250 genuine public conversations about vague-memory photo retrieval. 

To keep the system beginner-friendly, fast to build, and cheap to run, the system uses a **lightweight, file-based architecture**:
- **Programming Language:** Python (simple, readable, and standard for data and AI).
- **User Interface:** Streamlit (an interactive web interface built entirely in Python without needing HTML/CSS/JavaScript or complex frontend frameworks).
- **Data Storage:** Standard CSV files stored locally on disk (no SQL databases, no cloud data warehouses, no Docker).
- **Data Manipulation:** Pandas (fast tabular data filtering, aggregation, and search).
- **Visualizations:** Native Streamlit metric cards and charts (or lightweight Plotly charts).
- **AI Engine:** A single direct LLM API connection (used for batch classification of raw records and answering grounded user research questions).

Everything runs inside a single Python environment. There is no separate backend/frontend split, no login authentication wall, and no vector database.

```text
+-----------------------------------------------------------------+
|                         USER INTERFACE                          |
|                       (Streamlit Web App)                       |
|   [Overview]  [Failures]  [Memory]  [Evidence]  [Q&A]  [Challenge]  |
+--------------------------------+--------------------------------+
                                 |
                                 v
+-----------------------------------------------------------------+
|                       APPLICATION LOGIC                         |
|      (Pandas Data Filtering, Query Formatting, Prompt Assembly)  |
+---------------+--------------------------------+----------------+
                |                                |
                v                                v
+-------------------------------+  +------------------------------+
|          DATA LAYER           |  |           AI LAYER           |
|  - raw_evidence.csv           |  |  - LLM API (Classification)  |
|  - processed_evidence.csv     |  |  - LLM API (Grounded Q&A)    |
+-------------------------------+  +------------------------------+
```

---

## 2. Data Layer

The entire dataset consists of ~200–250 public records. At this scale, standard CSV files are faster, simpler, and far easier to inspect and audit than an external database.

### 2.1. Raw Dataset (`data/raw_evidence.csv`)
The raw dataset stores collected public records in their original state. **This file is treated as immutable (read-only once saved)** to guarantee that raw evidence is never lost, overwritten, or modified.

**Fields preserved in `raw_evidence.csv`:**
- `record_id` (string, unique primary key, e.g., `REC_001`, `REC_002`)
- `source` (string, e.g., `Reddit`, `Google Help`, `Play Store`, `App Store`, `YouTube`)
- `date` (string/date, e.g., `2024-03-15`, or `Unknown` if missing)
- `original_text` (string, exact verbatim user text)
- `source_url` (string, direct public URL to the post or thread)

### 2.2. Processed Dataset (`data/processed_evidence.csv`)
A second CSV file is created by the data processing and AI classification pipeline. It copies all columns from the raw dataset and adds structured research classifications.

**Fields added in `processed_evidence.csv`:**
- `is_relevant` (string: `Relevant`, `Irrelevant`)
- `relevance_reason` (string, why this record is or isn't about photo retrieval)
- `retrieval_intent` (string, what the user was seeking to achieve)
- `photo_type` (string, category of photo sought, e.g., `Receipt`, `Family event`, `Pet`)
- `retrieval_scenario` (string, context surrounding the search)
- `remembered_clues` (string, clues recalled by user, e.g., color, place, time)
- `forgotten_clues` (string, details the user explicitly forgot)
- `search_behaviour` (string, query formulation or keywords used)
- `reformulation_behaviour` (string, how searches were altered after failure)
- `manual_browsing` (string, scrolling, timeline scrubbing, album checks)
- `workaround` (string, actions taken after failure, e.g., asked friend, gave up)
- `failure_stage` (string, mapped strictly to taxonomy: `F1` to `F8`)
- `failure_reason` (string, concise justification from evidence)
- `retrieval_outcome` (string: `Success`, `Partial Success`, `Failure`, `Abandoned`)
- `evidence_strength` (string: `High`, `Medium`, `Low`, `Unknown`)
- `candidate_issues` (string: e.g., `Too many candidates`, `Visually similar`, `None`)

By keeping `raw_evidence.csv` and `processed_evidence.csv` separate, we can re-run or refine classifications at any time without corrupting the original evidence.

---

## 3. Data Processing Layer

The data processing layer handles data loading, cleaning, validation, and preparation before classification and analysis.

```text
Raw CSV -> Load into Pandas -> Clean & Deduplicate -> Filter Relevance -> Prepare for AI
```

### Steps:
1. **Loading:** Load `raw_evidence.csv` safely into a Pandas DataFrame using `pandas.read_csv()`.
2. **Cleaning:**
   - Strip leading and trailing whitespace from text fields.
   - Clean up non-standard line breaks or encoding artifacts.
   - Standardize date formats (e.g., `YYYY-MM-DD` or `Unknown`).
3. **Deduplication Check:**
   - Check for duplicate `source_url` values.
   - Check for near-identical `original_text` to eliminate accidental duplicates.
   - Ensure `record_id` is sequential and strictly unique.
4. **Missing Information Check:**
   - If `source_url` or `source` is missing, flag the record for review.
   - If `date` is missing, set value to `Unknown` without discarding the record.
5. **Relevance Filtering:**
   - Scan records for unrelated support issues (backup failure, deleted photos, storage quota warnings, upload errors, sync issues).
   - If a record is purely an unrelated complaint with no retrieval attempt, classify it as `is_relevant = "Irrelevant"`.
   - If the record contains a genuine retrieval struggle (even if mixed with other complaints), mark it `is_relevant = "Relevant"`.
6. **Classification Batch Preparation:**
   - Slice only records that need initial or updated classification and format them for the AI classification layer.

---

## 4. AI Classification Layer

To avoid manual data entry fatigue across 200–250 records while preserving research rigor, an AI classification script processes relevant records against structured extraction guidelines.

### 4.1. Structured Taxonomy & Prompting
The LLM is prompted with strict instructions based on `docs/problemStatement.md`:
- Must map the failure stage to one of the 8 taxonomy stages:
  - `F1 — Recall Gap`
  - `F2 — Expression Gap`
  - `F3 — Interpretation Gap`
  - `F4 — Candidate Gap`
  - `F5 — Recognition Gap`
  - `F6 — Refinement Gap`
  - `F7 — Coverage / Indexing Gap`
  - `F8 — Unknown`
- **Mandatory Default:** If the evidence does not clearly support stages F1–F7, the LLM **must** output `F8 — Unknown`.
- **Extraction Rules:**
  - Never infer what the user did not say.
  - Separate raw quotes from interpretations.
  - Return clean JSON formatted fields.

### 4.2. Batch Execution & Saving
- The script iterates through unclassified rows.
- Sends each record with the prompt to the LLM API.
- Parses the structured JSON output into corresponding DataFrame columns.
- Writes the resulting records to `data/processed_evidence.csv`.
- Each classification retains its permanent `record_id`, ensuring complete traceability.

---

## 5. Analysis Layer

The analysis layer runs inside the Streamlit application using Pandas. It computes dynamic summaries, counts, and crosstabs directly from `data/processed_evidence.csv`.

### Key Metrics & Aggregations:
- **Total Corpus & Source Mix:** Total records collected, broken down by source platform (Reddit, Google Help, app stores, etc.).
- **Relevance Breakdown:** Count and percentage of Relevant vs. Irrelevant records.
- **Failure Stage Distribution:** Frequency count of each failure stage (F1 to F8).
- **Memory Patterns:** Frequency of remembered clues (e.g., person, setting, approximate year) vs. forgotten clues (exact date, album name, specific file name).
- **Post-Failure Behaviours:** Most frequent user workarounds and abandonment rates.
- **Candidate Evaluation:** Occurrence of visual similarity confusion, scrolling fatigue, or excessive candidate results.

### Research Integrity Warning:
The analysis layer explicitly renders a disclaimer on all summary charts:
> *"Frequencies in this dataset reflect directional signals from collected public conversations. They are NOT statistical population prevalence across all Google Photos users."*

---

## 6. User Interface Architecture

The Streamlit web application provides a clean, single-window dashboard organized into six dedicated sections accessible via a navigation sidebar.

```text
Sidebar Navigation
├── 1. Research Overview
├── 2. Failure Explorer
├── 3. Memory Explorer
├── 4. Evidence Explorer
├── 5. Ask the Evidence
└── 6. Challenge an Insight
```

### Page Breakdown:

#### A. Research Overview
- **Purpose:** Provide an executive snapshot of dataset health and progress.
- **Elements:**
  - KPI Cards: Total Records Collected, Relevant Records, Irrelevant Records, Active Sources.
  - Source Distribution Chart (bar chart of records per platform).
  - Relevant vs. Irrelevant Ratio.
  - Current Research Status Banner (e.g., highlighting that survey and interviews are ongoing).

#### B. Failure Explorer
- **Purpose:** Analyze where photo retrieval breaks down along the journey.
- **Elements:**
  - Interactive Filters: Filter by Failure Stage (F1–F8), Source, Photo Type.
  - Failure Stage Distribution Chart.
  - Failure Cards: Expandable cards showing failure reason, evidence strength, and the raw quote with its `record_id`.

#### C. Memory Explorer
- **Purpose:** Investigate what users remember versus what they forget when searching.
- **Elements:**
  - Clue Comparison: Side-by-side breakdown of Remembered Clues vs. Forgotten Clues.
  - Clue Category Filters (temporal, spatial, visual, social).
  - Verbatim excerpt drawer showing actual user memory statements.

#### D. Evidence Explorer
- **Purpose:** Give the Product Manager an auditable, searchable table of all collected records.
- **Elements:**
  - Search bar (keyword search across original texts).
  - Filter by Source, Relevance, and Failure Stage.
  - Data table displaying `record_id`, `source`, `date`, `failure_stage`, and truncated text.
  - "Inspect Record" detail view: Clicking any record displays the full verbatim text, original source URL, date, and all AI-extracted fields side-by-side.

#### E. Ask the Evidence
- **Purpose:** Allow the PM to ask natural-language questions about user retrieval problems.
- **Elements:**
  - Chat / Question input box.
  - Response area displaying grounded answers.
  - Citation tags listing supporting `record_id`s.
  - "View Cited Records" expander showing the verbatim evidence used for the answer.

#### F. Challenge an Insight
- **Purpose:** Actively combat confirmation bias by searching for evidence that contradicts, complicates, or limits an assumption.
- **Elements:**
  - Input field for entering a proposed hypothesis or feature belief (e.g., *"Users fail because they cannot remember dates"*).
  - Multi-column comparison displaying:
    - **Supporting Evidence** (records validating the hypothesis)
    - **Contradicting Evidence** (records where retrieval failed for completely different reasons)
    - **Complicating Nuances** (records showing mixed or unexpected factors)
    - **Insufficient / Inconclusive** (records with unclear evidence)
  - Explicit uncertainty summary.

---

## 7. "Ask the Evidence" Architecture

To keep the application simple, robust, and beginner-friendly, **we do NOT use a vector database** (e.g., Pinecone, Chroma, FAISS). 

### Why No Vector Database is Needed:
- The entire dataset is only ~200–250 records.
- In total, 250 records represent roughly 30,000–60,000 words.
- Modern LLMs (such as Google Gemini) feature context windows of hundreds of thousands to over 1,000,000 tokens.
- We can filter relevant records using simple Pandas keyword matching or pass the most relevant subset directly in the LLM prompt. This eliminates vector embeddings, indexing bugs, connection timeouts, and extra dependencies.

### Step-by-Step Q&A Flow:
```text
User Question
    │
    ▼
1. Filter Context
   (Pandas extracts relevant records; if broad question, takes all relevant records)
    │
    ▼
2. Assemble Prompt
   (System Prompt + Grounding Rules + Selected Record Texts + Record IDs + User Question)
    │
    ▼
3. Call LLM API
    │
    ▼
4. Enforce Strict Grounding Rules:
   - Answer ONLY using the provided records.
   - Every factual statement must cite [record_id].
   - If the answer cannot be determined from evidence, say:
     "The collected evidence does not contain sufficient information to answer this question."
    │
    ▼
5. Render in Streamlit UI
   (Answer text + clickable expanders to view verbatim cited records)
```

---

## 8. "Challenge an Insight" Architecture

The "Challenge an Insight" tool is an architectural counterweight to confirmation bias. When product teams believe a specific solution or root cause is obvious, this tool surfaces counter-evidence.

### Step-by-Step Flow:
1. **Researcher Input:** The user inputs an assumption (e.g., *"Users fail primarily because Google Photos search cannot understand natural descriptions"*).
2. **Context Assembly:** The system extracts the classified records and their failure reasons.
3. **Structured Challenge Prompt:** The LLM evaluates the hypothesis against the records and categorizes matching evidence into four buckets:
   - **Supports:** Evidence showing this exact barrier.
   - **Contradicts:** Evidence showing failure occurred despite description capability (e.g., candidate clutter, recognition failure, complete recall blank).
   - **Complicates:** Evidence showing hybrid problems (e.g., search understood the term, but OCR or visual indexing was inaccurate).
   - **Neutral / Insufficient:** Records that offer no stance on this assertion.
4. **Display:** Streamlit displays the 4 categories side-by-side with direct citations, forcing the researcher to acknowledge counter-evidence before reaching conclusions.

---

## 9. Research Traceability Architecture

Traceability is a core architectural requirement. No metric or summary statement may appear in the UI without an unbroken audit trail back to raw data.

```text
Dashboard Insight / Chart / Q&A Answer
   └── Cites [record_id] (e.g., REC_042)
          └── Linked to processed_evidence.csv
                 └── Linked to raw_evidence.csv
                        └── Direct Link: source_url (Public post URL)
```

### Traceability Rules:
1. **Charts:** Every chart bar or category displays the count of underlying records. Clicking or filtering isolates the exact `record_id` list.
2. **AI Answers:** Every claim generated in "Ask the Evidence" or "Challenge an Insight" includes bracketed citations like `[REC_015]`.
3. **Evidence Cards:** Every cited record can be expanded in the UI to display:
   - Verbatim user quote
   - Source platform name
   - Date
   - Direct clickable link to the live public thread (`source_url`)
   - AI classification fields and reasoning

---

## 10. Error and Uncertainty Handling

The system is designed to handle messy real-world qualitative data safely without crashing or producing misleading results:

| Potential Issue | Architectural Handling |
|---|---|
| **Missing Values** | If dates or optional metadata are missing, Pandas replaces them with `"Unknown"` or `"Not Recorded"`. The app never crashes on `NaN`. |
| **Irrelevant Records** | Flagged as `is_relevant = "Irrelevant"` with an explanation. Excluded from retrieval failure charts, but retained in the Overview to demonstrate sample filtering. |
| **Ambiguous Failure Stage** | Classified as `F8 — Unknown`. The prompt explicitly forbids the AI from forcing a classification when details are sparse. |
| **Duplicate Posts** | Filtered during data ingestion using Pandas `drop_duplicates(subset=['source_url'])` and text hash comparisons. |
| **AI Classification Uncertainty** | Tracked via `evidence_strength` (`High`, `Medium`, `Low`). Records with low confidence are visually tagged in the UI. |
| **LLM API Timeout or Network Failure** | Wrapped in standard Python `try / except` blocks. Displays a user-friendly Streamlit warning (`st.error("AI service temporarily unavailable. Please retry.")`) without crashing the application. |
| **Empty Filter Results** | If a user selects a combination of filters with zero matching records, Streamlit displays an informative callout (`st.info("No records match these criteria.")`) rather than a blank or broken screen. |
| **Unsupported User Questions** | The system prompt strictly prohibits speculation. If evidence is lacking, the LLM outputs a standard refusal message explaining the evidence gap. |

---

## 11. Proposed Project File Structure

Here is the simple, beginner-friendly file structure for the finished project:

```text
Faujiyah/
│
├── app/
│   ├── main.py                     # Main Streamlit app entry point & navigation
│   ├── pages/                      # Multi-page application views
│   │   ├── 1_overview.py           # Research Overview & dataset stats
│   │   ├── 2_failures.py           # Failure Stage Explorer (F1-F8)
│   │   ├── 3_memory.py             # Memory Explorer (Remembered vs Forgotten)
│   │   ├── 4_evidence.py           # Evidence Explorer (Searchable raw records)
│   │   ├── 5_ask_evidence.py       # Grounded Q&A with record citations
│   │   └── 6_challenge_insight.py  # Counter-evidence and bias checker
│   ├── utils/
│   │   ├── data_loader.py          # Pandas loader with @st.cache_data for speed
│   │   └── llm_helper.py           # Clean LLM API caller & grounding prompt builder
│   └── classify_pipeline.py        # Offline script to run AI classification on raw CSV
│
├── data/
│   ├── raw_evidence.csv            # Original immutable public records
│   └── processed_evidence.csv      # Cleaned dataset with AI classifications
│
├── docs/
│   ├── problemStatement.txt        # Original project brief
│   ├── problemStatement.md         # Master context document
│   └── architecture.md             # This technical architecture document
│
├── requirements.txt                # Minimal Python dependencies
└── README.md                       # Project overview and setup instructions
```

---

## 12. Deployment Approach

To make the application publicly testable with zero infrastructure hassle and no cost:

### Recommended Platform: **Streamlit Community Cloud**
- **Cost:** Free.
- **Complexity:** Beginner-friendly. No Docker, no server management, no Linux commands.
- **Workflow:**
  1. Push code and CSV files to a private or public GitHub repository.
  2. Sign in to [share.streamlit.io](https://share.streamlit.io) using GitHub.
  3. Select the repository and set the main file path to `app/main.py`.
  4. Store the LLM API key securely in the **Streamlit Secrets** dashboard (`st.secrets["GEMINI_API_KEY"]`).
  5. Click **Deploy**.
- **Result:** Provides a permanent, shareable public HTTPS link (e.g., `https://recallscope.streamlit.app`) for evaluators and stakeholders to interact with the discovery engine.

---

## 13. Data Flow Diagram

```text
+-----------------------------------------------------------------------+
|                       1. Public Evidence Collection                   |
|   (200–250 genuine records from Reddit, Google Help, App Stores, etc.) |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    2. Raw Storage (data/raw_evidence.csv)             |
|   (Preserves record_id, source, date, original_text, source_url)      |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    3. Data Cleaning & Validation                      |
|   (Strip whitespace, deduplicate URLs, check missing fields)          |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    4. Relevance Filtering                             |
|   (Separate photo retrieval evidence from generic complaints)         |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    5. AI Classification Pipeline                      |
|   (Extract clues, map F1–F8 stages, evaluate candidate issues)        |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|             6. Processed Storage (data/processed_evidence.csv)        |
|   (Combined immutable raw evidence + structured AI classifications)   |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    7. Pandas Analysis Layer                           |
|   (In-memory filtering, distributions, clue aggregation)              |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    8. RecallScope Streamlit Interface                 |
|   [Overview]  [Failures]  [Memory]  [Evidence]  [Q&A]  [Challenge]    |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                    9. Grounded Research Insights                      |
|   (Traceable to record IDs, surfaces contradictions, no fabrication)  |
+-----------------------------------------------------------------------+
```

---

## 14. Core Design Principles

1. **Simplicity Over Cleverness:** Avoid unnecessary tools, frameworks, and microservices. A clean Python/Streamlit script over a CSV file is reliable, fast to build, and easy to maintain.
2. **Evidence Traceability:** Every number, chart element, and AI answer must link back to specific public record IDs and live source URLs.
3. **Research Integrity:** Never force classifications. Honor uncertainty by defaulting to `F8 — Unknown`.
4. **Zero Fabrication:** Never invent records, quotes, statistics, or solutions.
5. **Separation of Evidence and Interpretation:** Always display verbatim user text alongside AI-generated classifications.
6. **No Preconceptions:** The architecture does not assume any particular solution or feature (such as conversational search or visual browsing).
7. **Fast Development & Public Testability:** Designed so that a complete beginner can run it locally and deploy it to the web with minimal friction.
