# RecallScope — Edge Cases & Research Integrity Guide

> **Document Type:** Edge Case Taxonomy, Risk Analysis & Mitigation Guide  
> **Target Audience:** Beginner Developer / Product Manager  
> **Status:** Reference Blueprint for Defensive Design  
> **Core Principle:** Conservative interpretation, zero data fabrication, and graceful failure. "Unknown / Insufficient Evidence" is always preferred over invented certainty.

---

## Table of Contents
- [A. Raw Data Quality](#a-raw-data-quality)
- [B. Relevance Classification](#b-relevance-classification)
- [C. AI Classification](#c-ai-classification)
- [D. Failure-Stage Taxonomy Distinctions](#d-failure-stage-taxonomy-distinctions)
- [E. Evidence Traceability](#e-evidence-traceability)
- [F. Ask the Evidence (Grounded Q&A)](#f-ask-the-evidence-grounded-qa)
- [G. Challenge an Insight (Bias Countering)](#g-challenge-an-insight-bias-countering)
- [H. Analysis and Metrics](#h-analysis-and-metrics)
- [I. Privacy and Ethics](#i-privacy-and-ethics)
- [J. Application & Technical Failures](#j-application--technical-failures)
- [K. User Experience & Interface](#k-user-experience--interface)
- [L. Research-Integrity Red Flags](#l-research-integrity-red-flags)

---

## A. Raw Data Quality

### A1. Duplicate Public Records
1. **Edge Case:** Identical public comment or post recorded multiple times with different IDs.
2. **Simple Example:** A user posts the exact same query in two different subreddits or review threads: *"Can't find my red car picture from 2021"*.
3. **Why It Matters:** Counting the same feedback twice artificially inflates category frequencies and skews research signals.
4. **Expected System Behaviour:** Detect duplicates during data ingestion, keep only the first valid record, and log the duplicate count.
5. **How We Can Detect It:** Check for exact matches on normalized `original_text` (lowercased, whitespace stripped) or identical `source_url`.
6. **Planned Mitigation:** Run a deduplication check during Phase 1 ingestion using Pandas `drop_duplicates(subset=['clean_text'])` and report removed duplicates in the health log.

---

### A2. Same Conversation Appearing from Multiple URLs
1. **Edge Case:** Cross-posted threads or syndication across forum mirrors with distinct URLs.
2. **Simple Example:** A Reddit thread shared or scraped onto an aggregator website under a different web address.
3. **Why It Matters:** URL-based deduplication alone will miss it, causing redundant records.
4. **Expected System Behaviour:** Identify near-identical body text across different URLs and flag for manual confirmation or merge.
5. **How We Can Detect It:** Text similarity comparison (e.g., matching the first 100 characters of text across records).
6. **Planned Mitigation:** Ingestion script flags text collisions with different URLs as potential duplicates for review before final saving.

---

### A3. Missing Source URL
1. **Edge Case:** A record contains user text and metadata but the `source_url` field is blank or missing.
2. **Why It Matters:** Violates the non-negotiable rule of 100% public traceability. An evaluator cannot verify if the quote is genuine.
3. **Expected System Behaviour:** Reject or quarantine the record during ingestion until a verified URL is provided.
4. **How We Can Detect It:** Check if `source_url` is null, empty string, or invalid URL format.
5. **Planned Mitigation:** Data validation check in Phase 1 flags records missing `source_url` and prevents them from entering `raw_evidence.csv`.

---

### A4. Missing Date
1. **Edge Case:** A public forum comment does not display an exact timestamp (e.g., shows only *"3 years ago"* or date is missing).
2. **Why It Matters:** Date fields can cause software to crash if converted to standard date objects without handling blanks.
3. **Expected System Behaviour:** Accept the record, assign `"Unknown"` to the date field, and do not crash date filters.
4. **How We Can Detect It:** Detect null or non-parseable values in the `date` column.
5. **Planned Mitigation:** Fill missing date values with `"Unknown"` and exclude them gracefully from chronological timelines without dropping the record.

---

### A5. Missing Source Platform Name
1. **Edge Case:** The record does not identify whether it came from Reddit, Google Help, or an App Store.
2. **Why It Matters:** Skews source distribution charts and weakens provenance tracking.
3. **Expected System Behaviour:** Tag source as `"Other / Unspecified"` and alert the researcher during data ingestion.
4. **How We Can Detect It:** Validation check for null or whitespace-only `source` column.
5. **Planned Mitigation:** Ingestion schema enforcement requires a non-empty `source` string before accepting a record into the dataset.

---

### A6. Empty Original Text
1. **Edge Case:** A row in the CSV contains an ID and URL but the `original_text` field is empty.
2. **Why It Matters:** An empty record provides zero qualitative evidence and causes LLM prompts to fail.
3. **Expected System Behaviour:** Automatically discard the empty row and log an ingestion warning.
4. **How We Can Detect It:** Check if `len(original_text.strip()) == 0` or value is `NaN`.
5. **Planned Mitigation:** Automated pre-flight validation drops any record with empty text before processing begins.

---

### A7. Extremely Short Comments
1. **Edge Case:** A comment consists of only two or three words (e.g., *"Search sucks"*, *"Photos gone"*).
2. **Why It Matters:** Too brief to provide meaningful research evidence regarding retrieval stages or remembered clues.
3. **Expected System Behaviour:** Classify as `Irrelevant` or `Uncertain / Insufficient Evidence` rather than guessing a failure stage.
4. **How We Can Detect It:** Character count threshold (e.g., fewer than 25 characters or fewer than 5 words).
5. **Planned Mitigation:** Relevance filter flags extremely short records as insufficient evidence unless they contain explicit retrieval keywords.

---

### A8. Very Long Posts
1. **Edge Case:** A sprawling forum post spanning multiple paragraphs with detailed anecdotes and tangential complaints.
2. **Why It Matters:** Can cause UI layout breakage, overflow table cells, or consume excessive LLM prompt tokens.
3. **Expected System Behaviour:** Preserve full text in raw storage and detail views; truncate neatly with an ellipsis in summary tables.
4. **How We Can Detect It:** Check character length exceeding 1,000 characters.
5. **Planned Mitigation:** UI displays first 150 characters with an expandable "Read Full Post" button; prompt templates pass full text safely.

---

### A9. Malformed CSV Rows (Unescaped Quotes or Commas)
1. **Edge Case:** User text contains unescaped quotation marks (`"`), commas (`,`), or unexpected newlines inside the text.
2. **Why It Matters:** Corrupts CSV column alignment, shifting text into date columns or creating phantom rows.
3. **Expected System Behaviour:** Parse multi-line and quoted strings safely using standard CSV formatting.
4. **How We Can Detect It:** Pandas ingestion fails with `ParserError` or reports mismatched column counts.
5. **Planned Mitigation:** Use `pandas.read_csv(..., escapechar='\\', quotechar='"')` and always save data with proper RFC-4180 quoting.

---

### A10. Unusual Characters and Emojis
1. **Edge Case:** Posts containing non-ASCII symbols, foreign language characters, or emojis (e.g., 🔍, 😡, café).
2. **Why It Matters:** Can cause encoding crashes (`UnicodeDecodeError`) on Windows machines if encoded incorrectly.
3. **Expected System Behaviour:** Cleanly render all UTF-8 characters and emojis across both the CSV and the web app.
4. **How We Can Detect It:** Check file encoding during loading.
5. **Planned Mitigation:** Enforce explicit `encoding="utf-8"` in all Python read/write operations and Streamlit text renders.

---

### A11. Deleted or Unavailable Source Links
1. **Edge Case:** A public post that was active during collection is later deleted or removed by moderators.
2. **Why It Matters:** Clicking the link in the UI may return a 404 error on the external website.
3. **Expected System Behaviour:** The recorded verbatim text remains preserved in RecallScope; the UI notes that external links may change over time.
4. **How We Can Detect It:** External link verification or user reports.
5. **Planned Mitigation:** Store the verbatim raw text permanently in `raw_evidence.csv` so research integrity remains intact even if the external post disappears.

---

### A12. Records Containing Quoted Text from Another User
1. **Edge Case:** A forum post quotes an earlier user's comment before providing their own reply.
2. **Why It Matters:** The AI could mistakenly attribute the quoted text to the author or double-count clues.
3. **Expected System Behaviour:** Separate the author's primary statement from quoted material where possible.
4. **How We Can Detect It:** Look for quote markdown (`> quote`) or quotation marks accompanied by attribution phrases.
5. **Planned Mitigation:** Prompt guidelines instruct the classification LLM to analyze only the author's direct contribution.

---

### A13. Records Discussing Multiple Problems at Once
1. **Edge Case:** A single user post discusses a backup failure, a storage full warning, AND an unsuccessful search for a graduation photo.
2. **Why It Matters:** Categorizing the entire post as purely "irrelevant" loses valid retrieval evidence.
3. **Expected System Behaviour:** Tag as `Relevant` because it contains genuine retrieval evidence, while logging that other complaints exist.
4. **How We Can Detect It:** Keyword presence across both complaint categories (backup/storage) and retrieval categories (search/find/remember).
5. **Planned Mitigation:** Relevance rule: If a record contains *any* substantive photo retrieval attempt, classify as `Relevant` and isolate the retrieval segment for AI analysis.

---

## B. Relevance Classification

```text
Incoming Public Record
    ├── Pure technical complaint (No retrieval effort) ──────────> IRRELEVANT
    ├── Genuine retrieval struggle (Looking for photo) ─────────> RELEVANT
    └── Mixed / Vague / Insufficient context ────────────────────> UNCERTAIN
```

### B1. Clearly Relevant Retrieval Record
1. **Edge Case:** User clearly describes searching for a specific remembered photo and encountering friction.
2. **Simple Example:** *"I searched for my dog at the beach in 2022, but Google Photos just gave me hundreds of random beach pictures."*
3. **Why It Matters:** This is the core subject of our research and must be retained.
4. **Expected System Behaviour:** Classify as `is_relevant = "Relevant"`, log reason, and pass to AI classification pipeline.
5. **How We Can Detect It:** Presence of retrieval intent, search terms, and memory references.
6. **Planned Mitigation:** Clear inclusion criteria in `relevance_filter.py`.

---

### B2. Clearly Irrelevant Complaint Record
1. **Edge Case:** Pure technical complaint with no search or retrieval element.
2. **Simple Example:** *"Google Photos charged my credit card twice for 100GB storage renewal."*
3. **Why It Matters:** Retaining this in retrieval analysis pollutes the dataset with irrelevant customer billing noise.
4. **Expected System Behaviour:** Classify as `is_relevant = "Irrelevant"`, log reason (e.g., *"Billing issue, no retrieval"*), and exclude from failure charts.
5. **How We Can Detect It:** Presence of billing/payment keywords with no retrieval language.
6. **Planned Mitigation:** Keyword exclusion filters flag billing, payment, and account login issues.

---

### B3. Ambiguous Relevance
1. **Edge Case:** Short or vague post that could imply retrieval difficulty or general dissatisfaction.
2. **Simple Example:** *"Search doesn't work anymore."*
3. **Why It Matters:** Deciding unilaterally could introduce researcher bias or false data.
4. **Expected System Behaviour:** Classify as `is_relevant = "Uncertain"`, flag for manual researcher review, and default to exclusion until confirmed.
5. **How We Can Detect It:** High-level search complaint without specific context, clues, or symptoms.
6. **Planned Mitigation:** Dedicated `Uncertain` state ensures ambiguous records are surfaced for human review rather than misclassified.

---

### B4. Backup Issue Containing Retrieval Evidence
1. **Edge Case:** A user is trying to find a remembered photo, but discovers it failed to backup months ago.
2. **Simple Example:** *"I tried searching for my wedding invitations from June, but realised backup paused and Photos never uploaded them."*
3. **Why It Matters:** While backup was the technical cause, the trigger was a vague-memory retrieval attempt.
4. **Expected System Behaviour:** Classify as `Relevant` with failure stage mapped to `F7 — Coverage / Indexing Gap`.
5. **How We Can Detect It:** Co-occurrence of retrieval search language and backup failure terms.
6. **Planned Mitigation:** Explicit rule: If the user discovered the issue while trying to search/retrieve a specific photo, retain as relevant under `F7`.

---

### B5. Deleted-Photo Issue Mistaken for Retrieval Failure
1. **Edge Case:** User deleted photos from their trash and later searches for them.
2. **Simple Example:** *"I emptied my trash bin last week and now when I search for my vacation pictures they aren't coming up."*
3. **Why It Matters:** This is an intentional or accidental file deletion issue, not an algorithmic search retrieval failure.
4. **Expected System Behaviour:** Classify as `is_relevant = "Irrelevant"`, logging *"Deleted photos issue"*.
5. **How We Can Detect It:** Mentions of trash, bin, permanent delete, or recovery.
6. **Planned Mitigation:** Rule-based filter excludes records where missing status is explicitly linked to trash emptying or deletion.

---

### B6. General Complaint with No Retrieval Behaviour
1. **Edge Case:** A low-star app store review expressing frustration without details.
2. **Simple Example:** *"1 star. App used to be good, now it's terrible and confusing."*
3. **Why It Matters:** Contains zero qualitative evidence about memory, queries, or search outcomes.
4. **Expected System Behaviour:** Classify as `is_relevant = "Irrelevant"` (reason: *"Generic complaint, no retrieval evidence"*).
5. **How We Can Detect It:** Absence of verbs related to searching, finding, remembering, or viewing.
6. **Planned Mitigation:** Rule flags reviews lacking specific feature context as irrelevant.

---

### B7. User Says "Can't Find Photos" but Means Photos Disappeared
1. **Edge Case:** User uses search vocabulary like "can't find", but the context reveals a sync bug caused files to vanish from their library.
2. **Simple Example:** *"Updated to Android 14 and now I can't find any of my camera photos, the gallery is completely blank."*
3. **Why It Matters:** Confusing a missing file/sync bug with a vague-memory search failure leads to incorrect root cause assumptions.
4. **Expected System Behaviour:** Classify as `is_relevant = "Irrelevant"` (reason: *"Sync/display bug, library wiped"*).
5. **How We Can Detect It:** Mentions of whole gallery missing, blank screens, or post-update disappearance.
6. **Planned Mitigation:** Train relevance rules to check whether the user is searching for *a remembered photo* versus complaining about *an empty gallery*.

---

### B8. User Remembers Photo but Provides Too Little Evidence for Stage
1. **Edge Case:** User confirms they remember a specific photo, but doesn't explain what they typed or what happened.
2. **Simple Example:** *"Spent an hour trying to find my concert picture from 2019 and gave up."*
3. **Why It Matters:** It IS a relevant vague-memory retrieval struggle, but lacks detail to assign a specific failure stage F1–F7.
4. **Expected System Behaviour:** Mark `is_relevant = "Relevant"`, but assign `failure_stage = "F8 — Unknown"`.
5. **How We Can Detect It:** Relevant intent present, but query text and system response details are absent.
6. **Planned Mitigation:** Strict taxonomy separation: Relevance determines *if* it enters the research set; F8 captures *insufficient failure details*.

---

## C. AI Classification

### C1. Insufficient Evidence for a Field
1. **Edge Case:** A user post describes a query but does not mention if they browsed or tried workarounds.
2. **Simple Example:** *"Searched 'blue jacket' and got no hits."*
3. **Why It Matters:** Forcing the AI to fill every field results in hallucinated user behaviours.
4. **Expected System Behaviour:** The AI outputs `"Unknown"` or `"Not Stated"` for missing fields.
5. **How We Can Detect It:** Prompt test checks whether fields with no textual basis contain fabricated descriptions.
6. **Planned Mitigation:** Prompt instruction: *"If the user did not explicitly mention a workaround or manual browsing, you MUST write 'Not Stated'."*

---

### C2. Multiple Possible Failure Stages in One Record
1. **Edge Case:** A user struggled to phrase their search (F2), and when they did search, 800 similar candidates appeared (F5).
2. **Simple Example:** *"Didn't know what words to use, so typed 'birthday' and had to scroll past 900 pictures without spotting it."*
3. **Why It Matters:** Forcing a single rigid stage ignores complex multi-stage failures.
4. **Expected System Behaviour:** Record the primary breakdown stage while noting secondary failure stages in `failure_reason`.
5. **How We Can Detect It:** Post contains symptoms matching more than one taxonomy stage definition.
6. **Planned Mitigation:** Schema captures `primary_failure_stage` (e.g., `F2`) and an optional `secondary_stage` (e.g., `F5`) in the analysis layer.

---

### C3. AI Inventing Remembered Clues
1. **Edge Case:** The LLM hallucinates clues that the user never wrote down.
2. **Simple Example:** User says *"Can't find my holiday picture"*, and the AI outputs `remembered_clues = "Beach, sunset, family"`.
3. **Why It Matters:** Fabricates research data and compromises scientific credibility.
4. **Expected System Behaviour:** Extract *only* explicitly mentioned words or immediate synonyms. If none, output `"None mentioned"`.
5. **How We Can Detect It:** Audit script compares extracted clue words against the vocabulary of `original_text`.
6. **Planned Mitigation:** Prompt rule: *"Extract remembered clues ONLY using words explicitly present in the user quote. Never infer or embellish."*

---

### C4. AI Inferring a Photo Type Not Stated by User
1. **Edge Case:** The LLM guesses what kind of photo it was without evidence.
2. **Simple Example:** User says *"Can't find that file from last Tuesday"*, and AI classifies `photo_type = "Document / Receipt"`.
3. **Why It Matters:** Inaccurate categorization corrupts photo-type analysis charts.
4. **Expected System Behaviour:** Mark `photo_type = "Unknown / Not specified"`.
5. **How We Can Detect It:** Review photo-type tags on posts lacking descriptive nouns.
6. **Planned Mitigation:** Default category value `"Unspecified"` enforced whenever photo type is ambiguous.

---

### C5. AI Inventing a User Workaround
1. **Edge Case:** The LLM assumes the user asked a friend or gave up when the post ended without stating what happened.
2. **Simple Example:** Post ends with *"Why is this so hard?"*, and AI outputs `workaround = "Gave up searching"`.
3. **Why It Matters:** Distorts behavioral outcome frequencies.
4. **Expected System Behaviour:** Set `workaround = "Not Stated"`.
5. **How We Can Detect It:** Validate whether workaround field claims actions absent from verbatim text.
6. **Planned Mitigation:** System prompt explicitly instructs: *"Do not infer actions taken after retrieval unless the user states them."*

---

### C6. AI Assigning a Confident Failure Stage Without Evidence
1. **Edge Case:** The LLM chooses `F3 — Interpretation Gap` with 100% confidence for a one-line vague post.
2. **Why It Matters:** Creates an illusion of precision on sparse data.
3. **Expected System Behaviour:** Assign `F8 — Unknown` and set `evidence_strength = "Low"`.
4. **How We Can Detect It:** Cross-reference `evidence_strength` with failure stage assignment.
5. **Planned Mitigation:** Prompt heuristic: If the post contains fewer than two factual retrieval elements, default to `F8 — Unknown`.

---

### C7. Conflicting Information Inside One Record
1. **Edge Case:** A user contradicts themselves (e.g., *"I searched for my red car, but I never use search"*).
2. **Why It Matters:** Confuses simple extraction logic.
3. **Expected System Behaviour:** Flag `evidence_strength = "Low / Contradictory"` and document the contradiction in `failure_reason`.
4. **How We Can Detect It:** LLM reasoning highlights internal inconsistencies.
5. **Planned Mitigation:** Structured output includes an `uncertainty_notes` field.

---

### C8. Classification Output in the Wrong Format
1. **Edge Case:** LLM returns conversational prose instead of valid JSON.
2. **Why It Matters:** Application code will crash with a `JSONDecodeError`.
3. **Expected System Behaviour:** Catch formatting error, re-try with structured format enforcement, or quarantine row.
4. **How We Can Detect It:** `json.loads()` throws an exception.
5. **Planned Mitigation:** Use structured JSON output mode in API calls and wrap parser in a fallback handler that sets fields to `Unknown` rather than crashing.

---

### C9. API Returning Incomplete Output
1. **Edge Case:** LLM response is truncated halfway through due to token limit or network disconnect.
2. **Why It Matters:** Leaves corrupted partial fields in the dataset.
3. **Expected System Behaviour:** Detect missing closing brackets, discard partial output, and log for retry.
4. **How We Can Detect It:** Schema validation checks for presence of all required JSON keys.
5. **Planned Mitigation:** Retry failed record up to 2 times; if still incomplete, mark as `Processing Error` for later review.

---

### C10. AI Response Failing Completely
1. **Edge Case:** The AI API returns a 500 error or rate limit exhaustion.
2. **Why It Matters:** Could halt batch classification of the dataset.
3. **Expected System Behaviour:** Pause execution gracefully, save all successfully classified rows to disk, and display a retry prompt.
4. **How We Can Detect It:** API client raises an HTTP or connection exception.
5. **Planned Mitigation:** Batch script saves checkpoint after every 10 records so progress is never lost.

---

## D. Failure-Stage Taxonomy Distinctions

```text
    User Memory               Query Formulated              Search Executed               Candidate Results
[ F1: Recall Gap ]  ──>  [ F2: Expression Gap ]  ──>  [ F3: Interpretation ]  ──>  [ F4: Candidate Gap ]
User can't remember       User can't put memory        Search engine misses         Photo not returned
enough clues.             into query words.            the user's intent.           in top candidates.
                                                                                           │
                                                                                           ▼
                                                        [ F6: Refinement Gap ] <── [ F5: Recognition Gap ]
                                                        User doesn't know how      Results exist, but user
                                                        to modify search.          can't spot the photo.
```

### D1. Expression Gap (F2) vs. Interpretation Gap (F3)
1. **Edge Case:** Disentangling whether the user struggled to express what they knew, or whether they expressed it well but Google Photos misunderstood.
2. **Simple Example:** User says *"I typed 'party at lake' but it gave me ocean pictures."* Did they fail to express the lake type (F2), or did search misinterpret 'lake' as any body of water (F3)?
3. **Why It Matters:** F2 suggests user-expression support tools; F3 suggests search semantic model improvements.
4. **Expected System Behaviour:** If the user provided a reasonable keyword that the system visibly misinterpreted, classify as **F3**. If the user explicitly complains they couldn't think of the right words, classify as **F2**. If ambiguous, classify as **F8**.
5. **How We Can Detect It:** Analyze whether user self-blames their phrasing vs. blames the search engine's wrong matches.
6. **Planned Mitigation:** Strict prompt definitions with explicit contrast guidelines between F2 and F3.

---

### D2. Candidate Gap (F4) vs. Recognition Gap (F5)
1. **Edge Case:** Did the search fail to surface the photo at all (F4), or was the photo returned but buried among 500 identical photos so the user couldn't spot it (F5)?
2. **Simple Example:** *"Search gave me results, but there were so many dog photos I gave up looking after 10 minutes."*
3. **Why It Matters:** F4 is a retrieval recall problem; F5 is a visual clutter and candidate browsing/recognition problem.
4. **Expected System Behaviour:** If the photo is confirmed not present in candidates, tag **F4**. If candidates appeared but finding the specific photo required excessive scrolling or inspection, tag **F5**.
5. **How We Can Detect It:** Mentions of scrolling fatigue, visual similarity, or overwhelming candidate volume.
6. **Planned Mitigation:** Classify records mentioning *"too many similar results"* or *"scrolled forever"* as **F5 — Recognition Gap**.

---

### D3. Recognition Gap (F5) vs. Refinement Gap (F6)
1. **Edge Case:** User sees candidate results, cannot easily spot the photo, and does not know what to search next.
2. **Simple Example:** *"Got 300 pictures of food, didn't see the one I wanted, and had no clue what filter to try next."*
3. **Why It Matters:** Highlights the transition between browsing failure and reformulation failure.
4. **Expected System Behaviour:** Classify the primary failure where the journey terminated (here, F6 if they abandoned due to not knowing how to refine).
5. **How We Can Detect It:** Presence of post-result confusion and query abandonment.
6. **Planned Mitigation:** Map the primary stage to the point of permanent abandonment, recording F5 as a contributing factor.

---

### D4. Recall Gap (F1) vs. Expression Gap (F2)
1. **Edge Case:** User can't remember the details (F1) vs. remembers them vividly but cannot formulate a search term (F2).
2. **Simple Example:** *"I remember it was a nice day, but that's literally all I know"* (F1) vs. *"I remember the exact texture of the wallpaper, but how do you search for that?"* (F2).
3. **Why It Matters:** F1 points to memory aiding/reminiscence prompts; F2 points to multi-modal or descriptive query inputs.
4. **Expected System Behaviour:** If memory itself is depleted/blank, tag **F1**. If memory is rich but non-textual or hard to phrase, tag **F2**.
5. **How We Can Detect It:** Check whether user states they forgot the facts vs. states they don't know what keywords to type.
6. **Planned Mitigation:** Distinct prompt criteria: F1 = insufficient memory; F2 = memory present, translation into query blocked.

---

### D5. Coverage / Indexing Gap (F7) vs. Interpretation Gap (F3)
1. **Edge Case:** The photo was never indexed (e.g., text in image not OCR'd, receipt not tagged) vs. indexed but search misinterpreted query.
2. **Simple Example:** *"Searched for the serial number on my fridge picture, but Photos doesn't read numbers on metal."*
3. **Why It Matters:** F7 is a computer vision/indexing capability limitation; F3 is a semantic search matching error.
4. **Expected System Behaviour:** Tag as **F7** when the failure is explicitly tied to unindexed visual attributes (e.g., text, obscure objects, lack of metadata).
5. **How We Can Detect It:** User references unreadable text, missing faces, or non-indexed visual elements.
6. **Planned Mitigation:** Category definitions explicitly define F7 as visual indexing or metadata absence.

---

### D6. Insufficient Evidence to Identify Any Stage
1. **Edge Case:** Record confirms a retrieval failure occurred, but gives zero diagnostic clues.
2. **Simple Example:** *"I spent two hours trying to find a photo from last summer and failed."*
3. **Why It Matters:** Forcing an F1–F7 stage here would be pure fiction.
4. **Expected System Behaviour:** Classify strictly as **F8 — Unknown**.
5. **How We Can Detect It:** Absence of query text, candidate descriptions, or memory details.
6. **Planned Mitigation:** In UI and charts, **F8 — Unknown** is displayed transparently as an honest scientific category.

---

## E. Evidence Traceability

### E1. AI Insight Without Supporting Record IDs
1. **Edge Case:** An AI-generated summary makes a claim without citing a specific record ID.
2. **Simple Example:** *"Most users try searching by color after failure"* (with no citation).
3. **Why It Matters:** Violates the core traceability rule; unverifiable claim.
4. **Expected System Behaviour:** Flag as ungrounded; require every sentence to cite at least one valid `[REC_xxx]`.
5. **How We Can Detect It:** Regex audit checks AI responses for the pattern `\[REC_\d+\]`.
6. **Planned Mitigation:** Strict prompt template: *"Every factual assertion must end with a citation [REC_xxx]. If you cannot cite a record, do not make the claim."*

---

### E2. Chart Count Not Matching Filtered Records
1. **Edge Case:** A chart displays a bar showing 15 records, but clicking the bar displays only 12 rows in the table.
2. **Why It Matters:** Destroys evaluator trust in the dashboard's calculations.
3. **Expected System Behaviour:** Dynamic recalculation where chart series and table rows share the exact same underlying filtered Pandas DataFrame.
4. **How We Can Detect It:** Automated test verifies `len(filtered_df) == sum(chart_counts)`.
5. **Planned Mitigation:** Single-source-of-truth architecture: all UI components consume the exact same filtered DataFrame instance.

---

### E3. Missing Original Evidence File
1. **Edge Case:** `data/raw_evidence.csv` is accidentally deleted or moved.
2. **Why It Matters:** The entire system loses its empirical foundation.
3. **Expected System Behaviour:** Display an immediate clear error: *"Raw evidence file missing at data/raw_evidence.csv"*.
4. **How We Can Detect It:** `os.path.exists('data/raw_evidence.csv') == False`.
5. **Planned Mitigation:** Data loader checks file existence on startup and halts with a friendly instruction.

---

### E4. Broken Source URL
1. **Edge Case:** Clicking a source URL in Evidence Explorer leads to a 404 or dead link.
2. **Why It Matters:** Minor verification friction for evaluators.
3. **Expected System Behaviour:** Link is marked with an external icon; user can still view the full verbatim quote stored locally.
4. **How We Can Detect It:** Periodic link-checking script or user report.
5. **Planned Mitigation:** Verbatim quote stored permanently in the CSV so the research finding does not depend on the live link staying up indefinitely.

---

### E5. Processed Record Losing Connection to Raw Record
1. **Edge Case:** A bug causes `processed_evidence.csv` to lose or misalign its `record_id` with `raw_evidence.csv`.
2. **Why It Matters:** Complete breakdown of research traceability.
3. **Expected System Behaviour:** Refuse to load if `record_id` values do not match 1-to-1 between raw and processed files.
4. **How We Can Detect It:** Integrity check: `set(raw['record_id']) == set(processed['record_id'])`.
5. **Planned Mitigation:** Ingestion and classification pipelines enforce identical primary key joins.

---

### E6. Duplicate Record Affecting a Chart
1. **Edge Case:** An undetected duplicate record is counted twice in a failure-stage breakdown.
2. **Why It Matters:** Distorts the directional frequency.
3. **Expected System Behaviour:** Filter duplicates before any metric calculation.
4. **How We Can Detect It:** Check `df['record_id'].nunique() == len(df)`.
5. **Planned Mitigation:** Integrity check asserts primary key uniqueness across all data loaders.

---

### E7. Edited Raw Evidence
1. **Edge Case:** Someone edits a raw quote in the CSV to make it fit a hypothesis better.
2. **Why It Matters:** Severe breach of research ethics and scientific integrity.
3. **Expected System Behaviour:** Raw evidence file is treated as immutable read-only source.
4. **How We Can Detect It:** File hash / checksum check or Git diff monitoring.
5. **Planned Mitigation:** Ingestion script treats `raw_evidence.csv` as strictly read-only; processed data is saved to a distinct file.

---

## F. Ask the Evidence (Grounded Q&A)

### F1. Question Supported by Many Records
1. **Edge Case:** User asks *"What are the most common things people remember?"*, which is supported by 50+ records.
2. **Why It Matters:** Can overwhelm the context window or produce a sprawling list.
3. **Expected System Behaviour:** Synthesize the primary patterns, cite top representative record IDs (e.g., 3–5 citations per theme), and note the breadth of evidence.
4. **How We Can Detect It:** High frequency of matching keyword records.
5. **Planned Mitigation:** Prompt instructs LLM to group findings into themes and cite 2–4 representative records per theme.

---

### F2. Question Supported by Only One Record
1. **Edge Case:** User asks about a very niche scenario that only one user mentioned (e.g., finding a photo of an antique clock).
2. **Why It Matters:** Stating it as a general finding would be misleading.
3. **Expected System Behaviour:** Explicitly state: *"This is supported by only a single record in the dataset [REC_084] and should be treated as an isolated observation rather than a broad pattern."*
4. **How We Can Detect It:** Context retrieval returns only 1 relevant record.
5. **Planned Mitigation:** Prompt rule: *"If a finding is supported by only one record, you MUST state that it is an isolated record."*

---

### F3. Question Unsupported by Dataset
1. **Edge Case:** User asks *"Do users prefer paying monthly or yearly for Google One?"*
2. **Why It Matters:** If the LLM uses external knowledge, it invents an ungrounded answer.
3. **Expected System Behaviour:** Explicit refusal: *"The collected research dataset contains no evidence regarding Google One payment preferences."*
4. **How We Can Detect It:** Context retrieval finds zero matching records with relevant terms.
5. **Planned Mitigation:** Strict grounding prompt: *"If the supplied records do not contain the answer, state that the dataset contains insufficient evidence."*

---

### F4. Question Asking for Population-Level Prevalence
1. **Edge Case:** User asks *"What percentage of all Google Photos users worldwide fail because of Expression Gap?"*
2. **Why It Matters:** Our dataset cannot answer population prevalence; answering it with our sample frequency is statistically invalid.
3. **Expected System Behaviour:** Decline to give a population number, clarify that public forum records provide directional evidence only, and share the sample frequency clearly labeled as sample-only.
4. **How We Can Detect It:** Queries containing phrases like *"worldwide"*, *"all users"*, *"market share"*, or *"population percentage"*.
5. **Planned Mitigation:** System prompt instructs LLM to explicitly distinguish sample frequencies from global population prevalence.

---

### F5. Question Asking for Final Product Recommendation
1. **Edge Case:** User asks *"Should we build conversational voice search to solve this?"*
2. **Why It Matters:** RecallScope is an exploratory discovery engine, not a solution validator.
3. **Expected System Behaviour:** Refuse to prescribe a final product solution; reframe to what the evidence says about user struggles with expression and speech.
4. **How We Can Detect It:** Queries asking *"Should we build..."*, *"What is the best feature..."*, or *"What solution should we pick?"*.
5. **Planned Mitigation:** System prompt instructs: *"RecallScope is a problem discovery engine, not a solution recommendation tool. Do not prescribe final product solutions."*

---

### F6. Question Containing a False Assumption
1. **Edge Case:** User asks *"Why do all users remember dates but forget locations?"* (when evidence shows many forgot dates).
2. **Why It Matters:** An unconstrained LLM might play along with the false premise.
3. **Expected System Behaviour:** Politely correct the false assumption using cited evidence: *"The evidence does not support this assumption. In fact, records such as [REC_012] and [REC_045] show users frequently forgetting dates while remembering locations."*
4. **How We Can Detect It:** Prompt instructs the model to evaluate the premise against the evidence before answering.
5. **Planned Mitigation:** Grounding prompt rule: *"If a question contains a premise contradicted by the records, explicitly point out the contradiction."*

---

### F7. Question Asking About Information Outside the Dataset
1. **Edge Case:** User asks about Apple Photos algorithms or competitor backend architectures.
2. **Why It Matters:** Hallucination risk from general LLM knowledge.
3. **Expected System Behaviour:** State that external technical architectures are not covered in the public user dataset.
4. **How We Can Detect It:** Query asks about internal algorithms or non-dataset entities.
5. **Planned Mitigation:** Enforce closed-domain grounding prompt.

---

### F8. No Relevant Records Retrieved for a Query
1. **Edge Case:** The search terms in the question match zero records in the dataset.
2. **Why It Matters:** LLM might fabricate an answer if called with empty context.
3. **Expected System Behaviour:** Intercept before calling the LLM and display: *"No records in the research dataset match your query. Please try different terms."*
4. **How We Can Detect It:** Context filter returns an empty list.
5. **Planned Mitigation:** Pre-call check in `llm_helper.py` halts execution and returns a standard empty-result notice without consuming API tokens.

---

### F9. Contradictory Evidence Exists for the Question
1. **Edge Case:** Some records show users love date filtering, while other records show date filtering was completely useless for them.
2. **Why It Matters:** Answering with only one side hides vital nuance.
3. **Expected System Behaviour:** Present both perspectives clearly: *"The evidence is divided: records [REC_010, REC_014] report successful retrieval via date scrubbing, whereas records [REC_032, REC_055] report that date estimates returned overwhelming clutter."*
4. **How We Can Detect It:** Semantic diversity in retrieved records.
5. **Planned Mitigation:** Prompt rule: *"When evidence contains conflicting experiences, present both sides and cite records for each."*

---

### F10. LLM Tries to Answer from General Knowledge
1. **Edge Case:** LLM ignores the provided context and recites general knowledge from its training weights.
2. **Why It Matters:** Destroys research integrity and makes answers unverifiable.
3. **Expected System Behaviour:** Prompt forces the LLM to restrict its entire knowledge base to the provided text snippet.
4. **How We Can Detect It:** Statements made without any citation tag `[REC_xxx]`.
5. **Planned Mitigation:** Automated regex post-check flags any answer containing factual sentences without bracketed citations.

---

## G. Challenge an Insight (Bias Countering)

### G1. Strong Supporting Evidence but No Contradiction
1. **Edge Case:** An entered insight is uniformly supported across all matching records (e.g., *"Users feel frustrated when retrieval fails"*).
2. **Why It Matters:** The researcher might think the tool is broken if the "Contradicting" column is empty.
3. **Expected System Behaviour:** Populate the "Supporting" column, and display an explicit note under "Contradicting": *"No contradicting records found in the current dataset."*
4. **How We Can Detect It:** Zero records identified in the contradicting bucket.
5. **Planned Mitigation:** Clear UI status message explaining that no counter-evidence was detected for this specific statement.

---

### G2. Strong Contradictory Evidence
1. **Edge Case:** A popular hypothesis is directly debunked by the data (e.g., *"Users always remember the year"*).
2. **Why It Matters:** This is the highest-value outcome of the tool—preventing bad product decisions.
3. **Expected System Behaviour:** Highlight the contradicting bucket prominently with bold citations and verbatim quotes.
4. **How We Can Detect It:** Contradicting bucket contains high-confidence records.
5. **Planned Mitigation:** Visual emphasis on counter-evidence to ensure the Product Manager confronts it.

---

### G3. Mixed Evidence
1. **Edge Case:** Roughly equal numbers of records support and contradict the insight.
2. **Why It Matters:** Demonstrates that the user problem is heterogeneous, not one-size-fits-all.
3. **Expected System Behaviour:** Display balanced columns and summarize the nuance in a "Complicating Factors" section.
4. **How We Can Detect It:** Both supporting and contradicting buckets have non-zero counts.
5. **Planned Mitigation:** Provide a synthesis statement noting that user behavior diverges based on scenario.

---

### G4. Too Little Evidence to Evaluate the Insight
1. **Edge Case:** User tests an insight that only 1 or 2 records touch upon.
2. **Why It Matters:** Drawing conclusions from 1 record is premature.
3. **Expected System Behaviour:** Place records in the "Insufficient Evidence" bucket with an explicit warning banner: *"Evidence is too sparse to evaluate this insight confidently."*
4. **How We Can Detect It:** Total matching records < 3 (or configured minimum threshold).
5. **Planned Mitigation:** UI warning banner whenever total relevant records are below the configurable threshold.

---

### G5. Proposed Insight is Too Broad
1. **Edge Case:** User enters an overly vague statement like *"Search is bad"*.
2. **Why It Matters:** Too broad to categorize meaningfully across failure stages.
3. **Expected System Behaviour:** Prompt the user to narrow their insight: *"This insight is very broad. For better results, test a specific hypothesis about memory, queries, or results (e.g., 'Users struggle to describe colors')."*
4. **How We Can Detect It:** Statement length < 4 words or lacks specific failure/retrieval entities.
5. **Planned Mitigation:** Front-end helper text providing example hypotheses for the user to try.

---

### G6. Proposed Insight Contains a Solution Rather Than a Research Claim
1. **Edge Case:** User enters *"Google Photos should add a voice assistant"*.
2. **Why It Matters:** Evaluates a solution rather than discovering where the problem occurs.
3. **Expected System Behaviour:** Reframe the query: show evidence regarding user speech/voice search behaviors and expression struggles, while reminding the user that RecallScope evaluates problem evidence rather than solution roadmaps.
4. **How We Can Detect It:** Presence of solution keywords (*"should build"*, *"feature"*, *"solution"*).
5. **Planned Mitigation:** Guidance banner: *"RecallScope tests problem hypotheses. Showing evidence related to the user friction underlying this proposed feature."*

---

### G7. Counter-Evidence Comes from Only One Weak Record
1. **Edge Case:** The only contradicting record is a 5-word low-confidence comment.
2. **Why It Matters:** Could cause the researcher to discard a valid hypothesis based on noise.
3. **Expected System Behaviour:** Display the counter-record, but clearly badge its evidence strength as `Low Confidence / Weak Record`.
4. **How We Can Detect It:** Record has `evidence_strength == "Low"`.
5. **Planned Mitigation:** Display confidence badges on all evidence cards in the Challenge view.

---

### G8. Apparent Contradiction is Actually a Different User Scenario
1. **Edge Case:** A record seems to contradict an insight, but close inspection reveals the user was looking for a document rather than a personal photo.
2. **Why It Matters:** Apples-to-oranges comparison.
3. **Expected System Behaviour:** The AI notes the scenario difference in the "Complicating Nuances" section.
4. **How We Can Detect It:** Mismatched `photo_type` or `retrieval_scenario`.
5. **Planned Mitigation:** Challenge prompt explicitly instructs the LLM to inspect whether the user context differs.

---

## H. Analysis and Metrics

### H1. Tiny Category Sizes
1. **Edge Case:** A failure stage or photo type has only 2 records out of 250.
2. **Why It Matters:** Converting 2 records into a percentage (0.8%) can give an illusion of statistical precision.
3. **Expected System Behaviour:** Display raw counts alongside percentages, and add a footnote: *"Small sample count (n=2); interpret with caution."*
4. **How We Can Detect It:** Count < 5 in any category.
5. **Planned Mitigation:** UI helper automatically appends a small-sample flag to any category with fewer than 5 records.

---

### H2. Source Imbalance
1. **Edge Case:** 80% of records come from Reddit, and only 5% from App Store reviews.
2. **Why It Matters:** Reddit users may be more tech-savvy than typical phone users, creating platform bias.
3. **Expected System Behaviour:** Research Overview displays the source breakdown clearly and includes a visible callout highlighting source skew.
4. **How We Can Detect It:** Any single source represents > 60% of the dataset.
5. **Planned Mitigation:** Methodology section explicitly notes: *"Source distribution is skewed towards [Source]; findings reflect forum user behavior."*

---

### H3. Percentages Calculated on the Wrong Denominator
1. **Edge Case:** Calculating the percentage of `F2 — Expression Gap` using total *raw* records (including irrelevant ones) instead of total *relevant* records.
2. **Why It Matters:** Artificially deflates failure stage percentages.
3. **Expected System Behaviour:** All failure stage percentages must use `total_relevant_records` as the explicit denominator.
4. **How We Can Detect It:** Sum of failure stage percentages does not equal 100%.
5. **Planned Mitigation:** Analysis layer unit test verifies: `sum(failure_stage_counts) / len(relevant_records) == 1.0`.

---

### H4. Irrelevant Records Included in Research Statistics
1. **Edge Case:** A storage complaint gets accidentally included in the failure stage chart.
2. **Why It Matters:** Corrupts the core research metrics.
3. **Expected System Behaviour:** All analytical filters default to `is_relevant == 'Relevant'`.
4. **How We Can Detect It:** Check whether `is_relevant == 'Irrelevant'` rows exist in the filtered analytical DataFrame.
5. **Planned Mitigation:** Base query in `analysis.py` strictly slices `df[df['is_relevant'] == 'Relevant']` before passing data to charts.

---

### H5. Unknown Classifications Ignored
1. **Edge Case:** A researcher drops all `F8 — Unknown` records to make the charts look clean and decisive.
2. **Why It Matters:** Conceals real uncertainty and overstates research confidence.
3. **Expected System Behaviour:** `F8 — Unknown` is prominently included in all failure stage charts and tables.
4. **How We Can Detect It:** Absence of `F8` in chart categories when `F8` exists in data.
5. **Planned Mitigation:** Analysis pipeline explicitly mandates that `F8 — Unknown` is retained in all aggregations.

---

### H6. Correlation Interpreted as Causation
1. **Edge Case:** A chart shows that users looking for "vacation photos" frequently hit `F5 — Recognition Gap`, leading someone to say "vacations cause recognition failure".
2. **Why It Matters:** Unjustified causal claim.
3. **Expected System Behaviour:** UI text uses descriptive language (*"co-occurs frequently with"*, *"observed in"*) rather than causal claims (*"causes"*, *"leads to"*).
4. **How We Can Detect It:** Text audit of UI labels and summaries.
5. **Planned Mitigation:** Standardized phrasing guidelines in UI labels.

---

### H7. Dataset Frequency Presented as Population Prevalence
1. **Edge Case:** A slide or card says *"28% of Google Photos users struggle with expression"*.
2. **Why It Matters:** Factually false; 28% of *our collected public sample* struggled with expression.
3. **Expected System Behaviour:** Prominent persistent disclaimer on all metric dashboards: *"Frequencies reflect our collected sample (N=200–250), not population prevalence across Google Photos."*
4. **How We Can Detect It:** Any metric presented without sample size indicator `(n=X)`.
5. **Planned Mitigation:** UI formatting template: Always display `Percentage% (n=Count / N=Total)`.

---

### H8. Survey Evidence Mixed Directly with Public-Conversation Evidence
1. **Edge Case:** Mixing numbers from an ongoing survey into the public conversation CSV without distinction.
2. **Why It Matters:** Blurs distinct research methodologies and invalidates data lineage.
3. **Expected System Behaviour:** Keep public conversation evidence and survey evidence in separate, clearly labeled data stores.
4. **How We Can Detect It:** Mixed source IDs or methodology mismatches.
5. **Planned Mitigation:** Architecture keeps public records isolated; any future survey integration will have its own dedicated view.

---

## I. Privacy and Ethics

### I1. Public Post Contains a Username
1. **Edge Case:** A raw forum post includes the author's handle (e.g., `u/john_doe_99`).
2. **Why It Matters:** While public, displaying usernames in an academic/PM presentation is unnecessary and raises privacy concerns.
3. **Expected System Behaviour:** Anonymize or redact personal handles in the UI, displaying only the platform (e.g., `Reddit User`).
4. **How We Can Detect It:** Regex pattern detecting `u/username`, `@handle`.
5. **Planned Mitigation:** Pre-display cleaning function replaces identifiable handles with generic labels like `[User]`.

---

### I2. Public Post Contains Email Address or Phone Number
1. **Edge Case:** A user mistakenly included their contact info in a public review (e.g., *"Call me at 555-0192 to fix this"*).
2. **Why It Matters:** Severe PII (Personally Identifiable Information) risk.
3. **Expected System Behaviour:** Automatically redact emails and phone numbers during Phase 1 ingestion.
4. **How We Can Detect It:** Regex search for email patterns and phone number patterns.
5. **Planned Mitigation:** Automated redaction regex: `re.sub(r'[\w\.-]+@[\w\.-]+', '[REDACTED_EMAIL]', text)`.

---

### I3. Sensitive Personal Information in a Retrieval Story
1. **Edge Case:** A user describes searching for deeply sensitive photos (e.g., medical symptoms, legal disputes, intimate moments).
2. **Why It Matters:** Research ethics require respectful handling of sensitive qualitative data.
3. **Expected System Behaviour:** Preserve only what is necessary to understand the retrieval failure (e.g., `photo_type = "Medical Document"`), without sensationalizing.
4. **How We Can Detect It:** Keyword filters for sensitive personal domains.
5. **Planned Mitigation:** Ethics review checklist before finalizing `raw_evidence.csv`.

---

### I4. Exposing Public Usernames in the Web Interface
1. **Edge Case:** The Evidence Explorer table includes a column with author usernames.
2. **Why It Matters:** Exposes individuals unnecessarily when the research goal is understanding retrieval barriers, not tracking individuals.
3. **Expected System Behaviour:** Omit author usernames from the dataset schema entirely. Use only sequential IDs (`REC_001`).
4. **How We Can Detect It:** Check CSV column headers for `author`, `username`, or `user_id`.
5. **Planned Mitigation:** Schema design strictly excludes author identity fields; only `record_id` is stored.

---

## J. Application & Technical Failures

### J1. CSV File Missing
1. **Edge Case:** The application starts but `data/processed_evidence.csv` does not exist on disk.
2. **Why It Matters:** Python throws `FileNotFoundError` and Streamlit crashes.
3. **Expected System Behaviour:** Render a friendly setup screen: *"Processed dataset not found. Please run the data pipeline or check data/."*
4. **How We Can Detect It:** `try / except FileNotFoundError` block in `data_loader.py`.
5. **Planned Mitigation:** Friendly error boundary in `app/main.py` directing the user to setup steps.

---

### J2. CSV Schema Incorrect
1. **Edge Case:** A CSV file exists, but someone renamed or deleted the `failure_stage` column.
2. **Why It Matters:** Pandas code will crash with `KeyError`.
3. **Expected System Behaviour:** Validate column names on load; display exact missing column names in an error callout.
4. **How We Can Detect It:** Check `set(REQUIRED_COLUMNS).issubset(df.columns)`.
5. **Planned Mitigation:** Assertion check inside `data_loader.py` validates all required headers before returning DataFrame.

---

### J3. Application Starts with Empty Dataset
1. **Edge Case:** `raw_evidence.csv` has headers but zero rows.
2. **Why It Matters:** Charts crash when passed empty datasets without rows.
3. **Expected System Behaviour:** Display an empty state placeholder: *"Dataset is currently empty. 0 records found."*
4. **How We Can Detect It:** `len(df) == 0`.
5. **Planned Mitigation:** Early return with `st.info()` banner if DataFrame is empty.

---

### J4. Filter Returns Zero Records
1. **Edge Case:** A user selects filters: `Source = App Store`, `Failure Stage = F1`, `Photo Type = Receipt`, and no records match.
2. **Why It Matters:** Empty charts look broken.
3. **Expected System Behaviour:** Display a clean notification: *"No records match your selected filter combination. Try broadening your filters."*
4. **How We Can Detect It:** `len(filtered_df) == 0`.
5. **Planned Mitigation:** Guard check before rendering charts; displays `st.warning()` if row count is zero.

---

### J5. API Key Missing
1. **Edge Case:** The app is launched without setting `GEMINI_API_KEY` in `.env` or Streamlit secrets.
2. **Why It Matters:** Q&A and AI classification features will throw authentication errors.
3. **Expected System Behaviour:** Disable AI features gracefully; display an alert: *"API key not detected. Q&A is running in offline preview mode."*
4. **How We Can Detect It:** `os.getenv('GEMINI_API_KEY') is None`.
5. **Planned Mitigation:** Helper function checks for API key availability; hides or disables Q&A input with instructions to add key.

---

### J6. LLM API Unavailable / Server Error (5xx)
1. **Edge Case:** Google's AI API is temporarily down or unreachable.
2. **Why It Matters:** App could freeze or crash with an unhandled exception.
3. **Expected System Behaviour:** Catch exception; display: *"AI service is temporarily unavailable. Please try your question again in a moment."*
4. **How We Can Detect It:** Catch `APIError` or `ConnectionError`.
5. **Planned Mitigation:** All API calls wrapped in robust `try / except` blocks.

---

### J7. API Rate Limit Reached (429)
1. **Edge Case:** Rapidly submitting questions or batch processing exceeds the free tier RPM (requests per minute).
2. **Why It Matters:** API requests fail immediately.
3. **Expected System Behaviour:** Implement automatic exponential backoff (wait 2s, 4s, 8s) or display: *"Rate limit reached. Please wait 30 seconds before asking another question."*
4. **How We Can Detect It:** HTTP 429 status code.
5. **Planned Mitigation:** Use `time.sleep()` delays in batch processing and display friendly cooldown timers in the UI.

---

### J8. Internet Connection Unavailable
1. **Edge Case:** User runs the app locally while disconnected from Wi-Fi.
2. **Why It Matters:** Static pages (Overview, Failures, Memory) should still work from the local CSV, but AI Q&A will fail.
3. **Expected System Behaviour:** All browsing, filtering, and chart views work 100% offline. Only Q&A shows an offline warning.
4. **How We Can Detect It:** Socket connection test or failed API request.
5. **Planned Mitigation:** Decouple data visualization from the AI API; data viewing requires zero internet.

---

### J9. Malformed AI Response
1. **Edge Case:** LLM responds with corrupted text or cut-off JSON during live Q&A.
2. **Why It Matters:** Displaying broken code looks amateurish.
3. **Expected System Behaviour:** Catch parsing error; display: *"Unable to format response. Please retry."*
4. **How We Can Detect It:** JSON or markdown validation check.
5. **Planned Mitigation:** Fallback error handler renders raw text cleanly if formatting fails.

---

### J10. Chart Receives No Data
1. **Edge Case:** Plotly chart called with all NaN values.
2. **Why It Matters:** Renders an ugly blank gray box.
3. **Expected System Behaviour:** Replace chart with a clear text banner: *"Insufficient data to display this chart."*
4. **How We Can Detect It:** `df['column'].dropna().empty`.
5. **Planned Mitigation:** Check series validity before calling plotting functions.

---

### J11. Source URL Cannot Open
1. **Edge Case:** User clicks a source URL, but their browser blocks it or the URL is malformed.
2. **Why It Matters:** Frustrating user experience.
3. **Expected System Behaviour:** Ensure all links open in a new tab (`target="_blank"`) and validate that URLs start with `https://`.
4. **How We Can Detect It:** Check `url.startswith('http')`.
5. **Planned Mitigation:** Helper function prefixes missing schemes and sanitizes URLs before rendering links.

---

### J12. Streamlit Application Restarts Unexpectedly
1. **Edge Case:** Cloud server restarts or user refreshes page, losing their question history.
2. **Why It Matters:** Annoying to retype questions.
3. **Expected System Behaviour:** Preserve chat history in `st.session_state` during the active session.
4. **How We Can Detect It:** Check `st.session_state` keys on page load.
5. **Planned Mitigation:** Initialize session state variables on app startup.

---

### J13. Deployment Secrets Missing on Streamlit Cloud
1. **Edge Case:** Code is pushed to GitHub and deployed, but secrets were not pasted into the Streamlit Cloud dashboard.
2. **Why It Matters:** The deployed app cannot run AI queries.
3. **Expected System Behaviour:** Display an admin banner on the live site: *"Configuration required: Please set GEMINI_API_KEY in Streamlit Cloud Secrets."*
4. **How We Can Detect It:** Check `st.secrets.get('GEMINI_API_KEY') is None`.
5. **Planned Mitigation:** Clear diagnostic check in `app/main.py`.

---

## K. User Experience & Interface

### K1. User Does Not Understand Failure-Stage Labels
1. **Edge Case:** A visitor sees "F3 — Interpretation Gap" and has no idea what it means.
2. **Why It Matters:** Jargon alienates evaluators and stakeholders.
3. **Expected System Behaviour:** Every failure stage label includes a simple plain-English tooltip or subtitle (e.g., *"F3: Search engine misunderstood user's query"*).
4. **How We Can Detect It:** User testing observation.
5. **Planned Mitigation:** Use `st.help()` or hover tooltips beside every stage label and include a visible glossary.

---

### K2. Too Many Charts (Dashboard Overload)
1. **Edge Case:** Putting 15 charts on one screen.
2. **Why It Matters:** Visual fatigue; the researcher cannot identify the key takeaway.
3. **Expected System Behaviour:** Limit each page to 2–3 high-impact charts accompanied by summary takeaways.
4. **How We Can Detect It:** Visual review of page density.
5. **Planned Mitigation:** Group related charts into tabs or clean expandable sections.

---

### K3. Dashboard Becomes Text-Heavy
1. **Edge Case:** Dumping raw CSV tables with 20 columns onto the screen without formatting.
2. **Why It Matters:** Evaluators cannot read giant unformatted blocks of text.
3. **Expected System Behaviour:** Present information in bite-sized evidence cards with badges, highlights, and collapsed expanders.
4. **How We Can Detect It:** Horizontal scrolling required to read text.
5. **Planned Mitigation:** Style evidence records as clean card components showing only essential fields initially.

---

### K4. Filters Are Confusing
1. **Edge Case:** 8 different dropdown filters stacked together where selecting one causes others to break.
2. **Why It Matters:** Frustrating navigation.
3. **Expected System Behaviour:** Keep filters simple (Source, Failure Stage, Photo Type) and include a single "Reset All Filters" button.
4. **How We Can Detect It:** Multi-filter conflict states.
5. **Planned Mitigation:** Dedicated "Clear Filters" button that resets `st.session_state`.

---

### K5. User Cannot Locate Original Evidence
1. **Edge Case:** A user reads a great insight on the Overview but cannot find the quotes that generated it.
2. **Why It Matters:** Destroys the promise of evidence traceability.
3. **Expected System Behaviour:** Every summary card provides a direct link or button: *"Inspect these 14 records in Evidence Explorer"*.
4. **How We Can Detect It:** User journey testing.
5. **Planned Mitigation:** Cross-page deep linking via session state filters.

---

### K6. AI Answer Appears More Authoritative Than Underlying Evidence
1. **Edge Case:** The LLM generates a fluent, highly polished response based on only 2 vague forum comments.
2. **Why It Matters:** Gives false confidence to decision-makers.
3. **Expected System Behaviour:** Display an evidence strength indicator beside every answer (e.g., `Based on 2 records — Low sample size`).
4. **How We Can Detect It:** Discrepancy between LLM response confidence and record count.
5. **Planned Mitigation:** UI explicitly shows the exact count of cited records directly above the answer text.

---

### K7. Methodology Limitations Are Hidden
1. **Edge Case:** Caveats about sample size and public forum bias are buried in a subfolder readme.
2. **Why It Matters:** Academic evaluators will mark down the project for lack of scientific rigor.
3. **Expected System Behaviour:** Place a prominent, permanently visible "Methodology & Limitations" tab or expander right on Page 1 (Overview).
4. **How We Can Detect It:** UI inspection.
5. **Planned Mitigation:** Dedicated expandable section on the home screen explaining sample size, source bias, and directional limitations.

---

### K8. Mobile / Small-Screen Readability Issues
1. **Edge Case:** An evaluator opens the deployed URL on an iPad or phone, and wide tables get cut off.
2. **Why It Matters:** Poor presentation impression.
3. **Expected System Behaviour:** Use responsive column layouts (`st.columns`) that stack vertically on narrow screens.
4. **How We Can Detect It:** Test app on mobile browser viewports.
5. **Planned Mitigation:** Design using single-column flow and auto-wrapping text containers.

---

## L. Research-Integrity Red Flags

> [!CAUTION]
> In the following situations, RecallScope **MUST NOT** make a strong or definitive conclusion.

```text
+------------------------------------------------------------------------+
|                   RESEARCH-INTEGRITY RED FLAG CHECK                    |
|                                                                        |
|  [!] Fewer than minimum supporting records?  ──> FLAG: Low Sample Size |
|  [!] Found on only ONE source?               ──> FLAG: Source Bias     |
|  [!] Evidence contradicts itself?            ──> FLAG: Ambiguous       |
|  [!] AI confidence is Low?                   ──> FLAG: Uncertain       |
|  [!] Conclusion requires missing facts?      ──> FLAG: Unsupported     |
|                                                                        |
|  ACTION: System refuses definitive claim & displays explicit warning.  |
+------------------------------------------------------------------------+
```

### L1. Fewer Than a Meaningful Number of Supporting Records
1. **Red Flag:** An insight is supported by only 1 or 2 records.
2. **Simple Example:** Asserting *"Users always switch to Apple Photos after failure"* because 2 Reddit comments said so.
3. **Why It Matters:** Anecdote masquerading as data.
4. **Expected System Behaviour:** Refuse to call it a "pattern" or "trend"; label it as an *"isolated observation (n=2)"*.
5. **How We Can Detect It:** `citation_count < MIN_SAMPLE_THRESHOLD` *(configurable research rule)*.
6. **Planned Mitigation:** UI displays an orange warning badge whenever a cited claim has fewer than a configurable number of supporting records.

---

### L2. Finding Exists on Only One Source
1. **Red Flag:** A pattern appears 20 times, but *all 20* come exclusively from Reddit r/googlephotos.
2. **Why It Matters:** Could be an artifact of Reddit community culture rather than a Google Photos product reality.
3. **Expected System Behaviour:** Display a source skew warning: *"This pattern was observed exclusively in Reddit records; not corroborated across App Store or Google Help sources."*
4. **How We Can Detect It:** `unique_sources_in_sample == 1`.
5. **Planned Mitigation:** System checks source diversity and flags single-source findings in the UI.

---

### L3. Evidence Is Ambiguous
1. **Red Flag:** The underlying user statements can be interpreted in multiple conflicting ways.
2. **Simple Example:** User says *"Search brought back nothing"*, which could mean zero results or zero relevant results.
3. **Why It Matters:** Building a feature based on a misunderstood quote wastes engineering resources.
4. **Expected System Behaviour:** Default to `F8 — Unknown` and display the ambiguity explicitly.
5. **How We Can Detect It:** LLM reasoning identifies multiple equally plausible failure stages.
6. **Planned Mitigation:** Prompt instruction forbids picking a stage when two stages have equal likelihood.

---

### L4. Evidence Contradicts Itself
1. **Red Flag:** Two distinct user groups report opposite experiences under the same scenario.
2. **Simple Example:** Half of users say facial recognition found the photo immediately; the other half say facial recognition grouped completely wrong people.
3. **Why It Matters:** A single takeaway would be misleading.
4. **Expected System Behaviour:** Surface the contradiction side-by-side as a "Key Research Tension" rather than smoothing it away into an average.
5. **How We Can Detect It:** Opposing failure stages on identical retrieval scenarios.
6. **Planned Mitigation:** "Challenge an Insight" actively highlights contradictions as valuable research discoveries.

---

### L5. AI Confidence Is Low
1. **Red Flag:** The classification LLM outputs `evidence_strength = "Low"`.
2. **Why It Matters:** Low-confidence AI guesses should not drive product strategy.
3. **Expected System Behaviour:** Exclude low-confidence records from high-level takeaway cards, or display them with a dotted "low confidence" border.
4. **How We Can Detect It:** Check `evidence_strength` column.
5. **Planned Mitigation:** UI provides a toggle: *"Exclude low-confidence classifications from charts"*.

---

### L6. Classification Requires Information Not Contained in Original Text
1. **Red Flag:** An analyst or AI assumes a user was using an iPhone when the post never mentioned iOS.
2. **Why It Matters:** Introduces ungrounded speculation into the scientific record.
3. **Expected System Behaviour:** Mark the field as `"Unknown"`.
4. **How We Can Detect It:** Fact-checking prompts verifying claims against raw text.
5. **Planned Mitigation:** Prompt rule strictly penalizes inferring unstated device, OS, or user demographics.

---

### L7. Proposed Conclusion Goes Beyond the Dataset
1. **Red Flag:** Claiming *"Fixing this will increase Google Photos user retention by 5%"*.
2. **Why It Matters:** Qualitative forum discovery cannot project macro-business metrics without telemetry data.
3. **Expected System Behaviour:** Reject business projection claims; reframe strictly to user behavioral friction points observed in the qualitative data.
4. **How We Can Detect It:** Q&A queries asking for ROI, revenue, or global retention predictions.
5. **Planned Mitigation:** System prompt states: *"RecallScope evaluates qualitative discovery evidence only; it does not forecast revenue, retention, or business ROI metrics."*

---

### L8. Research Being Used to Confirm a Predetermined Solution
1. **Red Flag:** A stakeholder asks only questions designed to prove that conversational voice search is the only answer.
2. **Why It Matters:** The fatal flaw of product discovery is confirmation bias.
3. **Expected System Behaviour:** The system steers the user to the "Challenge an Insight" tool to actively surface counter-evidence and alternative failure points (e.g., visual clutter, recognition gap, indexing gap).
4. **How We Can Detect It:** One-sided solution-seeking questions.
5. **Planned Mitigation:** Prompt and UI guidelines reinforce RecallScope's identity: **an objective discovery engine to uncover problems, not a tool to rubber-stamp predetermined solutions**.
