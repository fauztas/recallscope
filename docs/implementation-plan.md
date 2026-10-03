# RecallScope — Implementation Plan

> **Document Type:** Step-by-Step Implementation Blueprint  
> **Target Audience:** Beginner Developer / Product Manager  
> **Status:** Approved Plan — Execution On Hold  
> **Core Principle:** Small, independently testable phases with zero over-engineering.

---

## Important Research Data Timing

> [!IMPORTANT]
> The real ~200–250 genuine public records have **NOT** been fully collected yet.  
> Survey collection is still ongoing, and user interviews have not yet been completed.
>
> - **Phases 0 and Foundation** do not require the final dataset.
> - **Phase 1 onwards** requires the real public dataset (`data/raw_evidence.csv`).
> - **Never fabricate** public records, quotes, URLs, dates, or research findings.
> - If dummy data is ever required strictly for early technical interface testing, it must be explicitly labelled **`TEST DATA — NOT REAL EVIDENCE`** and kept completely isolated from the research data.

---

## Overview of Phases

```text
Phase 0: Project Foundation (Environment, packages, entry point)
   ↓
Phase 1: Dataset Ingestion & Validation (Load real raw CSV, audit health)
   ↓
Phase 2: Relevance Filtering (Separate retrieval struggles from complaints)
   ↓
Phase 3: AI Research Classification (Batch extract clues, F1–F8 stages)
   ↓
Phase 4: Research Analysis (Pandas aggregations & directional metrics)
   ↓
Phase 5: Core Streamlit Discovery Interface (Overview, Failures, Memory, Evidence)
   ↓
Phase 6: Ask the Evidence (Grounded natural-language Q&A with citations)
   ↓
Phase 7: Challenge an Insight (Confirmation bias checker & counter-evidence)
   ↓
Phase 8: Quality & Research-Integrity Checks (Traceability audits, methodology)
   ↓
Phase 9: UI Polish (Layout, readability, tooltips, responsive cards)
   ↓
Phase 10: End-to-End Testing (User journeys, error states, API fallbacks)
   ↓
Phase 11: Deployment (Streamlit Community Cloud public release)
```

---

## Phase 0 — Project Foundation

### 1. Objective
Prepare the project environment, folder structure, configuration, and dependencies so the application can be developed and run without setup friction.

### 2. Tasks
- Finalize the project folder structure (`app/`, `app/pages/`, `app/utils/`, `data/`, `docs/`).
- Create `requirements.txt` with minimal, stable dependencies:
  - `streamlit` (web interface)
  - `pandas` (data manipulation)
  - `plotly` (interactive charts)
  - `google-genai` (LLM API for classification and Q&A)
  - `python-dotenv` (local environment variable handling)
- Create `.env.example` demonstrating how API keys will be configured locally.
- Create a basic Streamlit entry point in `app/main.py` that displays a welcome screen and navigation placeholder.
- Add `.gitignore` to prevent committing virtual environment files, secrets, or cache files.

### 3. Files Created or Modified
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `app/main.py`

### 4. Expected Output
A clean, running skeleton Streamlit application that can be launched locally with `streamlit run app/main.py`.

### 5. Beginner-Friendly Explanation
Think of this as setting up your workbench and organizing your toolboxes before you start building anything. It makes sure Python knows which libraries to use and where every file belongs.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Running `streamlit run app/main.py` opens a browser window without errors.
- [ ] The app displays the project title and a placeholder message.
- [ ] Folder structure matches the architecture document.

### 7. Dependencies on Previous Phases
None (this is the starting foundation).

### 8. What Must NOT Happen in This Phase
- Do NOT write business or classification logic yet.
- Do NOT hardcode API keys.
- Do NOT connect GitHub or deploy.

---

## Phase 1 — Dataset Ingestion and Validation

### 1. Objective
Load the genuine public research dataset (~200–250 records) from CSV, validate required fields, remove accidental duplicates, and produce a dataset health report without touching or mutating the original file.

### 2. Tasks
- Place the collected public records into `data/raw_evidence.csv`.
- Create `app/utils/data_loader.py` to safely read `raw_evidence.csv` using Pandas.
- Validate that all mandatory columns exist:
  - `record_id`
  - `source`
  - `date`
  - `original_text`
  - `source_url`
- Check for duplicate records (matching `source_url` or identical `original_text`).
- Handle missing values gracefully (e.g., set missing dates to `"Unknown"`; flag missing URLs or text).
- Generate a summary of dataset health (total count, distribution by source, count of missing dates).

### 3. Files Created or Modified
- `data/raw_evidence.csv` (the real public records)
- `app/utils/data_loader.py`

### 4. Expected Output
A verified, clean Pandas DataFrame loaded into memory with an automated data quality summary report.

### 5. Beginner-Friendly Explanation
This step is like receiving a stack of survey forms and checking that none are blank, none are photocopies of each other, and all have an ID number.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Loader loads all ~200–250 records into a Pandas DataFrame.
- [ ] Zero missing `record_id`, `original_text`, or `source` values.
- [ ] Duplicate check runs and logs any duplicate entries.
- [ ] `data/raw_evidence.csv` remains completely unchanged on disk.

### 7. Dependencies on Previous Phases
- Requires Phase 0 (environment setup).
- Requires real public data to be collected and placed into `data/raw_evidence.csv`.

### 8. What Must NOT Happen in This Phase
- Do NOT overwrite or modify `data/raw_evidence.csv`.
- Do NOT invent or fabricate public records.
- Do NOT delete records without logging the reason.

---

## Phase 2 — Relevance Filtering

### 1. Objective
Identify and separate genuine photo-retrieval evidence from unrelated Google Photos technical complaints (such as backup failures, accidental deletions, storage quota limits, account login problems, upload errors, and sync issues).

### 2. Tasks
- Create filtering rules that flag unrelated complaints.
- Classify each record as:
  - `Relevant`: Contains meaningful evidence of someone attempting to find or retrieve a remembered photo.
  - `Irrelevant`: Unrelated complaint with no retrieval attempt.
  - `Uncertain`: Mixed evidence requiring manual review.
- Record a short, explicit `relevance_reason` for every classification.
- Retain all records in the dataset (do not delete irrelevant rows; flag them so they can be audited).

### 3. Files Created or Modified
- `app/utils/relevance_filter.py`
- Staging output or column addition: `is_relevant`, `relevance_reason`.

### 4. Expected Output
A dataset where every record has an auditable `is_relevant` tag and explanation, separating valid research evidence from noise.

### 5. Beginner-Friendly Explanation
Imagine going through a customer feedback box: some notes are about finding old vacation photos (what we want), while others are complaints about full storage or password resets (unrelated). This step sorts the pile into relevant vs. irrelevant without throwing anything in the trash.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Clear support complaints (e.g., *"My storage is full and won't let me back up"*) are classified as `Irrelevant`.
- [ ] Clear retrieval posts (e.g., *"I'm searching for a photo of a receipt from last month but can't find it"*) are classified as `Relevant`.
- [ ] Every record includes a human-readable `relevance_reason`.

### 7. Dependencies on Previous Phases
- Requires Phase 1 (validated dataset loaded).

### 8. What Must NOT Happen in This Phase
- Do NOT discard or permanently delete irrelevant records (they must remain visible in the Research Overview).
- Do NOT exclude records just because they are difficult to classify.

---

## Phase 3 — AI Research Classification

### 1. Objective
Use structured LLM batch processing to extract research attributes from relevant records and classify each failure into the F1–F8 taxonomy while guaranteeing complete traceability.

### 2. Tasks
- Implement `app/classify_pipeline.py` to batch-process relevant records safely without unnecessary repeated API calls.
- Define a strict system prompt embedding the taxonomy and extraction fields:
  - `retrieval_intent`
  - `photo_type`
  - `retrieval_scenario`
  - `remembered_clues`
  - `forgotten_clues`
  - `search_behaviour`
  - `reformulation_behaviour`
  - `manual_browsing`
  - `workaround`
  - `failure_stage` (mapped strictly to `F1`–`F8`)
  - `failure_reason`
  - `retrieval_outcome`
  - `evidence_strength` (`High`, `Medium`, `Low`)
  - `candidate_issues`
- Force the model to output `F8 — Unknown` whenever the record does not provide sufficient evidence.
- Parse JSON outputs into DataFrame columns.
- Save the results into `data/processed_evidence.csv`, preserving all original raw fields.

### 3. Files Created or Modified
- `app/classify_pipeline.py`
- `app/utils/llm_helper.py`
- `data/processed_evidence.csv`

### 4. Expected Output
`data/processed_evidence.csv` populated with structured research classifications linked directly to original `record_id`s and `source_url`s.

### 5. Beginner-Friendly Explanation
This is where our AI helper reads each relevant post and fills out a structured research questionnaire for it: What was the person looking for? What did they remember? Where did they get stuck? If the post doesn't say, the AI is trained to mark "Unknown" instead of guessing.

### 6. Test / Checklist to Confirm Phase Works
- [ ] All relevant records are processed and saved in `data/processed_evidence.csv`.
- [ ] Every record has a valid `failure_stage` in `['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8']`.
- [ ] Ambiguous posts correctly receive `F8 — Unknown`.
- [ ] `data/raw_evidence.csv` remains identical to its original state.

### 7. Dependencies on Previous Phases
- Requires Phase 2 (relevance tags established).
- Requires an active LLM API key configured in `.env`.

### 8. What Must NOT Happen in This Phase
- Do NOT run API calls in a loop without saving intermediate results.
- Do NOT force records into F1–F7 if the evidence is thin.
- Do NOT invent or infer details not stated by the user.

---

## Phase 4 — Research Analysis

### 1. Objective
Transform `processed_evidence.csv` into aggregated, directional research summaries and chart data using Pandas.

### 2. Tasks
- Create `app/utils/analysis.py` containing modular calculation functions:
  - Total records count, active sources count.
  - Relevance breakdown (count and percentage).
  - Failure stage distribution (F1–F8 frequency).
  - Remembered clues vs. forgotten clues frequency.
  - User workarounds and abandonment breakdown.
  - Candidate evaluation issues (visual clutter, excessive scrolling).
- Attach an explicit directional disclaimer string to all summary outputs.

### 3. Files Created or Modified
- `app/utils/analysis.py`

### 4. Expected Output
Reusable Python analysis functions that return structured numbers, dataframes, and chart figures on demand.

### 5. Beginner-Friendly Explanation
Here we write the math formulas that count up the research results: How many people failed at the search step? How many people remembered colors vs. dates? It turns individual posts into clear summary tables.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Sum of failure stages matches total relevant records.
- [ ] Sum of relevant + irrelevant + uncertain matches total raw records.
- [ ] Calculations run in under 1 second using Pandas.
- [ ] All functions include the required directional research disclaimer.

### 7. Dependencies on Previous Phases
- Requires Phase 3 (`processed_evidence.csv` available).

### 8. What Must NOT Happen in This Phase
- Do NOT present frequencies as population prevalence across all Google Photos users.
- Do NOT select a final target segment or single root cause.

---

## Phase 5 — Core Streamlit Discovery Interface

### 1. Objective
Build the interactive, multi-view Streamlit dashboard that lets a Product Manager explore the research evidence visually and dynamically.

### 2. Tasks
- Configure multi-page navigation in `app/main.py` and `app/pages/`.
- **Page 1: Research Overview (`app/pages/1_overview.py`)**
  - KPI summary cards (Total Records, Relevant, Irrelevant, Sources).
  - Source mix bar chart.
  - Research status banner (noting ongoing survey and interview phases).
- **Page 2: Failure Explorer (`app/pages/2_failures.py`)**
  - Dropdown filters for Failure Stage (F1–F8), Source, Photo Type.
  - Interactive failure stage distribution chart.
  - Cards displaying failure reason, evidence strength, and verbatim quotes.
- **Page 3: Memory Explorer (`app/pages/3_memory.py`)**
  - Comparison charts: Remembered Clues vs. Forgotten Clues.
  - Filter by clue category (temporal, spatial, visual, social).
  - Quote drawer showing what users explicitly said they recalled or forgot.
- **Page 4: Evidence Explorer (`app/pages/4_evidence.py`)**
  - Searchable, paginated data table of all records.
  - Keyword search across verbatim user texts.
  - Detailed inspect modal/drawer showing original text, live source URL, date, and full AI classifications side-by-side.

### 3. Files Created or Modified
- `app/main.py`
- `app/pages/1_overview.py`
- `app/pages/2_failures.py`
- `app/pages/3_memory.py`
- `app/pages/4_evidence.py`

### 4. Expected Output
A fully interactive web dashboard running locally in the browser where every chart and metric can be filtered and inspected down to individual public records.

### 5. Beginner-Friendly Explanation
This is the visual screen of your app. It turns the numbers and spreadsheet rows into interactive charts, search bars, and clickable cards that a Product Manager can explore with a mouse.

### 6. Test / Checklist to Confirm Phase Works
- [ ] All 4 pages load smoothly from the sidebar.
- [ ] Filtering by failure stage updates the visible list of evidence cards.
- [ ] Searching a keyword in Evidence Explorer instantly filters the table.
- [ ] Clicking a record link opens the original public forum URL in a new browser tab.

### 7. Dependencies on Previous Phases
- Requires Phase 4 (analysis functions ready).

### 8. What Must NOT Happen in This Phase
- Do NOT display aggregate charts without the ability to inspect underlying records.
- Do NOT hide verbatim quotes behind pure AI paraphrases.

---

## Phase 6 — Ask the Evidence

### 1. Objective
Enable a Product Manager to ask natural-language questions about the research dataset and receive answers strictly grounded only in collected public evidence with mandatory record citations.

### 2. Tasks
- Build `app/pages/5_ask_evidence.py`.
- Implement simple context retrieval: filter records matching keywords or pass relevant subset into the prompt.
- Assemble a strict grounding prompt:
  - Supply record IDs, source names, and original text.
  - Instruct the LLM to answer *only* using supplied records.
  - Require bracketed citations (e.g., `[REC_023]`) for every factual statement.
  - Require explicit refusal if evidence is missing: *"There is insufficient evidence in the collected records to answer this question."*
- Render the answer in Streamlit with expandable cards showing the verbatim text of all cited records.

### 3. Files Created or Modified
- `app/pages/5_ask_evidence.py`
- Updates to `app/utils/llm_helper.py`

### 4. Expected Output
A grounded Q&A interface where the AI answers research questions and provides direct citations to the underlying public evidence.

### 5. Beginner-Friendly Explanation
Like an ultra-disciplined research assistant who answers your questions using only the notes in your folder, pointing to the exact page number for every claim, and honestly saying "I don't know" if the notes don't mention it.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Asking *"What clues do users typically remember?"* produces an answer citing specific record IDs.
- [ ] Clicking a cited record ID displays the raw user quote.
- [ ] Asking an unsupported question (e.g., *"What is the average Google Photos subscription price?"*) results in an explicit refusal to answer due to lack of evidence.

### 7. Dependencies on Previous Phases
- Requires Phase 3 (classified evidence) and Phase 5 (Streamlit framework).

### 8. What Must NOT Happen in This Phase
- Do NOT use a vector database (standard in-memory filtering is sufficient and simpler for ~200–250 records).
- Do NOT allow the LLM to hallucinate or draw from general internet knowledge.

---

## Phase 7 — Challenge an Insight

### 1. Objective
Provide a dedicated research tool that actively searches for counter-evidence, contradictions, and nuances to combat confirmation bias when formulating hypotheses.

### 2. Tasks
- Build `app/pages/6_challenge_insight.py`.
- Accept a user-entered hypothesis (e.g., *"Users fail because they cannot remember dates"*).
- Query the dataset and prompt the LLM to categorize matching records into four buckets:
  1. **Supporting Evidence** (records validating the hypothesis)
  2. **Contradicting Evidence** (records where retrieval failed for other reasons)
  3. **Complicating Nuances** (records showing hybrid or unexpected factors)
  4. **Insufficient / Inconclusive Evidence**
- Display the four categories side-by-side with citations and verbatim quotes.

### 3. Files Created or Modified
- `app/pages/6_challenge_insight.py`
- Updates to `app/utils/llm_helper.py`

### 4. Expected Output
An interactive bias-checking tool that surfaces counter-examples and prevents researchers from jumping to premature conclusions.

### 5. Beginner-Friendly Explanation
A "devil's advocate" feature. If you think *"All users fail because of bad queries"*, this tool immediately finds the users who wrote great queries but failed because the photo was buried under 500 identical pictures.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Entering a one-sided statement returns both supporting and contradicting records.
- [ ] Every record shown includes its `record_id` and can be expanded to view verbatim text.
- [ ] Displays an explicit uncertainty warning if evidence is inconclusive.

### 7. Dependencies on Previous Phases
- Requires Phase 6 (grounded LLM helper).

### 8. What Must NOT Happen in This Phase
- Do NOT suppress counter-evidence or contradictions.
- Do NOT declare any hypothesis "proven".

---

## Phase 8 — Quality and Research-Integrity Checks

### 1. Objective
Audit the entire system for research defensibility, data consistency, citation accuracy, and transparent methodology for an academic or PM graduation defense.

### 2. Tasks
- Create an automated audit script `app/utils/integrity_checks.py`:
  - Verify 100% of cited record IDs in AI outputs exist in `processed_evidence.csv`.
  - Check for orphaned records or unmapped failure stages.
  - Audit source balance (flag if one source dominates >70% of the dataset).
  - Verify that directional disclaimers are present on all views.
- Add a dedicated **"Methodology & Limitations"** expander/modal on the Overview page detailing:
  - Sample size (~200–250 records).
  - Source channels and potential public forum bias.
  - Distinction between directional findings and population prevalence.

### 3. Files Created or Modified
- `app/utils/integrity_checks.py`
- `app/pages/1_overview.py` (add Methodology & Limitations section)

### 4. Expected Output
A verified audit report confirming zero broken citations, no hallucinated records, and clear public documentation of methodology and limitations.

### 5. Beginner-Friendly Explanation
This is the quality inspection stamp. It makes sure every quote is real, every link works, and anyone evaluating your project can see exactly how the research was conducted and where its limits are.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Audit script passes with zero broken citations or orphaned records.
- [ ] "Methodology & Limitations" section is clearly visible in the UI.
- [ ] Frequencies are explicitly labeled as directional signals.

### 7. Dependencies on Previous Phases
- Requires Phases 1 through 7 completed.

### 8. What Must NOT Happen in This Phase
- Do NOT sweep data limitations or small sample sizes under the rug.
- Do NOT skip citation verification.

---

## Phase 9 — UI Polish

### 1. Objective
Refine the layout, typography, navigation, and responsiveness of the Streamlit application to ensure an intuitive, executive-ready presentation.

### 2. Tasks
- Configure `.streamlit/config.toml` for clean typography, brand palette, and layout defaults.
- Improve visual hierarchy:
  - Use consistent metric cards with clear labels.
  - Add help tooltips explaining F1–F8 failure stages.
  - Style verbatim quotes with distinct blockquote cards.
  - Ensure high color contrast and mobile/laptop responsiveness.
- Keep the design clean, quiet, and research-focused (avoid flashy animations or unnecessary visual elements).

### 3. Files Created or Modified
- `.streamlit/config.toml`
- UI styling refinements across `app/main.py` and `app/pages/*.py`.

### 4. Expected Output
A cohesive, polished, professional web interface that prioritizes readability, evidence traceability, and ease of navigation.

### 5. Beginner-Friendly Explanation
Giving the app a clean, professional finish—making sure buttons look neat, text is easy to read, and helpful explanations pop up when you hover your mouse over technical terms.

### 6. Test / Checklist to Confirm Phase Works
- [ ] App displays cleanly on standard laptop screen resolutions.
- [ ] Hover tooltips explain the meaning of each failure stage (F1 to F8).
- [ ] Navigation between pages is instant and intuitive.

### 7. Dependencies on Previous Phases
- Requires Phase 8 (all core features functional and audited).

### 8. What Must NOT Happen in This Phase
- Do NOT prioritize visual styling over readability or data accuracy.
- Do NOT introduce complex custom CSS that could break Streamlit updates.

---

## Phase 10 — End-to-End Testing

### 1. Objective
Verify that a third party or evaluator can use every feature of RecallScope smoothly without errors, crashes, or confusing states.

### 2. Tasks
- Perform structured end-to-end user journey tests:
  - Test 1: First-time visitor lands on Overview, reviews KPIs, and reads Methodology.
  - Test 2: User filters Failure Explorer by `F2 — Expression Gap` and opens a verbatim quote.
  - Test 3: User examines Memory Explorer and compares remembered vs. forgotten clues.
  - Test 4: User searches a keyword in Evidence Explorer and clicks the public source link.
  - Test 5: User asks a natural-language question in "Ask the Evidence" and inspects citations.
  - Test 6: User tests an unsupported question and verifies proper graceful refusal.
  - Test 7: User enters a hypothesis in "Challenge an Insight" and examines counter-evidence.
- Test error and edge cases:
  - Disconnect internet / invalid API key: verify user receives a friendly `st.error()` message instead of an unhandled crash.
  - Filter with zero matching records: verify informative `st.info()` banner appears.

### 3. Files Created or Modified
- `docs/test-walkthrough.md` (or QA testing checklist log)

### 4. Expected Output
A verified, bug-free application ready for live demonstration or deployment.

### 5. Beginner-Friendly Explanation
Test-driving the entire car before handing the keys to someone else: testing every button, checking what happens if the internet cuts out, and making sure nothing crashes.

### 6. Test / Checklist to Confirm Phase Works
- [ ] All 7 user journeys pass with zero crashes.
- [ ] Offline / API failure triggers a clean, friendly error message.
- [ ] Empty search queries display helpful guidance rather than an empty screen.

### 7. Dependencies on Previous Phases
- Requires Phase 9 (polished interface).

### 8. What Must NOT Happen in This Phase
- Do NOT skip testing failure and offline states.
- Do NOT modify raw research data during testing.

---

## Phase 11 — Deployment

### 1. Objective
Publish RecallScope to the web using Streamlit Community Cloud so evaluators and stakeholders can access and test the live discovery engine via a public URL.

### 2. Tasks
- Ensure `requirements.txt` is up-to-date and contains exact working versions.
- Confirm all secrets (API keys) are read via `st.secrets` for production compatibility while falling back to `.env` locally.
- Initialize a clean Git repository and push the project code and data to GitHub.
- Connect the repository to [share.streamlit.io](https://share.streamlit.io).
- Add the `GEMINI_API_KEY` in the Streamlit Cloud Secrets dashboard.
- Deploy the application and perform a live smoke test.

### 3. Files Created or Modified
- `requirements.txt` (final version lock)
- `README.md` (updated with live deployment URL)

### 4. Expected Output
A publicly accessible HTTPS link (e.g., `https://recallscope.streamlit.app`) hosting the functional RecallScope engine.

### 5. Beginner-Friendly Explanation
Putting the finished app online for free so anyone with the web link can open it in their browser and try it out, without needing to install anything on their computer.

### 6. Test / Checklist to Confirm Phase Works
- [ ] Public URL loads in a private / incognito browser window.
- [ ] Navigation across all 6 pages works smoothly.
- [ ] Grounded Q&A generates answers using cloud secrets without error.
- [ ] No API keys or secrets are exposed in the GitHub repository.

### 7. Dependencies on Previous Phases
- Requires Phase 10 (all tests passing locally).

### 8. What Must NOT Happen in This Phase
- Do NOT deploy before passing Phase 10 tests.
- Do NOT commit `.env` or any secret keys to GitHub.
- Do NOT deploy unfinished or untested experimental code.
