# RecallScope — Master Context & Problem Statement

> **Document Type:** Master Context Document  
> **Status:** Active Reference / Ground Truth  
> **Target System:** RecallScope (AI-Powered Discovery Engine for Google Photos Retrieval Research)

---

## 1. Project Overview

**RecallScope** is an AI-powered research and discovery engine designed to investigate why vague-memory photo retrieval fails in photo management platforms like Google Photos.

When users know a photo exists in their library but cannot precisely describe it (lacking exact dates, locations, or clear keywords), their search journeys often break down. RecallScope systematically collects, filters, and analyzes genuine public user conversations to uncover the anatomy of these failures.

---

## 2. Business Goal

Google Photos wants to increase the percentage of users who successfully retrieve a photo they remember but cannot precisely describe when they begin searching.

---

## 3. Core Research Question

> *"When people know a photo exists but cannot precisely describe it, where does retrieval break despite them remembering parts of the photo or experience?"*

---

## 4. Research Objectives

Build an AI-powered discovery engine that analyzes approximately 200–250 genuine public conversations related to finding and retrieving photos.

The engine must support a Product Manager to:
1. **Separate** relevant photo-retrieval evidence from unrelated Google Photos complaints.
2. **Understand** what users remember about photos they are trying to retrieve.
3. **Understand** what information users have forgotten.
4. **Identify** where the retrieval journey breaks.
5. **Identify** user behaviours and workarounds adopted after retrieval failure.
6. **Discover** recurring retrieval problems and possible behavioural user segments.
7. **Compare** evidence across different sources.
8. **Identify** contradictory evidence and areas of uncertainty.
9. **Ask** natural-language research questions and receive answers strictly grounded only in collected evidence.

---

## 5. What RecallScope Is

- **An AI-powered discovery engine** built for product discovery and exploratory research.
- **An evidence-grounded research tool** that helps Product Managers interrogate qualitative evidence at scale.
- **A diagnostic platform** designed to uncover user memory patterns, failure stages, and post-failure workarounds.
- **An objective lens** that preserves raw user evidence alongside AI interpretations.

---

## 6. What RecallScope Is NOT

> [!IMPORTANT]
> RecallScope is **NOT** the final Google Photos product solution.

- It is **not** a consumer-facing photo search tool or replacement for Google Photos.
- It must **not** begin with the assumption that any specific feature (e.g., conversational search, clarification questions, visual browsing, candidate elimination) is the correct solution.
- It is **not** an engine designed to validate predetermined conclusions or biases.
- It is **not** a statistical census of all Google Photos users worldwide.

---

## 7. Target Public Data Sources

The research dataset will be compiled from approximately 200–250 genuine public records across platforms including:
- **Reddit** (e.g., r/googlephotos and related forums)
- **Google Photos Help / Community forums**
- **Google Play reviews**
- **Apple App Store reviews**
- **YouTube comments**
- **Other relevant public forums** where photo retrieval is discussed

---

## 8. Dataset Requirements

### Record Metadata Schema
Every collected public record must preserve:
- **Unique ID**: Persistent identifier for traceability.
- **Source**: Origin platform (e.g., Reddit, Play Store).
- **Original text**: Unaltered user statement.
- **Source URL**: Direct link to the public post or comment.
- **Date**: Timestamp/date where available.

### Non-Fabrication Rules
Never fabricate:
- Records
- Quotes
- URLs
- Dates
- Statistics
- User behaviours
- Research findings

### Relevance Filtering
The raw corpus may contain unrelated Google Photos complaints, including:
- Backup failures
- Deleted photos
- Storage quota problems
- Account access problems
- Upload problems
- Sync problems

**Filter Rule:** These complaints must be classified as **irrelevant** unless the record also contains meaningful evidence about trying to retrieve a remembered photo.

---

## 9. Retrieval Journey

The conceptual journey from initial memory to final retrieval follows a 7-stage linear progression:

```text
Recall
  → Expression
      → Interpretation
          → Candidate Retrieval
              → Recognition
                  → Refinement
                      → Successful Retrieval
```

---

## 10. Failure Stage Taxonomy

When retrieval fails, the breakdown is classified into one of the following eight potential stages:

| Stage ID | Stage Name | Description |
|---|---|---|
| **F1** | **Recall Gap** | The user cannot remember enough potentially useful information. |
| **F2** | **Expression Gap** | The user remembers useful information but struggles to translate it into a search query. |
| **F3** | **Interpretation Gap** | The user expresses useful clues, but the search system appears to interpret them incorrectly. |
| **F4** | **Candidate Gap** | The intended photo is not adequately surfaced among candidate results. |
| **F5** | **Recognition Gap** | Potentially relevant results exist, but identifying the intended photo requires excessive inspection or scrolling. |
| **F6** | **Refinement Gap** | After an unsuccessful attempt, the user does not know how to improve or change the search. |
| **F7** | **Coverage / Indexing Gap** | Available metadata or indexed visual information appears insufficient for retrieval. |
| **F8** | **Unknown** | There is insufficient evidence in the record to confidently classify the failure. |

---

## 11. AI Analysis Requirements

For records classified as relevant, AI extraction must extract information **only when supported by the original evidence**.

### Extraction Fields
- **Retrieval intent**: What the user was seeking to achieve.
- **Photo type**: Category/nature of photo sought.
- **Retrieval scenario**: Context surrounding the search.
- **Remembered clues**: Specific attributes recalled by the user.
- **Forgotten clues**: Details the user explicitly acknowledges forgetting.
- **Query / search behaviour**: Initial queries or terms attempted.
- **Reformulation behaviour**: How queries were changed after initial attempts.
- **Manual browsing behaviour**: Scrolling, timeline scrubbing, album inspection.
- **Workaround**: Actions taken after failure (e.g., asking friends, external apps, giving up).
- **Failure stage**: Classification mapped to F1–F8.
- **Failure reason**: Textual justification based directly on evidence.
- **Retrieval outcome**: Success, partial success, failure, or abandonment.
- **Evidence strength**: Confidence score / assessment based on record completeness.

### Candidate-Evaluation Investigation
The analysis must specifically investigate candidate-evaluation behaviours:
- Were relevant candidates apparently returned?
- Were there too many candidates returned?
- Were candidates visually similar, creating confusion?
- Did the user struggle to recognise the intended photo?
- Was excessive scrolling required?

---

## 12. Research Integrity Rules

1. **Do not force every record into a theme:** Allow outliers and unique cases to exist.
2. **Use Unknown (F8) when evidence is insufficient:** Never guess a failure stage.
3. **Do not infer information not provided:** Stick strictly to what the user explicitly stated.
4. **Keep original evidence accessible:** Display the raw record alongside every AI classification.
5. **Ensure complete traceability:** Every summary and aggregate finding must trace back to individual record IDs.
6. **Separate evidence from interpretation:** Distinguish what the user said from AI analysis.
7. **Surface contradictions:** Highlight conflicting evidence rather than smoothing it away.
8. **Avoid confirmation bias:** Do not optimize analysis to support a predetermined feature or solution.
9. **No broad population claims:** Do not claim public forum conversations represent all Google Photos users.
10. **Directional evidence only:** Treat frequencies within this dataset as directional signals, not population prevalence.

---

## 13. Planned Discovery Engine Features

The discovery engine application will eventually provide six core capabilities:

1. **Research Overview**
   - Total dataset size and completion status
   - Source mix distribution
   - Relevant vs. irrelevant record breakdown
   - High-level research statistics
2. **Failure Explorer**
   - Multi-dimensional filtering by failure stage (F1–F8), source, photo type, and retrieval scenario
   - Drill-down into specific failure breakdowns
3. **Memory Explorer**
   - Granular breakdown of what users remembered vs. what they had forgotten
   - Analysis of clue types (temporal, spatial, visual, conceptual) that emerge during searches
4. **Evidence Explorer**
   - Detailed inspection interface allowing the Product Manager to review original raw records behind any finding
5. **Ask the Evidence**
   - Natural-language question-answering interface
   - Answers must draw strictly from collected evidence, cite record IDs, and refuse unsupported claims
6. **Challenge an Insight**
   - Dedicated counter-analysis tool allowing researchers to query specifically for evidence that contradicts, weakens, or complicates a proposed hypothesis

---

## 14. Expected Research Process

The end-to-end research methodology spans the following sequential stages:

```text
1. Approximately 200–250 Public Records Collected
   ↓
2. Relevance Filtering (Separate retrieval evidence from complaints)
   ↓
3. AI-Assisted Classification (Extract clues, stages, behaviours)
   ↓
4. Evidence Analysis & Synthesis (Patterns, contradictions, gaps)
   ↓
5. Survey Evidence Collection (Ongoing)
   ↓
6. User Interviews (5–6 in-depth sessions)
   ↓
7. Target Segment Selection
   ↓
8. Root-Cause Identification
   ↓
9. Measurable Problem Definition
   ↓
10. Solution Exploration
   ↓
11. Separate Functional MVP
   ↓
12. Target User Testing (Minimum 3 target users)
```

---

## 15. Known Information

The following items are established project parameters:
- **Defined problem scope**: Vague-memory photo retrieval failure in Google Photos.
- **Dataset target**: ~200–250 genuine public records across defined public channels.
- **Preserved schema**: Unique ID, Source, Original Text, Source URL, Date.
- **Relevance criteria**: Retrieval-focused evidence included; unrelated technical complaints excluded.
- **Journey model**: 7-step linear retrieval journey.
- **Taxonomy**: 8 failure stages (F1–F8) including an explicit Unknown stage.
- **Architectural intent**: Discovery engine with 6 defined functional views.
- **Core constraints**: Strict groundedness, complete traceability, no data fabrication.

---

## 16. Current Research Hypotheses

The following hypotheses are guiding inquiries that **require validation** against the collected data:
- *Hypothesis 1:* Photo retrieval breakdowns are not evenly distributed; certain stages (e.g., Expression Gap F2 or Recognition Gap F5) may cause disproportionate failure.
- *Hypothesis 2:* Users frequently remember subjective or contextual clues (emotions, events, visual relationships) that traditional keyword or metadata search engines cannot interpret (F3).
- *Hypothesis 3:* Even when relevant candidate photos are retrieved (F4 passes), users face a recognition barrier (F5) due to visual similarity or overwhelming volume.
- *Hypothesis 4:* When retrieval fails, users lack clear mental models for query refinement (F6), resulting in repetitive reformulation or complete abandonment.
- *Hypothesis 5:* Public forum posts contain sufficiently rich qualitative detail to extract structured clue-memory patterns.

---

## 17. Information Still To Be Collected

The following empirical data has **not yet been gathered**:
- The complete corpus of ~200–250 verified public records (collection in progress).
- Complete survey responses and quantitative survey analysis (ongoing).
- Findings and transcripts from the 5–6 user interviews.
- Quantitative distribution and empirical counts for each failure stage (F1–F8).
- Evidence-backed behavioral user segments.
- Confirmed root causes of vague-memory retrieval breakdown.
- User feedback from functional MVP testing.

---

## 18. Conclusions We Are NOT Yet Allowed To Make

> [!CAUTION]
> To preserve research integrity, the following conclusions are strictly prohibited at this stage:

1. **No predetermined product solutions**: We must not conclude that conversational search, clarification questions, visual browsing, candidate elimination, or any specific UI mechanism is the answer.
2. **No final target segment**: We must not claim to know which user segment is the primary target before evidence synthesis and interviews.
3. **No final root cause**: We must not declare the definitive root cause of retrieval failure.
4. **No final problem definition**: We must not lock in a final problem definition prior to completing the research stages.
5. **No population-level prevalence**: We must not extrapolate public conversation frequencies to represent the entire Google Photos user base.
6. **No uncollected data claims**: We must not cite survey percentages, interview findings, or MVP metrics that do not yet exist.
7. **No inferred facts**: We must not impute thoughts, feelings, or details beyond the verbatim evidence provided by users.

---

## 19. Success Criteria for the Discovery Engine

The RecallScope discovery engine will be considered successful if it achieves:
1. **High Relevance Precision**: Accurately filters out generic support complaints while retaining genuine retrieval struggles.
2. **Complete Traceability**: 100% of generated insights, categories, and AI summaries link directly to specific record IDs and raw text.
3. **Grounded Question Answering**: The "Ask the Evidence" feature answers PM queries using exclusively cited evidence and acknowledges when evidence is missing.
4. **Contradiction Surfacing**: The "Challenge an Insight" feature actively identifies counter-examples and ambiguities rather than confirming preconceived notions.
5. **Integrity Preservation**: Zero fabricated records, quotes, dates, or statistics across all views and outputs.
6. **Actionable Directional Guidance**: Delivers structured clarity to the Product Manager to inform subsequent survey analysis, interview protocols, and problem framing.
