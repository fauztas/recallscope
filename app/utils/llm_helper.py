"""
RecallScope — Groq classification helper
Phase 3: AI Research Classification

Sends one evidence record at a time to Groq and validates the JSON response.
The model is instructed to use only the supplied evidence. Unknown is a
legitimate value. This module never prints the API key.
"""

import ast
import json
import re
import time
from typing import Any, Dict, List, Tuple

from app.utils.config import get_groq_api_key, is_groq_configured

LLM_PROVIDER = "Groq"
LLM_MODEL = "openai/gpt-oss-120b"
MAX_ATTEMPTS = 3

FAILURE_STAGES = [
    "F1 — Recall Gap",
    "F2 — Expression Gap",
    "F3 — Interpretation Gap",
    "F4 — Candidate Gap",
    "F5 — Recognition Gap",
    "F6 — Refinement Gap",
    "F7 — Coverage / Indexing Gap",
    "F8 — Unknown / Insufficient Evidence",
]
STAGE_BY_CODE = {stage.split(" ")[0]: stage for stage in FAILURE_STAGES}

OUTCOMES = ["Found", "Not Found", "Partially Found", "Gave Up", "Unknown"]
SIGNALS = ["Yes", "No", "Unknown"]
STRENGTHS = ["High", "Medium", "Low"]
CONFIDENCE_LEVELS = ["High", "Medium", "Low"]

TEXT_FIELDS = [
    "retrieval_intent",
    "retrieval_scenario",
    "photo_type",
    "remembered_clues",
    "missing_or_forgotten_clues",
    "search_or_browse_behavior",
    "reformulation_behavior",
    "manual_browsing_behavior",
    "workaround",
    "failure_reason",
    "evidence_strength_reason",
    "ai_interpretation",
]

AI_FIELDS = TEXT_FIELDS + [
    "retrieval_outcome",
    "primary_failure_stage",
    "secondary_failure_stage",
    "candidate_overload_signal",
    "recognition_difficulty_signal",
    "query_difficulty_signal",
    "manual_scroll_signal",
    "evidence_strength",
    "confidence",
    "needs_human_review",
    "human_review_reason",
]

UNKNOWN_TEXT_MARKERS = {
    "unknown",
    "n/a",
    "na",
    "none",
    "none mentioned",
    "not stated",
    "not mentioned",
    "not specified",
    "unspecified",
    "insufficient evidence",
    "not recorded",
}

SYSTEM_PROMPT = """You are a careful qualitative research classifier for RecallScope.

RecallScope studies this question only:
"Where and why do users struggle when trying to retrieve a photo they remember exists, especially when they cannot precisely describe or locate it?"

Use only the supplied evidence. If a field is not supported by the evidence, return Unknown. Do not fill gaps using assumptions or general knowledge.

Rules:
- Do not invent user intent, forgotten information, emotions, demographics, causes, outcomes, or workarounds.
- Do not assume a Google Photos feature exists.
- Do not convert ambiguity into certainty.
- Do not claim how common a problem is.
- Do not recommend a product or solution.
- Source and date are collection metadata. Do not treat them as clues the person remembered unless the evidence text itself states them.
- Unknown is a correct and preferred answer whenever the evidence is insufficient.
- Do not force a photo type. Use Unknown when the evidence does not support one.
- Remembered clues must be explicitly supported by the evidence.
- Missing or forgotten clues must be explicitly supported. Otherwise return Unknown.
- Reformulation, manual browsing, and workaround must be Unknown unless the evidence describes them.
- Retrieval outcome must be one of: Found, Not Found, Partially Found, Gave Up, Unknown.
- Do not mark Gave Up unless the person explicitly says they gave up or stopped.
- Do not force exactly one failure stage when the evidence supports two. Put the main stage in primary_failure_stage and the other in secondary_failure_stage.
- If only one stage is supported, secondary_failure_stage must be None.
- If no stage is defensibly supported, primary_failure_stage must be "F8 — Unknown / Insufficient Evidence" and secondary_failure_stage must be Unknown.
- Failure-stage definitions:
  F1 — Recall Gap: the person cannot remember enough useful information.
  F2 — Expression Gap: the person remembers potentially useful information but struggles to translate it into a searchable query.
  F3 — Interpretation Gap: the person expresses useful clues, but search appears to interpret them poorly.
  F4 — Candidate Gap: the desired photo is not adequately surfaced among results.
  F5 — Recognition Gap: candidates are available or plausible, but identifying the intended photo is difficult because of volume, similarity, or visual scanning burden.
  F6 — Refinement Gap: after an unsuccessful attempt, the person struggles to improve or refine the search.
  F7 — Coverage / Indexing Gap: the evidence suggests missing indexing, metadata, coverage, sync, or search availability.
  F8 — Unknown / Insufficient Evidence: the evidence does not support a defensible failure-stage classification.
- Distinguish F2 from F3: F2 is difficulty choosing words; F3 is a stated query that search appears to mishandle.
- Distinguish F4 from F5: F4 means the wanted photo is not surfaced; F5 means results are present but hard to recognize or scan.
- candidate_overload_signal, recognition_difficulty_signal, query_difficulty_signal, and manual_scroll_signal must be Yes, No, or Unknown.
- Use Yes only when the evidence explicitly supports that signal.
- evidence_strength and confidence must be High, Medium, or Low.
- needs_human_review must be true when the evidence is very short, contradictory, or too ambiguous for a confident classification.
- If needs_human_review is false, human_review_reason must be None.
- ai_interpretation is your concise reading of the evidence. It must not add facts that are absent from the evidence.
- Return one JSON object and nothing else.
"""


def _redact_secrets(text: str) -> str:
    """Remove anything that looks like an API key from an error string."""
    cleaned = re.sub(r"gsk_[A-Za-z0-9_\-]+", "[REDACTED]", text or "")
    cleaned = re.sub(
        r"(?i)(api[_-]?key['\"\s:=]+)[^\s'\"]+",
        r"\1[REDACTED]",
        cleaned,
    )
    return cleaned[:400]


class ClassificationError(RuntimeError):
    """Raised when classification cannot continue safely."""


def require_groq_key() -> str:
    """Return the configured key, or stop before any classification call."""
    if not is_groq_configured():
        raise ClassificationError(
            "GROQ_API_KEY is not configured. Classification was not run and no values were invented."
        )
    return get_groq_api_key()


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_text_field(value: Any) -> str:
    if isinstance(value, list):
        value = "; ".join(_normalize_token(item) for item in value if _normalize_token(item))
    text = _normalize_token(value)
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            text = "; ".join(_normalize_token(item) for item in parsed if _normalize_token(item))
    if text.lower() in UNKNOWN_TEXT_MARKERS:
        return "Unknown"
    return text


def _normalize_choice(value: Any, allowed: List[str]) -> str:
    text = _normalize_token(value)
    lookup = {item.lower(): item for item in allowed}
    return lookup.get(text.lower(), "")


def _normalize_stage(value: Any, allow_none: bool) -> str:
    if value is None:
        return "None" if allow_none else ""
    text = _normalize_token(value)
    lowered = text.lower()
    if allow_none and lowered in {"none", "null", "n/a", "na", "no secondary", "no secondary stage"}:
        return "None"
    if lowered in {"unknown", "insufficient evidence", "not stated"}:
        return "Unknown" if allow_none else ""
    code_match = re.search(r"\bF([1-8])\b", text, flags=re.IGNORECASE)
    if code_match:
        return STAGE_BY_CODE[f"F{code_match.group(1)}"]
    return ""


def _normalize_review_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _normalize_token(value).lower() in {"true", "yes", "1"}


def validate_classification(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Normalize one model payload.
    Returns the cleaned field dict and a list of validation errors.
    Unknown is accepted. Missing or unsupported values are errors, not guesses.
    """
    errors: List[str] = []
    if not isinstance(payload, dict):
        return {}, ["Response was not a JSON object."]

    cleaned: Dict[str, Any] = {}
    for field in TEXT_FIELDS:
        if field not in payload:
            errors.append(f"Missing field: {field}")
            continue
        value = _normalize_text_field(payload.get(field))
        if not value:
            errors.append(f"Empty field: {field}")
            continue
        cleaned[field] = value

    outcome = _normalize_choice(payload.get("retrieval_outcome"), OUTCOMES) if "retrieval_outcome" in payload else ""
    if not outcome:
        errors.append("retrieval_outcome must be Found, Not Found, Partially Found, Gave Up, or Unknown.")
    else:
        cleaned["retrieval_outcome"] = outcome

    primary = _normalize_stage(payload.get("primary_failure_stage"), allow_none=False) if "primary_failure_stage" in payload else ""
    if primary not in FAILURE_STAGES:
        errors.append("primary_failure_stage must be one of F1 through F8.")
    else:
        cleaned["primary_failure_stage"] = primary

    if "secondary_failure_stage" not in payload:
        errors.append("Missing field: secondary_failure_stage")
    else:
        secondary = _normalize_stage(payload.get("secondary_failure_stage"), allow_none=True)
        if secondary == "":
            errors.append("secondary_failure_stage must be a failure stage, None, or Unknown.")
        elif primary and secondary == primary:
            cleaned["secondary_failure_stage"] = "None"
        else:
            cleaned["secondary_failure_stage"] = secondary

    for field in (
        "candidate_overload_signal",
        "recognition_difficulty_signal",
        "query_difficulty_signal",
        "manual_scroll_signal",
    ):
        if field not in payload:
            errors.append(f"Missing field: {field}")
            continue
        signal = _normalize_choice(payload.get(field), SIGNALS)
        if not signal:
            errors.append(f"{field} must be Yes, No, or Unknown.")
        else:
            cleaned[field] = signal

    strength = _normalize_choice(payload.get("evidence_strength"), STRENGTHS) if "evidence_strength" in payload else ""
    if not strength:
        errors.append("evidence_strength must be High, Medium, or Low.")
    else:
        cleaned["evidence_strength"] = strength

    confidence = _normalize_choice(payload.get("confidence"), CONFIDENCE_LEVELS) if "confidence" in payload else ""
    if not confidence:
        errors.append("confidence must be High, Medium, or Low.")
    else:
        cleaned["confidence"] = confidence

    if "needs_human_review" not in payload:
        errors.append("Missing field: needs_human_review")
    else:
        cleaned["needs_human_review"] = _normalize_review_flag(payload.get("needs_human_review"))

    if "human_review_reason" not in payload:
        errors.append("Missing field: human_review_reason")
    else:
        reason = _normalize_token(payload.get("human_review_reason"))
        if reason.lower() in {"", "none", "null", "unknown", "n/a", "na"}:
            reason = ""
        cleaned["human_review_reason"] = reason

    if errors:
        return cleaned, errors

    if cleaned["needs_human_review"] and not cleaned["human_review_reason"]:
        cleaned["human_review_reason"] = "Model requested human review without a specific reason."
    elif not cleaned["needs_human_review"] and cleaned["human_review_reason"]:
        cleaned["needs_human_review"] = True
    elif not cleaned["needs_human_review"]:
        cleaned["human_review_reason"] = ""

    if cleaned["primary_failure_stage"] != "F8 — Unknown / Insufficient Evidence" and cleaned["failure_reason"] == "Unknown":
        cleaned["needs_human_review"] = True
        note = "A specific failure stage was assigned without a failure reason."
        if note not in cleaned["human_review_reason"]:
            cleaned["human_review_reason"] = (cleaned["human_review_reason"] + " " + note).strip()

    return cleaned, []


def _fallback_classification(reason: str) -> Dict[str, Any]:
    """Used only after retries fail. Does not invent a research interpretation."""
    fallback = {field: "Unknown" for field in TEXT_FIELDS}
    fallback.update({
        "retrieval_outcome": "Unknown",
        "primary_failure_stage": "Unknown",
        "secondary_failure_stage": "Unknown",
        "candidate_overload_signal": "Unknown",
        "recognition_difficulty_signal": "Unknown",
        "query_difficulty_signal": "Unknown",
        "manual_scroll_signal": "Unknown",
        "evidence_strength": "Low",
        "confidence": "Low",
        "needs_human_review": True,
        "human_review_reason": reason or "Model response stayed invalid after retries. Missing values were not invented.",
        "classification_status": "invalid_response",
        "classification_error": reason,
    })
    return fallback


def _record_prompt(record_id: str, source: str, date: str, original_text: str) -> str:
    return (
        f"Record ID: {record_id}\n"
        f"Source: {source}\n"
        f"Date: {date}\n\n"
        "Evidence:\n"
        f'"""\n{original_text}\n"""\n\n'
        "Use only the supplied evidence. If a field is not supported by the evidence, return Unknown. "
        "Do not fill gaps using assumptions or general knowledge.\n"
        "Return one JSON object with exactly these keys:\n"
        + ", ".join(AI_FIELDS)
    )


def _parse_json_object(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    parsed = json.loads(text)
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        raise ValueError("Model response was not a JSON object.")
    return parsed


def _call_model(messages: List[Dict[str, str]]) -> str:
    """Call Groq. Network retries stay inside this function. The key is never logged."""
    from groq import Groq

    client = Groq(api_key=require_groq_key())
    last_error = "Groq request failed."
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=4000,
            )
            content = response.choices[0].message.content if response.choices else ""
            if not content or not str(content).strip():
                raise ValueError("Groq returned an empty response.")
            return str(content)
        except Exception as exc:
            last_error = _redact_secrets(f"{type(exc).__name__}: {exc}")
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
    raise ClassificationError(last_error)


def classify_evidence_record(record_id: str, source: str, date: str, original_text: str) -> Dict[str, Any]:
    """
    Classify one relevant evidence record.
    Retries malformed JSON a limited number of times. If it stays invalid, the
    record is flagged for human review and no research values are invented.
    """
    require_groq_key()
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _record_prompt(record_id, source, date, original_text)},
    ]
    last_error = "Model response was invalid."

    for attempt in range(MAX_ATTEMPTS):
        try:
            raw_text = _call_model(messages)
            parsed = _parse_json_object(raw_text)
            cleaned, errors = validate_classification(parsed)
            if not errors:
                cleaned["classification_status"] = "classified"
                cleaned["classification_error"] = ""
                return cleaned
            last_error = "; ".join(errors)
        except (json.JSONDecodeError, ValueError, ClassificationError) as exc:
            last_error = _redact_secrets(str(exc))

        if attempt < MAX_ATTEMPTS - 1:
            messages.append({
                "role": "user",
                "content": (
                    "The previous response was invalid: "
                    + last_error
                    + " Return only one corrected JSON object. Use only the supplied evidence. "
                    "If a field is not supported by the evidence, return Unknown. "
                    "Do not fill gaps using assumptions or general knowledge."
                ),
            })

    return _fallback_classification(
        "Model response stayed invalid after retries. Missing values were not invented. "
        + last_error
    )


_BEHAVIOR_FIELDS = (
    "search_or_browse_behavior",
    "reformulation_behavior",
    "manual_browsing_behavior",
    "workaround",
)
_FORGOTTEN_STOPWORDS = {
    "other", "details", "detail", "such", "that", "were", "with", "this", "only",
    "thing", "things", "about", "from", "have", "been", "not", "are", "the",
    "and", "for", "when", "what", "they", "them", "their", "into", "more",
    "than", "also", "some", "any", "all", "was", "user", "person", "photo",
    "photos", "picture", "pictures",
}


def _content_words(text: str) -> List[str]:
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    return [word for word in words if word not in _FORGOTTEN_STOPWORDS and not word.startswith("remember")]


def repair_classification_integrity(original_text: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Correct storage and grounding problems without creating new research claims.
    Blank secondary stages are restored to None. Unsupported forgotten clues
    become Unknown and the record is flagged for review.
    """
    review_notes: List[str] = []
    for field in TEXT_FIELDS:
        if field in result:
            result[field] = _normalize_text_field(result.get(field))

    secondary = _normalize_token(result.get("secondary_failure_stage"))
    if secondary == "":
        result["secondary_failure_stage"] = "None"

    for field in _BEHAVIOR_FIELDS:
        if _normalize_token(result.get(field)).lower() in {"yes", "no"}:
            result[field] = "Unknown"
            review_notes.append(f"{field} was Yes/No rather than a described behavior, so it was set to Unknown.")

    forgotten = _normalize_text_field(result.get("missing_or_forgotten_clues"))
    content_words = _content_words(forgotten)
    if forgotten != "Unknown" and content_words:
        original_lower = original_text.lower()
        if not any(word in original_lower for word in content_words):
            result["missing_or_forgotten_clues"] = "Unknown"
            review_notes.append("Forgotten clues included details that are not in the evidence, so the field was set to Unknown.")

    if review_notes:
        result["needs_human_review"] = True
        existing = _normalize_token(result.get("human_review_reason"))
        addition = " ".join(review_notes)
        if existing.lower() in {"", "none", "unknown", "null"}:
            result["human_review_reason"] = addition
        elif addition not in existing:
            result["human_review_reason"] = f"{existing} {addition}"
    return result


def apply_phase2_review_flag(result: Dict[str, Any], review_required: bool) -> Dict[str, Any]:
    """Keep a Phase 2 manual-review flag even if the model does not request review."""
    if not review_required:
        return result
    result["needs_human_review"] = True
    note = "Phase 2 already flagged this Relevant record for manual review."
    existing = _normalize_token(result.get("human_review_reason"))
    if existing.lower() in {"", "none", "unknown", "null"}:
        result["human_review_reason"] = note
    elif note not in existing:
        result["human_review_reason"] = f"{existing} {note}"
    return result


def unknown_value_self_check() -> bool:
    """Confirm the validator accepts Unknown instead of rejecting it."""
    payload = {field: "Unknown" for field in TEXT_FIELDS}
    payload.update({
        "retrieval_outcome": "Unknown",
        "primary_failure_stage": "F8 — Unknown / Insufficient Evidence",
        "secondary_failure_stage": "Unknown",
        "candidate_overload_signal": "Unknown",
        "recognition_difficulty_signal": "Unknown",
        "query_difficulty_signal": "Unknown",
        "manual_scroll_signal": "Unknown",
        "evidence_strength": "Low",
        "confidence": "Low",
        "needs_human_review": True,
        "human_review_reason": "Insufficient evidence.",
    })
    cleaned, errors = validate_classification(payload)
    return not errors and cleaned.get("retrieval_intent") == "Unknown" and cleaned.get("retrieval_outcome") == "Unknown"
