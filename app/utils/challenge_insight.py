"""
RecallScope — Phase 7 Challenge an Insight

Retrieves saved records on both sides of a proposed insight, then asks Groq
to assess only that evidence. Importing this module does not call Groq.
Verbatim excerpts are copied from the saved original posts.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app.utils.discovery_data import load_discovery_records, load_research_analysis
from app.utils.llm_helper import (
    LLM_MODEL,
    ClassificationError,
    _call_model,
    _parse_json_object,
    _redact_secrets,
    is_groq_configured,
)

ASSESSMENTS = (
    "Supported by current evidence",
    "Partially supported / mixed evidence",
    "Weakly supported",
    "Not supported by current evidence",
    "Insufficient evidence",
)

EXAMPLE_INSIGHTS = [
    "Recognition difficulty is the main reason people fail to retrieve remembered photos.",
    "Manual scrolling is a common workaround after search does not help.",
    "Users mainly fail because they cannot remember the date.",
    "Search frequently returns no useful candidates.",
    "Coverage or indexing problems explain most retrieval failures.",
]

CORPUS_LIMITATION = (
    "This interim public-evidence corpus cannot establish population prevalence "
    "among Google Photos users. A count in this corpus is not a population rate."
)

SYSTEM_PROMPT = """You are the RecallScope research tool for Challenge an Insight.

Your job is to test a proposed insight against the supplied saved records.
You are not here to confirm the insight. Search the supplied records for support and for evidence that weakens, contradicts, or limits it.

Rules:
- Use only the supplied records and the supplied corpus summary.
- Do not use general knowledge about Google Photos.
- Do not invent records, quotes, counts, or causes.
- Do not write quotations. Refer to record IDs only. The application attaches the original text.
- The audited fields are interpretations. The original post is the evidence.
- Unknown must stay Unknown. Do not treat Unknown as No.
- Absence of a detail in a post is not evidence that the detail was absent for the person.
- A single record, or a handful of records, cannot establish a main cause or what most people do.
- If challenging records exist, do not assess the insight as "Supported by current evidence".
- If the insight says something is the main reason, the majority cause, or the explanation of most failures, do not assess it as "Supported by current evidence" unless the supplied stage counts show that.
- Do not claim population prevalence.
- Do not select a final problem statement.
- Do not recommend a product, feature, or solution.
- next_research_questions must be questions for interviews or further evidence collection. They must not be product recommendations.
- Use only record IDs from the supplied records.
- Phase 2 Uncertain records are not in the supplied records. Do not cite them as support or contradiction.

assessment must be exactly one of:
- Supported by current evidence
- Partially supported / mixed evidence
- Weakly supported
- Not supported by current evidence
- Insufficient evidence

Return one JSON object with these keys:
assessment, assessment_reason,
supporting, challenging, evidence_gaps, next_research_questions

supporting and challenging are arrays of objects with record_id and reason.
next_research_questions is an array of 2 to 4 strings.
"""


def _tokens(text: str) -> set:
    words = set(re.findall(r"[a-z0-9']+", str(text).lower()))
    kept = set()
    stop = {
        "a", "an", "the", "of", "to", "and", "or", "in", "on", "for", "is", "are",
        "people", "users", "user", "photo", "photos", "google", "because", "when",
        "after", "they", "their", "this", "that", "with", "from", "into", "not",
    }
    for word in words:
        if word in stop or len(word) < 3:
            continue
        kept.add(word)
        if word.endswith("ing") and len(word) > 5:
            kept.add(word[:-3])
    return kept


def _blob(record: Dict[str, Any]) -> str:
    parts = [
        record.get("original_text", ""),
        record.get("primary_failure_stage", ""),
        record.get("retrieval_outcome", ""),
        record.get("remembered_clues", ""),
        record.get("missing_or_forgotten_clues", ""),
        record.get("search_or_browse_behavior", ""),
        record.get("manual_browsing_behavior", ""),
        record.get("workaround", ""),
        record.get("failure_reason", ""),
        record.get("manual_scroll_signal", ""),
        record.get("recognition_difficulty_signal", ""),
        record.get("candidate_overload_signal", ""),
        record.get("evidence_strength", ""),
    ]
    return " ".join(str(part) for part in parts).lower()


def _excerpt(text: str, limit: int = 280) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rsplit(" ", 1)[0] + "…"


def _eligible(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        record for record in records
        if record.get("classified") and record.get("relevance_label") == "Relevant"
    ]


def _uncertain_ids(records: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        record["record_id"] for record in records
        if record.get("relevance_label") == "Uncertain"
    ]


def _predicates(insight: str) -> Tuple[Callable[[Dict[str, Any]], bool], Callable[[Dict[str, Any]], bool]]:
    text = insight.lower()

    def other_than(match: Callable[[Dict[str, Any]], bool]) -> Callable[[Dict[str, Any]], bool]:
        return lambda record: not match(record)

    if any(word in text for word in ("recognition", "recognize", "recognise")):
        def supports(record: Dict[str, Any]) -> bool:
            return (
                str(record.get("primary_failure_stage", "")).startswith("F5")
                or record.get("recognition_difficulty_signal") == "Yes"
            )
        return supports, other_than(supports)

    if any(word in text for word in ("scroll", "scrolling", "manual")):
        def supports(record: Dict[str, Any]) -> bool:
            blob = _blob(record)
            return record.get("manual_scroll_signal") == "Yes" or "scroll" in blob or "digging" in blob
        def challenges(record: Dict[str, Any]) -> bool:
            blob = _blob(record)
            search_miss = record.get("retrieval_outcome") in {"Not Found", "Partially Found"} and "search" in blob
            no_scroll = record.get("manual_scroll_signal") != "Yes" and "scroll" not in blob and "digging" not in blob
            found_then_scroll = "once i find" in blob
            cannot_use_scroll = "can't just scroll" in blob or "cannot scroll" in blob or "instead of scrolling" in blob
            return (search_miss and no_scroll) or found_then_scroll or cannot_use_scroll
        return supports, challenges

    if "date" in text:
        def supports(record: Dict[str, Any]) -> bool:
            forgotten = str(record.get("missing_or_forgotten_clues", "")).lower()
            return str(record.get("primary_failure_stage", "")).startswith("F1") or "date" in forgotten
        return supports, other_than(supports)

    if any(word in text for word in ("index", "coverage")):
        def supports(record: Dict[str, Any]) -> bool:
            return str(record.get("primary_failure_stage", "")).startswith("F7")
        return supports, other_than(supports)

    if any(word in text for word in ("search", "candidates", "candidate")):
        def supports(record: Dict[str, Any]) -> bool:
            return record.get("retrieval_outcome") in {"Not Found", "Partially Found"} and "search" in _blob(record)
        def challenges(record: Dict[str, Any]) -> bool:
            return record.get("retrieval_outcome") == "Found" or str(record.get("primary_failure_stage", "")).startswith("F5")
        return supports, challenges

    return lambda record: False, lambda record: False


def _rank(records: Sequence[Dict[str, Any]], insight: str) -> List[Dict[str, Any]]:
    tokens = _tokens(insight)
    strength_rank = {"High": 0, "Medium": 1, "Low": 2}

    def key(record: Dict[str, Any]) -> Tuple[int, int, str]:
        overlap = len(tokens & _tokens(_blob(record)))
        return (strength_rank.get(str(record.get("evidence_strength")), 3), -overlap, record["record_id"])

    return sorted(records, key=key)


def retrieve_for_challenge(insight: str, records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Select saved Relevant classifications. Uncertain records are not selected."""
    eligible = _eligible(records)
    supports, challenges = _predicates(insight)
    challenge_pool = _rank([record for record in eligible if challenges(record)], insight)
    challenge_ids = {record["record_id"] for record in challenge_pool}
    support_pool = _rank(
        [record for record in eligible if supports(record) and record["record_id"] not in challenge_ids],
        insight,
    )
    selected: List[Dict[str, Any]] = []
    seen = set()
    for record in support_pool[:5] + challenge_pool[:7]:
        if record["record_id"] not in seen:
            selected.append(record)
            seen.add(record["record_id"])
    if not selected:
        tokens = _tokens(insight)
        keyword_hits = [
            record for record in eligible
            if tokens & _tokens(_blob(record))
        ]
        selected = _rank(keyword_hits, insight)[:8]
    return {
        "selected_records": selected,
        "support_pool_ids": [record["record_id"] for record in support_pool],
        "challenge_pool_ids": [record["record_id"] for record in challenge_pool],
        "uncertain_record_ids": _uncertain_ids(records),
        "method": (
            "Classified Relevant records are scored from the original post and audited fields. "
            "Records that match the insight and records that point elsewhere are both retrieved. "
            "Phase 2 Uncertain records are not sent for this assessment."
        ),
    }


def _claims_dominance(insight: str) -> bool:
    text = insight.lower()
    markers = (
        "main reason",
        "the main",
        "mostly",
        "most retrieval",
        "most failures",
        "explain most",
        "majority",
        "primarily",
    )
    return any(marker in text for marker in markers)


def _corpus_summary(analysis: Dict[str, Any]) -> str:
    stages = [
        f"{stage['failure_stage']}: {stage['record_count']}"
        for stage in analysis.get("failure_stages", [])
    ]
    summary = analysis.get("input", {})
    return (
        "Saved corpus summary. These counts are not user quotations and are not population prevalence.\n"
        f"Classified records: {summary.get('classified_record_count')}. "
        f"Human review: {summary.get('human_review_count')}. "
        f"Uncertain, excluded from this assessment: {', '.join(summary.get('uncertain_record_ids', []))}.\n"
        "Failure-stage counts: " + "; ".join(stages)
    )


def _context_block(record: Dict[str, Any]) -> str:
    review = "Needs human review" if record.get("needs_human_review") else "Not flagged for human review"
    return (
        f"RECORD {record['record_id']}\n"
        f"Source: {record.get('source')} | Date: {record.get('date')} | URL: {record.get('source_url')}\n"
        f"ORIGINAL POST:\n{record.get('original_text')}\n"
        f"AUDITED FIELDS: stage {record.get('primary_failure_stage')}; "
        f"outcome {record.get('retrieval_outcome')}; strength {record.get('evidence_strength')}; "
        f"remembered {record.get('remembered_clues')}; forgotten {record.get('missing_or_forgotten_clues')}; "
        f"search or browse {record.get('search_or_browse_behavior')}; "
        f"manual browsing {record.get('manual_browsing_behavior')}; "
        f"scroll signal {record.get('manual_scroll_signal')}; "
        f"recognition signal {record.get('recognition_difficulty_signal')}; "
        f"overload signal {record.get('candidate_overload_signal')}; "
        f"review {review}.\n"
    )


def _clean_reason(reason: str, record: Dict[str, Any], fallback: str) -> str:
    text = " ".join(str(reason).split())
    if not text:
        return fallback
    original = " ".join(str(record.get("original_text", "")).split()).lower()
    for quote in re.findall(r"[\"“](.{12,}?)[\"”]", text):
        if quote.lower() not in original:
            return fallback
    return text


def _card(record: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "source": record.get("source", ""),
        "date": record.get("date", ""),
        "source_url": record.get("source_url", ""),
        "excerpt": _excerpt(record.get("original_text", "")),
        "reason": reason,
        "evidence_strength": record.get("evidence_strength", ""),
        "primary_failure_stage": record.get("primary_failure_stage", ""),
        "needs_human_review": bool(record.get("needs_human_review")),
    }


def _parse_side(value: Any) -> List[Dict[str, str]]:
    items = []
    if not isinstance(value, list):
        return items
    for item in value:
        if isinstance(item, dict):
            record_id = str(item.get("record_id", "")).strip().strip("[]")
            reason = str(item.get("reason", "")).strip()
        else:
            record_id = str(item).strip().strip("[]")
            reason = ""
        if record_id:
            items.append({"record_id": record_id, "reason": reason})
    return items


def _fallback_questions(insight: str) -> List[str]:
    return [
        "When people describe a recent attempt to find a remembered photo, what did they try first, and what did they try next?",
        "Which details were already in mind before the search, and which details were only used after seeing results?",
        f"In interviews, what would confirm or weaken this proposed insight: {insight}",
    ]


def _research_questions(raw_questions: Any, insight: str) -> List[str]:
    product_markers = (
        "build ", "feature", "mvp", "product", "recommend", "ship ",
        "design intervention", "design element", "intervention", "solution",
        "what should we", "how should we", "how can we", "improve the app",
        "fix the", "alleviate", "ai suggestion", "could reduce", "could improve",
    )
    kept = []
    if isinstance(raw_questions, list):
        for item in raw_questions:
            text = " ".join(str(item).split())
            if not text or any(marker in text.lower() for marker in product_markers):
                continue
            if text not in kept:
                kept.append(text)
    for question in _fallback_questions(insight):
        if len(kept) >= 2:
            break
        kept.append(question)
    return kept[:4]


def _apply_assessment_guard(
    insight: str,
    assessment: str,
    reason: str,
    supporting_count: int,
    challenging_count: int,
) -> Tuple[str, str]:
    if assessment not in ASSESSMENTS:
        if supporting_count and challenging_count:
            assessment = "Partially supported / mixed evidence"
        elif supporting_count:
            assessment = "Weakly supported"
        else:
            assessment = "Insufficient evidence"
    if supporting_count == 0 and challenging_count == 0:
        return "Insufficient evidence", "No saved classified record was strong enough to support or challenge this insight."
    if _claims_dominance(insight):
        reason = (
            "The proposed insight claims a main or majority cause. "
            "The audited records in this interim corpus do not establish that conclusion. "
            + reason
        ).strip()
        return "Not supported by current evidence", reason
    if assessment == "Supported by current evidence" and challenging_count:
        assessment = "Partially supported / mixed evidence"
        reason = (
            reason + " Challenging records are also present, so the insight is not treated as fully supported."
        ).strip()
    return assessment, reason


def _plain_text(value: Any) -> str:
    if isinstance(value, list):
        parts = [" ".join(str(item).split()) for item in value if str(item).strip()]
        return " ".join(parts)
    return " ".join(str(value or "").split())


def _insufficient(insight: str, retrieval: Dict[str, Any], reason: str, called_model: bool = False, error: str = "") -> Dict[str, Any]:
    return {
        "status": "insufficient" if not error else "error",
        "called_model": called_model,
        "model": LLM_MODEL if called_model else "",
        "proposed_insight": insight,
        "assessment": "Insufficient evidence",
        "assessment_reason": reason,
        "supporting": [],
        "challenging": [],
        "evidence_gaps": reason + " " + CORPUS_LIMITATION,
        "next_research_questions": _fallback_questions(insight)[:3],
        "retrieved_record_ids": [record["record_id"] for record in retrieval.get("selected_records", [])],
        "uncertain_record_ids": retrieval.get("uncertain_record_ids", []),
        "retrieval_method": retrieval.get("method", ""),
        "corpus_limitation": CORPUS_LIMITATION,
        "error": error,
    }


def challenge_insight(
    insight: str,
    records: Optional[Sequence[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Test one proposed insight against the saved corpus.
    Groq is called only from this function, and only after records are retrieved.
    """
    insight = " ".join(str(insight).split())
    if records is None:
        records = load_discovery_records()
    if analysis is None:
        analysis = load_research_analysis()
    retrieval = retrieve_for_challenge(insight, records)
    selected = retrieval["selected_records"]
    lookup = {record["record_id"]: record for record in selected}
    if not insight:
        return _insufficient("", retrieval, "Enter an insight before challenging it.")
    if not selected:
        return _insufficient(
            insight,
            retrieval,
            "The current corpus does not provide enough evidence to judge this insight.",
        )
    if not is_groq_configured():
        result = _insufficient(
            insight,
            retrieval,
            "GROQ_API_KEY is not configured. No assessment was invented.",
        )
        result["error"] = "The Groq key is missing, so Challenge an Insight did not call the model."
        return result

    user_prompt = (
        f"PROPOSED INSIGHT:\n{insight}\n\n"
        f"{_corpus_summary(analysis)}\n\n"
        "SUPPLIED RECORDS:\n"
        + "\n".join(_context_block(record) for record in selected)
    )
    try:
        raw = _call_model([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        parsed = _parse_json_object(raw)
    except (ClassificationError, ValueError) as exc:
        result = _insufficient(
            insight,
            retrieval,
            "Challenge an Insight could not produce an assessment. No records were invented.",
            called_model=True,
            error=_redact_secrets(str(exc)),
        )
        return result

    allowed = set(lookup)
    support_pool = set(retrieval["support_pool_ids"])
    challenge_pool = set(retrieval["challenge_pool_ids"])

    def keep(items: List[Dict[str, str]], pool: set) -> List[str]:
        kept = []
        for item in items:
            record_id = item["record_id"]
            if record_id in allowed and record_id in pool and record_id not in kept:
                kept.append(record_id)
        return kept

    model_support = _parse_side(parsed.get("supporting"))
    model_challenge = _parse_side(parsed.get("challenging"))
    support_reasons = {item["record_id"]: item["reason"] for item in model_support}
    challenge_reasons = {item["record_id"]: item["reason"] for item in model_challenge}
    supporting_ids = keep(model_support, support_pool or allowed)
    challenging_ids = [
        record_id for record_id in keep(model_challenge, challenge_pool or allowed)
        if record_id not in supporting_ids
    ]
    if support_pool and not supporting_ids:
        supporting_ids = [record_id for record_id in retrieval["support_pool_ids"] if record_id in allowed][:4]
    if challenge_pool and not challenging_ids:
        challenging_ids = [record_id for record_id in retrieval["challenge_pool_ids"] if record_id in allowed][:6]

    supporting_cards = []
    for record_id in supporting_ids:
        record = lookup[record_id]
        fallback = (
            f"Audited stage: {record.get('primary_failure_stage')}. "
            f"Evidence strength: {record.get('evidence_strength')}. "
            "This is one saved record, not proof of a general cause."
        )
        supporting_cards.append(_card(record, _clean_reason(support_reasons.get(record_id, ""), record, fallback)))
    challenging_cards = []
    for record_id in challenging_ids:
        record = lookup[record_id]
        fallback = (
            f"Audited stage: {record.get('primary_failure_stage')}. "
            f"Outcome: {record.get('retrieval_outcome')}. "
            "This record does not establish the proposed insight."
        )
        challenging_cards.append(_card(record, _clean_reason(challenge_reasons.get(record_id, ""), record, fallback)))

    assessment, reason = _apply_assessment_guard(
        insight,
        _plain_text(parsed.get("assessment")),
        _plain_text(parsed.get("assessment_reason")),
        len(supporting_cards),
        len(challenging_cards),
    )
    gaps = _plain_text(parsed.get("evidence_gaps"))
    uncertain = ", ".join(retrieval["uncertain_record_ids"]) or "none"
    gaps = (
        f"{gaps} The current corpus cannot establish population prevalence. "
        f"Unknown was not treated as No. "
        f"Phase 2 Uncertain records were not used as support or contradiction: {uncertain}."
    ).strip()
    return {
        "status": "assessed",
        "called_model": True,
        "model": LLM_MODEL,
        "proposed_insight": insight,
        "assessment": assessment,
        "assessment_reason": reason,
        "supporting": supporting_cards,
        "challenging": challenging_cards,
        "evidence_gaps": gaps,
        "next_research_questions": _research_questions(parsed.get("next_research_questions"), insight),
        "retrieved_record_ids": [record["record_id"] for record in selected],
        "uncertain_record_ids": retrieval["uncertain_record_ids"],
        "retrieval_method": retrieval["method"],
        "corpus_limitation": CORPUS_LIMITATION,
        "error": "",
    }
