"""
RecallScope — Phase 6 Ask the Evidence

Selects saved records with transparent keyword matching, then asks Groq to
answer from that context only. Importing this module does not call Groq.
Quotes shown to the evaluator are copied from the saved original text.
"""

import re
from typing import Any, Dict, List, Optional, Sequence

from app.utils.discovery_data import load_discovery_records, load_research_analysis
from app.utils.llm_helper import (
    LLM_MODEL,
    ClassificationError,
    _call_model,
    _parse_json_object,
    _redact_secrets,
    is_groq_configured,
)

CORPUS_LIMITATION = (
    "This interim public-evidence corpus cannot establish how common a problem is "
    "among Google Photos users. Counts here are not population prevalence."
)

EXAMPLE_QUESTIONS = [
    "What evidence do we have of manual scrolling?",
    "What do users appear to remember about photos they are trying to retrieve?",
    "Which findings are still uncertain?",
    "What does the corpus suggest about search queries not returning expected photos?",
    "What evidence contradicts a recognition-gap hypothesis?",
    "Which retrieval problems have the strongest evidence?",
]

STOPWORDS = {
    "a", "an", "the", "of", "to", "and", "or", "in", "on", "for", "we", "do", "does",
    "what", "which", "about", "this", "that", "is", "are", "have", "has", "with",
    "from", "after", "before", "their", "they", "them", "it", "be", "can", "cannot",
    "not", "into", "when", "where", "why", "how", "user", "users", "photo", "photos",
    "google", "evidence", "corpus", "problem", "problems", "appear", "appears",
    "still", "suggest", "trying", "retrieve", "retrieval",
}

SYSTEM_PROMPT = """You are the RecallScope research assistant for Ask the Evidence.

You answer only from the supplied saved records and the supplied corpus summary.
You are a research tool, not a general chatbot.

Rules:
- Use only the supplied evidence. Do not use general knowledge about Google Photos.
- Do not invent evidence, record IDs, quotes, counts, or causes.
- Do not write quotations. Cite record IDs only. The application attaches the original text.
- Distinguish the original post from the audited classification. The classification is an interpretation.
- Unknown must stay Unknown. Do not treat Unknown as No.
- If records conflict, say the evidence is mixed.
- If the supplied evidence cannot answer the question, say the current corpus does not provide enough evidence.
- Do not turn a repeated observation into a causal claim.
- Do not agree with a hypothesis just because the question asserts it.
- Never say a corpus frequency is prevalence among Google Photos users.
- Never select a final product problem.
- Never recommend a product solution.
- supporting_record_ids and limiting_record_ids must be chosen only from the supplied record IDs.

Return one JSON object with these keys:
short_answer, evidence_summary, supporting_record_ids, limiting_record_ids,
evidence_is_mixed, evidence_is_insufficient, evidence_strength_note
"""


def _tokens(text: str) -> set:
    words = set(re.findall(r"[a-z0-9']+", str(text).lower()))
    expanded = set()
    for word in words:
        if word in STOPWORDS or len(word) < 3:
            continue
        expanded.add(word)
        if word.endswith("ing") and len(word) > 5:
            expanded.add(word[:-3])
        if word.endswith("ed") and len(word) > 4:
            expanded.add(word[:-2])
    return expanded


def _record_text(record: Dict[str, Any]) -> str:
    parts = [
        record.get("original_text", ""),
        record.get("primary_failure_stage", ""),
        record.get("retrieval_outcome", ""),
        record.get("remembered_clues", ""),
        record.get("missing_or_forgotten_clues", ""),
        record.get("search_or_browse_behavior", ""),
        record.get("reformulation_behavior", ""),
        record.get("manual_browsing_behavior", ""),
        record.get("workaround", ""),
        record.get("failure_reason", ""),
        record.get("evidence_strength", ""),
        f"manual scroll signal {record.get('manual_scroll_signal', '')}",
        f"recognition difficulty signal {record.get('recognition_difficulty_signal', '')}",
        f"candidate overload signal {record.get('candidate_overload_signal', '')}",
        f"human review {record.get('needs_human_review', '')}",
        record.get("relevance_label", ""),
    ]
    return " ".join(str(part) for part in parts if str(part).strip())


def _excerpt(text: str, limit: int = 280) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _is_leading(question: str) -> bool:
    text = question.lower()
    markers = (
        "prove",
        "proves",
        "proven",
        "population",
        "prevalence",
        "all google photos users",
        "main google photos problem",
        "the main problem",
    )
    return any(marker in text for marker in markers)


def _affirms_hypothesis(answer: str) -> bool:
    text = answer.lower().strip()
    if text.startswith("yes"):
        return True
    return bool(re.search(r"\b(this proves|is the main problem|main cause is recognition)\b", text))


def _corpus_summary(analysis: Dict[str, Any]) -> str:
    stages = []
    for stage in analysis.get("failure_stages", []):
        stages.append(f"{stage['failure_stage']}: {stage['record_count']}")
    challenges = [
        item.get("challenge", "")
        for item in analysis.get("contradictions_and_evidence_gaps", {}).get("challenges", [])
    ]
    summary = analysis.get("input", {})
    lines = [
        "Saved analysis summary. These are counts from this corpus, not user quotations, and not population prevalence.",
        f"Raw records: {summary.get('raw_record_count')}. Classified records: {summary.get('classified_record_count')}.",
        f"Uncertain and not auto-classified: {', '.join(summary.get('uncertain_record_ids', [])) or 'none'}.",
        f"Human review count: {summary.get('human_review_count')}.",
        "Failure-stage counts: " + "; ".join(stages),
        "Saved contradiction notes: " + " | ".join(challenges),
    ]
    return "\n".join(lines)


def _theme_ids(question: str, records: Sequence[Dict[str, Any]]) -> List[str]:
    text = question.lower()
    selected = []

    def add(predicate) -> None:
        for record in records:
            if predicate(record) and record["record_id"] not in selected:
                selected.append(record["record_id"])

    if any(word in text for word in ("scroll", "manual", "brows")):
        add(lambda record: record.get("manual_scroll_signal") == "Yes" or "scroll" in _record_text(record).lower())
    if any(word in text for word in ("remember", "clue", "forgot", "forgotten")):
        add(lambda record: str(record.get("remembered_clues", "")).lower() not in {"", "unknown"})
    if any(word in text for word in ("recognition", "overload", "recogn")):
        add(lambda record: str(record.get("primary_failure_stage", "")).startswith("F5") or record.get("recognition_difficulty_signal") == "Yes" or record.get("candidate_overload_signal") == "Yes")
    if any(word in text for word in ("uncertain", "unknown", "insufficient", "review")):
        add(lambda record: record.get("needs_human_review") is True or record.get("relevance_label") == "Uncertain" or str(record.get("primary_failure_stage", "")).startswith("F8"))
    if any(word in text for word in ("strongest", "strong evidence", "high strength")):
        add(lambda record: record.get("evidence_strength") == "High")
    if any(word in text for word in ("search", "query", "keyword", "not return", "expected")):
        add(lambda record: record.get("retrieval_outcome") in {"Not Found", "Partially Found"} and "search" in _record_text(record).lower())
    return selected


def retrieve_records(question: str, records: Sequence[Dict[str, Any]], limit: int = 12) -> Dict[str, Any]:
    """Score saved records against the question. Does not call a model."""
    question_tokens = _tokens(question)
    scored = []
    for record in records:
        overlap = question_tokens & _tokens(_record_text(record))
        scored.append((len(overlap), record["record_id"], sorted(overlap)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    keyword_ids = [record_id for score, record_id, _ in scored if score > 0]
    theme_ids = _theme_ids(question, records)
    ordered = []
    for record_id in theme_ids + keyword_ids:
        if record_id not in ordered:
            ordered.append(record_id)
    selected_ids = ordered[:limit]
    lookup = {record["record_id"]: record for record in records}
    return {
        "selected_records": [lookup[record_id] for record_id in selected_ids if record_id in lookup],
        "match_notes": [
            {"record_id": record_id, "overlap_count": score, "matched_terms": terms}
            for score, record_id, terms in scored
            if record_id in selected_ids
        ],
        "method": "Keyword overlap on the original post and audited fields, plus a small set of explicit theme rules. No vector database is used.",
    }


def _context_block(record: Dict[str, Any]) -> str:
    review = "Needs human review" if record.get("needs_human_review") else "Not flagged"
    if not record.get("classified"):
        audit = "Not automatically classified. Relevance is Uncertain."
    else:
        audit = (
            f"Stage: {record.get('primary_failure_stage')}. "
            f"Outcome: {record.get('retrieval_outcome')}. "
            f"Evidence strength: {record.get('evidence_strength')}. "
            f"Remembered clues: {record.get('remembered_clues')}. "
            f"Forgotten clues: {record.get('missing_or_forgotten_clues')}. "
            f"Search or browse: {record.get('search_or_browse_behavior')}. "
            f"Reformulation: {record.get('reformulation_behavior')}. "
            f"Manual browsing: {record.get('manual_browsing_behavior')}. "
            f"Manual scroll signal: {record.get('manual_scroll_signal')}. "
            f"Recognition signal: {record.get('recognition_difficulty_signal')}. "
            f"Candidate overload signal: {record.get('candidate_overload_signal')}. "
            f"Workaround: {record.get('workaround')}. "
            f"Review: {review}."
        )
    return (
        f"RECORD {record['record_id']}\n"
        f"Source: {record.get('source')} | Date: {record.get('date')} | URL: {record.get('source_url')}\n"
        f"ORIGINAL POST:\n{record.get('original_text')}\n"
        f"AUDITED FIELDS (interpretation, not the post):\n{audit}\n"
    )


def _evidence_cards(records: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    cards = []
    for record in records:
        cards.append({
            "record_id": record["record_id"],
            "source": record.get("source", ""),
            "date": record.get("date", ""),
            "source_url": record.get("source_url", ""),
            "excerpt": _excerpt(record.get("original_text", "")),
            "evidence_strength": record.get("evidence_strength", "") if record.get("classified") else "Not classified",
            "primary_failure_stage": record.get("primary_failure_stage", "") if record.get("classified") else "Not classified",
        })
    return cards


def _strength_note(records: Sequence[Dict[str, Any]]) -> str:
    if not records:
        return "No classified evidence strength applies, because no saved record answered the question."
    counts: Dict[str, int] = {}
    review = 0
    for record in records:
        if not record.get("classified"):
            continue
        label = str(record.get("evidence_strength") or "Unknown")
        counts[label] = counts.get(label, 0) + 1
        if record.get("needs_human_review"):
            review += 1
    mix = "; ".join(f"{key}: {value}" for key, value in counts.items()) or "No classified strength"
    return f"Evidence strength among the cited classified records — {mix}. Records still needing human review: {review}."


def _empty_answer(question: str, reason: str, called_model: bool = False) -> Dict[str, Any]:
    return {
        "status": "insufficient",
        "called_model": called_model,
        "model": LLM_MODEL if called_model else "",
        "question": question,
        "short_answer": "The current corpus does not provide enough evidence to answer this question.",
        "evidence_summary": reason,
        "supporting_record_ids": [],
        "limiting_record_ids": [],
        "supporting_excerpts": [],
        "limiting_excerpts": [],
        "evidence_is_mixed": False,
        "evidence_is_insufficient": True,
        "evidence_strength_note": "No saved record supplied enough evidence for this question.",
        "corpus_limitation": CORPUS_LIMITATION,
        "retrieval_method": "Keyword and theme matching found no usable saved records.",
        "retrieved_record_ids": [],
        "error": "",
    }


def _guard_leading_answer(question: str, short_answer: str, analysis: Dict[str, Any]) -> str:
    if not _is_leading(question) or not _affirms_hypothesis(short_answer):
        return short_answer
    stage_counts = {
        stage["failure_stage"]: stage["record_count"]
        for stage in analysis.get("failure_stages", [])
    }
    recognition = stage_counts.get("F5 — Recognition Gap", 0)
    unknown = stage_counts.get("F8 — Unknown / Insufficient Evidence", 0)
    classified = analysis.get("input", {}).get("classified_record_count", 0)
    return (
        "No. The current evidence does not establish that conclusion. "
        f"The audited classifications keep recognition gap on {recognition} of {classified} records. "
        f"{unknown} of {classified} records are Unknown / Insufficient Evidence. "
        "A repeated observation in this interim corpus is not proof of a main cause, "
        "and it is not prevalence among Google Photos users."
    )


def ask_evidence(
    question: str,
    records: Optional[Sequence[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Answer one question from the saved corpus.
    Groq is called only from this function, and only when retrieval finds evidence.
    """
    question = " ".join(str(question).split())
    if not question:
        return _empty_answer("", "Type a research question before asking.")

    if records is None:
        records = load_discovery_records()
    if analysis is None:
        analysis = load_research_analysis()

    retrieval = retrieve_records(question, records)
    selected = retrieval["selected_records"]
    lookup = {record["record_id"]: record for record in records}
    if not selected:
        result = _empty_answer(
            question,
            "None of the saved posts or audited fields matched this question closely enough to ground an answer.",
        )
        result["retrieval_method"] = retrieval["method"]
        return result

    if not is_groq_configured():
        result = _empty_answer(question, "GROQ_API_KEY is not configured. No answer was invented.")
        result["status"] = "unavailable"
        result["retrieved_record_ids"] = [record["record_id"] for record in selected]
        result["error"] = "The Groq key is missing, so Ask the Evidence did not call the model."
        return result

    context = "\n".join(_context_block(record) for record in selected)
    user_prompt = (
        f"QUESTION:\n{question}\n\n"
        f"{_corpus_summary(analysis)}\n\n"
        "SUPPLIED RECORDS:\n"
        f"{context}\n"
        "Answer only from the records and summary above."
    )
    try:
        raw = _call_model([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        parsed = _parse_json_object(raw)
    except (ClassificationError, ValueError) as exc:
        return {
            "status": "error",
            "called_model": True,
            "model": LLM_MODEL,
            "question": question,
            "short_answer": "",
            "evidence_summary": "Ask the Evidence could not produce a grounded answer.",
            "supporting_record_ids": [],
            "limiting_record_ids": [],
            "supporting_excerpts": [],
            "limiting_excerpts": [],
            "evidence_is_mixed": False,
            "evidence_is_insufficient": True,
            "evidence_strength_note": "",
            "corpus_limitation": CORPUS_LIMITATION,
            "retrieval_method": retrieval["method"],
            "retrieved_record_ids": [record["record_id"] for record in selected],
            "error": _redact_secrets(str(exc)),
        }

    allowed = {record["record_id"] for record in selected}

    def keep_ids(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        kept = []
        for item in value:
            record_id = str(item).strip().strip("[]")
            if record_id in allowed and record_id not in kept:
                kept.append(record_id)
        return kept

    supporting_ids = keep_ids(parsed.get("supporting_record_ids"))
    limiting_ids = [record_id for record_id in keep_ids(parsed.get("limiting_record_ids")) if record_id not in supporting_ids]
    short_answer = str(parsed.get("short_answer") or "").strip()
    summary = str(parsed.get("evidence_summary") or "").strip()
    model_says_insufficient = bool(parsed.get("evidence_is_insufficient"))
    if not short_answer or (model_says_insufficient and not supporting_ids):
        short_answer = "The current corpus does not provide enough evidence to answer this question."
    insufficient = not supporting_ids
    short_answer = _guard_leading_answer(question, short_answer, analysis)
    mixed = bool(parsed.get("evidence_is_mixed")) or bool(supporting_ids and limiting_ids)
    if _is_leading(question):
        mixed = True
    supporting_records = [lookup[record_id] for record_id in supporting_ids]
    limiting_records = [lookup[record_id] for record_id in limiting_ids]
    strength_note = str(parsed.get("evidence_strength_note") or "").strip() or _strength_note(supporting_records)
    return {
        "status": "answered" if not insufficient else "insufficient",
        "called_model": True,
        "model": LLM_MODEL,
        "question": question,
        "short_answer": short_answer,
        "evidence_summary": summary or "The model did not add a separate evidence summary.",
        "supporting_record_ids": supporting_ids,
        "limiting_record_ids": limiting_ids,
        "supporting_excerpts": _evidence_cards(supporting_records),
        "limiting_excerpts": _evidence_cards(limiting_records),
        "evidence_is_mixed": mixed,
        "evidence_is_insufficient": insufficient and not supporting_ids,
        "evidence_strength_note": strength_note,
        "corpus_limitation": CORPUS_LIMITATION,
        "retrieval_method": retrieval["method"],
        "retrieved_record_ids": [record["record_id"] for record in selected],
        "error": "",
    }
