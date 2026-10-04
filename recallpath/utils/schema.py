"""Structured memory and photo-reading records."""

import json
import re

from recallpath.utils.text import content_tokens, is_hedged, split_sentences

FACETS = ("people", "setting", "objects", "appearance", "event", "time", "other")
CONFIDENCE = ("high", "medium", "low", "unknown")


def parse_json_object(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("The model returned an empty response.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        raise ValueError("The model response was not a JSON object.")
    return parsed


def _facet(value) -> str:
    text = str(value or "").strip().lower()
    return text if text in FACETS else "other"


def _confidence(value, default="unknown") -> str:
    text = str(value or "").strip().lower()
    return text if text in CONFIDENCE else default


def _clean_text(value, limit=180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _clue(item, source: str) -> dict:
    if isinstance(item, str):
        item = {"text": item, "quote": item}
    if not isinstance(item, dict):
        return {}
    text = _clean_text(item.get("text") or item.get("clue") or "")
    quote = _clean_text(item.get("quote") or "", limit=240)
    if not text:
        return {}
    clue = {
        "source": source,
        "facet": _facet(item.get("facet")),
        "text": text,
        "quote": quote,
    }
    if source == "ai_inferred":
        clue["basis"] = _clean_text(item.get("basis") or "", limit=240)
        clue["confidence"] = _confidence(item.get("confidence"), default="low")
    elif source == "recognition":
        clue["confidence"] = _confidence(item.get("confidence"), default="medium")
    return clue


def _grounded(clue_text: str, memory_text: str) -> bool:
    clue_tokens = content_tokens(clue_text)
    memory_tokens = content_tokens(memory_text)
    if not clue_tokens:
        return False
    return len(clue_tokens & memory_tokens) / len(clue_tokens) >= 0.5


_GENERIC_INFERENCE = {
    "location", "place", "city", "town", "country", "area", "somewhere", "visit", "trip",
}


def _repeats_hedge(clue: dict, hedged: list) -> bool:
    tokens = content_tokens(clue.get("text", "")) - _GENERIC_INFERENCE
    if not tokens:
        return False
    for item in hedged:
        hedged_tokens = content_tokens(item.get("text", "")) | content_tokens(item.get("quote", ""))
        if tokens <= hedged_tokens:
            return True
    return False


def _split_stated_clause(clue: dict) -> tuple:
    """Move hedged sentences out of a stated clue and keep the certain part."""
    stated = []
    hedged = []
    quote = clue.get("quote") or clue.get("text") or ""
    pieces = split_sentences(quote) or split_sentences(clue.get("text", ""))
    if len(pieces) <= 1:
        target = hedged if is_hedged(quote) or is_hedged(clue.get("text", "")) else stated
        target.append(clue)
        return stated, hedged
    for piece in pieces:
        copy = dict(clue)
        copy["text"] = _clean_text(piece)
        copy["quote"] = _clean_text(piece, limit=240)
        if is_hedged(piece):
            hedged.append(copy)
        else:
            stated.append(copy)
    return stated, hedged


def sanitize_memory(payload: dict, memory_text: str) -> dict:
    """Keep stated, hedged, and inferred clues apart. Drop clues the words do not support."""
    if not isinstance(payload, dict):
        raise ValueError("Memory reading was not a JSON object.")

    stated = []
    hedged = []
    for item in _as_list(payload.get("user_stated")):
        clue = _clue(item, "user_stated")
        if not clue or not _grounded(clue["text"], memory_text):
            continue
        certain, uncertain = _split_stated_clause(clue)
        for piece in certain:
            if _grounded(piece["text"], memory_text):
                stated.append(piece)
        for piece in uncertain:
            piece["source"] = "hedged"
            if _grounded(piece["text"], memory_text):
                hedged.append(piece)

    for item in _as_list(payload.get("hedged")):
        clue = _clue(item, "hedged")
        if clue and _grounded(clue["text"], memory_text):
            hedged.append(clue)

    inferred = []
    for item in _as_list(payload.get("ai_inferred")):
        clue = _clue(item, "ai_inferred")
        if not clue or not _grounded(clue["text"], memory_text):
            continue
        if _repeats_hedge(clue, hedged):
            continue
        if clue["confidence"] == "unknown":
            clue["confidence"] = "low"
        inferred.append(clue)

    missing = []
    for item in _as_list(payload.get("missing")):
        text = _clean_text(item if isinstance(item, str) else "")
        if text:
            missing.append(text)

    def _assign(items, prefix):
        unique = []
        seen = set()
        for item in items:
            key = (item["source"], item["facet"], item["text"].lower())
            if key in seen:
                continue
            seen.add(key)
            item["id"] = f"{prefix}{len(unique) + 1}"
            unique.append(item)
        return unique

    stated = _assign(stated, "s")
    hedged = _assign(hedged, "h")
    inferred = _assign(inferred, "i")
    return {
        "raw_memory": memory_text.strip(),
        "user_stated": stated,
        "hedged": hedged,
        "ai_inferred": inferred,
        "missing": missing[:8],
        "no_useful_clues": not bool(stated or hedged or inferred),
    }


def _string_list(value) -> list:
    items = []
    for item in _as_list(value):
        text = _clean_text(item if not isinstance(item, dict) else item.get("text", ""))
        if text:
            items.append(text)
    return items[:12]


def normalize_photo_reading(payload: dict, photo_id: str) -> dict:
    """Turn one model object into a photo reading. Empty fields stay empty."""
    if not isinstance(payload, dict):
        raise ValueError("Photo reading was not a JSON object.")
    observations = []
    for item in _as_list(payload.get("observations"))[:12]:
        if isinstance(item, str):
            item = {"text": item, "facet": "other", "confidence": "low"}
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"))
        if not text:
            continue
        observations.append({
            "facet": _facet(item.get("facet")),
            "text": text,
            "confidence": _confidence(item.get("confidence"), default="low"),
        })
    people_count = _clean_text(payload.get("people_count") or "unknown", limit=20) or "unknown"
    reading = {
        "photo_id": photo_id,
        "people_count": people_count,
        "people_arrangement": _clean_text(payload.get("people_arrangement")),
        "setting": _clean_text(payload.get("setting")),
        "objects": _string_list(payload.get("objects")),
        "appearance": _string_list(payload.get("appearance")),
        "activity": _clean_text(payload.get("activity")),
        "time_cues": _clean_text(payload.get("time_cues")),
        "not_visible": _string_list(payload.get("not_visible")),
        "summary": _clean_text(payload.get("summary"), limit=280),
        "confidence": _confidence(payload.get("confidence"), default="unknown"),
        "observations": observations,
        "failure_reason": "",
    }
    filled = any([
        reading["people_arrangement"],
        reading["setting"],
        reading["objects"],
        reading["appearance"],
        reading["activity"],
        reading["time_cues"],
        reading["summary"],
        reading["observations"],
        reading["people_count"] not in {"", "unknown"},
    ])
    reading["analysis_status"] = "ok" if filled else "weak"
    if reading["analysis_status"] == "weak":
        reading["failure_reason"] = "The reading of this photo was too thin to use strongly."
    return reading


def failed_reading(photo_id: str, reason: str) -> dict:
    return {
        "photo_id": photo_id,
        "analysis_status": "failed",
        "failure_reason": reason,
        "people_count": "unknown",
        "people_arrangement": "",
        "setting": "",
        "objects": [],
        "appearance": [],
        "activity": "",
        "time_cues": "",
        "not_visible": [],
        "summary": "",
        "confidence": "unknown",
        "observations": [],
    }


def readings_from_response(payload: dict) -> list:
    photos = payload.get("photos")
    if isinstance(photos, list):
        return [item for item in photos if isinstance(item, dict)]
    if any(key in payload for key in ("photo_id", "summary", "observations", "setting")):
        return [payload]
    raise ValueError("Photo reading JSON did not include photo descriptions.")
