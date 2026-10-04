# RecallPath — MVP plan

Status: planning only. No product code, package changes, commits, or deployment until this plan is approved.

RecallPath is a separate prototype. It tests whether recognition-assisted narrowing helps experience-led retrievers reach a remembered photo. That is a hypothesis, not a result. The five observed sessions are n=5 qualitative observations, not population prevalence.

RecallScope stays as it is. This document does not replace `docs/architecture.md` or `docs/implementation-plan.md`.

## Existing architecture that stays untouched

RecallScope is a single Streamlit app:

- Entry: `app/main.py` (`streamlit run app/main.py`)
- UI and research logic: `app/utils/`
- Offline phase scripts: `app/phase2_run.py` through `app/phase8_run.py`, `app/classify_pipeline.py`
- Research files: `data/public_evidence_raw.csv`, `data/public_evidence_relevance.csv`, `data/public_evidence_classified.csv`, `data/research_analysis.json`, `data/primary_research_interviews.json`, `data/public_evidence_raw_batch1.csv`, `data/phase3_audit_corrections.csv`
- Planning docs: `docs/architecture.md`, `docs/implementation-plan.md`, `docs/edge-case.md`, `docs/problemStatement.md`

AI today is text-only:

- Provider: Groq, via the `groq` package (`requirements.txt`: `groq>=0.13.0`)
- Model constant in `app/utils/llm_helper.py`: `openai/gpt-oss-120b`
- Calls: `chat.completions.create` with text messages and JSON mode
- Key: `GROQ_API_KEY` from the environment, `.env`, or Streamlit secrets. The key is never printed.
- `GEMINI_API_KEY` is an unused placeholder in `.env.example` and `app/utils/config.py`. Phase 3 does not call Gemini.

Dependencies today: `streamlit`, `pandas`, `python-dotenv`, `groq`. No image library is imported by RecallScope.

RecallPath must not edit those files, must not read the research corpus as photo-search data, and must not add itself to the RecallScope sidebar.

## Proposed architecture

A second Streamlit app in an isolated `recallpath/` package. Same repository, same Python environment, separate entry point:

```text
streamlit run recallpath/main.py
```

Later public deployment, only after a separate approval, would be a second Streamlit Community Cloud app in this repo, with main file `recallpath/main.py`, reusing the existing `GROQ_API_KEY` secret. RecallScope’s app entry stays `app/main.py`.

Session flow:

```text
Upload small collection
  -> describe the memory in natural language
  -> text model structures clues and keeps uncertainty
  -> vision model describes each uploaded photo
  -> rank a candidate grid from those descriptions
  -> recognition feedback reranks or broadens
  -> success state and session diagnostics
```

No database. No vector store. No RecallScope imports.

## AI and image understanding

The current RecallScope model cannot see images. `openai/gpt-oss-120b` receives text only.

Groq’s documented vision path, checked against https://console.groq.com/docs/vision on 4 October 2026, uses the same API and the same `groq` client with a different model:

- Model: `qwen/qwen3.8-27b`
- Endpoint: `chat.completions`
- Local images: base64 data URL
- JSON mode: supported
- Limits stated on that page: 3 images per request, 20MB request size for an image URL, about 2048 input tokens per image, 131K context

RecallPath would call two models with the existing key:

| Job | Model | Why |
|---|---|---|
| Interpret the memory | `openai/gpt-oss-120b` | Already used in this repo for strict JSON. Text only. |
| Describe each uploaded photo | `qwen/qwen3.8-27b` | Documented vision model on the same Groq account. |

No new vendor and no new API key. The vision model must be confirmed live on this key during implementation. If that model is unavailable, the screen says analysis failed and does not invent photo descriptions.

Each photo is analysed on its own, even though the API allows three images per request. One photo per call keeps a failure on a single image from discarding the others.

Vision output is a structured observation, not an identity judgment:

- people count and arrangement, without naming who they are
- setting
- objects
- visible appearance, such as clothing colour
- activity only when it is visible
- what is not visible
- per-field confidence: high, medium, low, or unknown
- `analysis_status`: `ok`, `weak`, or `failed`

Social facts the pixels cannot prove stay user-stated. “Cousins” remains a memory clue. The photo observation can say “a group of people.” It must not convert that into “these are cousins.”

## Candidate retrieval and reranking

Rankings come from the vision observations and the structured memory. There is no hardcoded photo order.

Memory JSON separates three lists:

- `user_stated`: the person said it, including short quotes
- `hedged`: the person marked it as unsure (“I think”, “maybe”)
- `ai_inferred`: the model’s interpretation, with the basis and a confidence

A hedged place such as “I think it was Goa” stays hedged. It is never stored as `location = Goa`.

Matching is soft. For every photo and every clue, the text model compares the clue with that photo’s observation and returns one of: `supported`, `partial`, `not_visible`, `contradicted`. Application code then applies fixed weights:

| Clue | Supported or partial | Contradicted | Not visible |
|---|---|---|---|
| Explicit user-stated | strong plus | moderate minus | zero |
| Hedged | small plus | zero | zero |
| AI-inferred | small plus | zero | zero |

A contradiction never removes a photo. Hedged and inferred clues never reduce a score. Photos whose analysis failed stay in an “could not check” group on the first screen, so a failed call cannot hide the target.

First screen, for a collection of at most 12 photos: show the whole collection, strongest matches first, then other photos, then any unchecked photos. Narrowing changes the visible window. The full set remains in the session.

Recognition actions:

- **This looks closer.** The chosen photo’s high-confidence observations become extra positive clues. Re-rank. Push the previous ranking onto an undo stack.
- **This is the photo.** Success state. Record diagnostics. Stop retrieval.
- **Not this.** Hide that photo from the current window only. Undo can bring it back.
- **None of these / broaden search.** Restore the previous wider window.
- **Not sure.** Record the event. Leave the ranking unchanged.
- **Back / undo.** Pop the ranking stack.

The target is removed from the session only when the user deletes the collection or ends the session. One bad inference or one “Not this” cannot delete it from the library.

The clue panel shows which user-stated, hedged, and inferred clues are affecting the current order.

## Privacy and data handling

- Uploaded bytes and vision JSON live in Streamlit `session_state` for that browser session.
- Nothing is written into `data/`, git, or a database.
- An explicit “Remove my photos” control clears the session collection.
- The first screen states that each photo is sent to Groq so the vision model can describe it, that RecallPath does not add those photos to the RecallScope research files, and that Groq’s own retention terms still apply. This prototype does not control Groq’s logs.
- EXIF location and timestamps are not read in this MVP.
- The vision prompt asks for visible scene facts, not names of people.

On Streamlit Community Cloud the process is ephemeral, but the image still exists in server memory while the session is open, and a copy is sent to Groq. That is the privacy tradeoff of using the existing key.

## File structure

```text
recallpath/
  main.py
  components/
    privacy_notice.py
    upload_step.py
    memory_step.py
    candidate_grid.py
    feedback_bar.py
    success_state.py
  services/
    groq_client.py
    memory_interpreter.py
    image_analyser.py
    retriever.py
  utils/
    schema.py
    scoring.py
    session_store.py
    diagnostics.py

docs/recallpath/
  mvp-plan.md
```

`requirements.txt` is shared. The only likely addition is Pillow, so uploads can be resized before the Groq call. Streamlit already depends on Pillow transitively. Declaring it is a requirements change and waits for approval. No other package is proposed.

## Implementation phases

After approval, build in this order. Each phase stays inside `recallpath/` and `docs/recallpath/`.

1. App shell, privacy notice, upload into session, remove-photos control. No model calls.
2. Memory interpreter on `openai/gpt-oss-120b`, with stated / hedged / inferred labels.
3. One-image vision analysis on `qwen/qwen3.8-27b`, with honest failure states.
4. Soft scoring and the first visual candidate grid.
5. Recognition actions, undo stack, and broaden.
6. Success state and session diagnostics. Diagnostics are labelled as session logs, not research results.
7. Local trial with a small collection the builder supplies. No claim that this is the 3-user test.

Deploy, commit, and push stay out of these phases until you ask for them.

## Risks and limitations

- Vision quality can be wrong. Clothing colour, counts, and places can be misread. The UI has to show that as an observation with confidence, and scoring must not hard-filter on it.
- The documented vision model can change. Llama 4 Scout on Groq was already deprecated. The implementation should pin `qwen/qwen3.8-27b` and fail clearly if Groq rejects it.
- A 12-photo collection means about 12 vision calls, plus memory and matching calls. Free-tier rate limits were not re-checked in this plan. A slow or capped key will make indexing feel slow. The UI should show per-photo progress.
- Session memory holds image bytes. The app should resize before storing and before sending. Large original files can strain a Streamlit Cloud instance.
- “Cousins”, “my trip”, and “about two years ago” are not visible facts. The product can only use them as memory clues.
- This build cannot show that recognition-assisted narrowing reduces effort. That needs the later test with at least three real users.
- Sending personal photos to a third-party API is a real privacy limit of this design.

## Decisions needed before any code

1. Approve this plan.
2. Approve calling `qwen/qwen3.8-27b` with the existing `GROQ_API_KEY`. RecallScope continues to call `openai/gpt-oss-120b` only.
3. Approve sending uploaded photos to Groq for description.
4. Approve a cap of 12 photos per session, JPEG / PNG / WEBP, resized before the API call.
5. Approve adding Pillow to `requirements.txt` if the implementation imports it directly.
6. Leave commit, push, and a second Streamlit deployment for a later explicit request.
