"""Rank photos from structured memory clues and structured photo readings.

Scores explain an order. They never remove a photo.
"""

from recallpath.utils.text import (
    colors_in,
    content_tokens,
    is_social_only,
    neutral_people_phrase,
    parse_count,
    people_band,
)

_POSITIVE = {
    "user_stated": {"supported": 3.0, "partial": 1.5},
    "hedged": {"supported": 1.0, "partial": 0.5},
    "ai_inferred": {"supported": 1.0, "partial": 0.5},
    "recognition": {"supported": 2.0, "partial": 1.0},
}
_CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.75, "low": 0.45, "unknown": 0.45}
_SOURCE_RANK = {"user_stated": 3, "recognition": 2, "hedged": 1, "ai_inferred": 0}
_GENERIC_SCENE = {
    "outside", "environment", "somewhere", "place", "setting", "area", "location", "background",
}
_FACET_FIELDS = {
    "people": ("people_count", "people_arrangement"),
    "setting": ("setting",),
    "objects": ("objects",),
    "appearance": ("appearance",),
    "event": ("activity", "setting"),
    "time": ("time_cues",),
    "other": ("summary", "setting", "objects", "appearance", "activity"),
}


def _join_field(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    return str(value or "")


def _facet_text(reading: dict, facet: str) -> str:
    parts = [_join_field(reading.get(field)) for field in _FACET_FIELDS.get(facet, ())]
    for observation in reading.get("observations") or []:
        if observation.get("facet") in {facet, "other"} or facet == "other":
            parts.append(observation.get("text") or "")
    if facet != "time":
        parts.append(reading.get("summary") or "")
    return " ".join(part for part in parts if part)


def _observation_confidence(reading: dict, facet: str) -> str:
    levels = []
    for observation in reading.get("observations") or []:
        if observation.get("facet") in {facet, "other"}:
            levels.append(observation.get("confidence") or "unknown")
    if levels:
        for level in ("high", "medium", "low", "unknown"):
            if level in levels:
                return level
    return reading.get("confidence") or "unknown"


def _points(source: str, judgment: str, confidence: str) -> float:
    if judgment == "contradicted":
        if source != "user_stated" or confidence != "high":
            return 0.0
        return -2.0
    if judgment not in {"supported", "partial"}:
        return 0.0
    base = _POSITIVE.get(source, {}).get(judgment, 0.0)
    return round(base * _CONFIDENCE_WEIGHT.get(confidence, 0.45), 2)


def _judgments_for(clue: dict, reading: dict) -> list:
    found = []
    count_judgment = _people_judgment(clue, reading)
    color_judgment = _color_judgment(clue, reading)
    overlap = _overlap_judgment(clue, reading)
    if count_judgment is not None:
        found.append(count_judgment)
    if color_judgment is not None:
        found.append(color_judgment)
    if overlap["judgment"] != "not_visible" or not found:
        if not (overlap["judgment"] == "not_visible" and found):
            found.append(overlap)
    if not found:
        found.append(overlap)
    return found


def _base_judgment(clue: dict) -> dict:
    return {
        "clue_id": clue.get("id", ""),
        "clue_text": clue.get("text") or "",
        "source": clue.get("source") or "user_stated",
        "judgment": "not_visible",
        "points": 0.0,
        "reason": "Not used to rule this photo out.",
    }


def _count_judgment(clue: dict, reading: dict):
    text = clue.get("text") or ""
    if (clue.get("facet") or "") != "people":
        return None
    clue_count = parse_count(text)
    photo_count = parse_count(_join_field(reading.get("people_count")))
    if clue_count is None or photo_count is None or clue_count > 20 or photo_count > 20:
        return None
    source = clue.get("source") or "user_stated"
    confidence = reading.get("confidence") or "unknown"
    gap = abs(clue_count - photo_count)
    if gap == 0:
        kind = "supported"
    elif gap == 1:
        kind = "partial"
    elif source == "user_stated" and confidence == "high":
        kind = "contradicted"
    else:
        return None
    item = _base_judgment(clue)
    item["judgment"] = kind
    item["points"] = _points(source, kind, confidence)
    item["specificity"] = 3
    item["reason"] = _people_reason(kind, text, _count_phrase(photo_count))
    return item


def _count_phrase(photo_count: int) -> str:
    if photo_count == 1:
        return "one person"
    if photo_count == 2:
        return "two people"
    return f"{photo_count} people"


def _people_evidence(reading: dict) -> str:
    parts = []
    count = _join_field(reading.get("people_count"))
    if count and count.lower() != "unknown":
        parts.append(count)
    arrangement = _join_field(reading.get("people_arrangement"))
    if arrangement:
        parts.append(arrangement)
    for observation in reading.get("observations") or []:
        if observation.get("facet") == "people" and observation.get("text"):
            parts.append(observation["text"])
    if parts:
        return " ".join(parts)
    return _join_field(reading.get("summary"))


def _people_judgment(clue: dict, reading: dict):
    text = clue.get("text") or ""
    if is_social_only(content_tokens(text)):
        return None
    exact = _count_judgment(clue, reading)
    if exact is not None:
        return exact
    clue_band = people_band(text)
    evidence = _people_evidence(reading)
    photo_band = people_band(evidence)
    if not clue_band or not photo_band:
        return None
    source = clue.get("source") or "user_stated"
    confidence = reading.get("confidence") or "unknown"
    if clue_band == photo_band:
        kind = "supported"
    elif {clue_band, photo_band} == {"one", "several"} and source == "user_stated" and confidence == "high":
        kind = "contradicted"
    else:
        kind = "partial"
    phrase = neutral_people_phrase(photo_band, evidence)
    item = _base_judgment(clue)
    item["judgment"] = kind
    item["points"] = _points(source, kind, confidence)
    item["specificity"] = 3
    item["reason"] = _people_reason(kind, text, phrase)
    return item


def _color_judgment(clue: dict, reading: dict):
    if (clue.get("facet") or "other") != "appearance":
        return None
    tokens = content_tokens(clue.get("text") or "")
    clue_colors = colors_in(tokens)
    photo_colors = colors_in(content_tokens(_facet_text(reading, "appearance")))
    if not clue_colors or not photo_colors:
        return None
    source = clue.get("source") or "user_stated"
    confidence = reading.get("confidence") or "unknown"
    if clue_colors & photo_colors:
        kind = "supported"
    elif source == "user_stated" and confidence == "high":
        kind = "contradicted"
    else:
        return None
    item = _base_judgment(clue)
    item["judgment"] = kind
    item["points"] = _points(source, kind, confidence)
    item["specificity"] = 3
    item["reason"] = _color_reason(kind, clue.get("text") or "")
    return item


def _overlap_judgment(clue: dict, reading: dict) -> dict:
    source = clue.get("source") or "user_stated"
    text = clue.get("text") or ""
    facet = clue.get("facet") or "other"
    tokens = content_tokens(text)
    base = _base_judgment(clue)
    if is_social_only(tokens):
        base["reason"] = "A relationship like this is not visible, so it does not change the order."
        return base

    observed = content_tokens(_facet_text(reading, facet))
    ratio = _ratio(tokens, observed)
    kind = _ratio_kind(ratio)
    if kind == "not_visible":
        broader = content_tokens(_facet_text(reading, "other"))
        broader_ratio = _ratio(tokens, broader)
        if broader_ratio >= 0.67:
            kind = "partial"
            confidence = _observation_confidence(reading, "other")
        else:
            base["reason"] = "This detail was not clear in the photo reading, so it was not used against the photo."
            return base
    else:
        confidence = _observation_confidence(reading, facet)
    base["judgment"] = kind
    base["points"] = _points(source, kind, confidence)
    base["specificity"] = _overlap_specificity(tokens, facet)
    if base["specificity"] == 0 and base["points"] > 0:
        base["points"] = round(base["points"] * 0.5, 2)
    base["reason"] = _overlap_reason(kind, source, text)
    return base


def _overlap_specificity(tokens: set, facet: str) -> int:
    if tokens and tokens <= _GENERIC_SCENE:
        return 0
    if facet in {"people", "objects", "appearance"}:
        return 2
    return 1


def _ratio(left: set, right: set) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _ratio_kind(ratio: float) -> str:
    if ratio >= 0.67:
        return "supported"
    if ratio >= 0.34:
        return "partial"
    return "not_visible"


def _people_reason(kind: str, text: str, phrase: str) -> str:
    visible = phrase or "the people in the reading"
    if kind == "contradicted":
        return f"The reading shows {visible}, which looks different from “{text}”."
    if kind == "supported":
        return f"The reading shows {visible}, which lines up with “{text}”."
    if kind == "partial":
        return f"The reading shows {visible}, which only partly matches “{text}”."
    return "The number of people was too uncertain to use against this photo."


def _color_reason(kind: str, text: str) -> str:
    if kind == "contradicted":
        return f"The clothing colour looks different from “{text}”."
    if kind == "supported":
        return f"The appearance lines up with “{text}”."
    return "The appearance was too uncertain to use against this photo."


def _overlap_reason(kind: str, source: str, text: str) -> str:
    if kind == "supported":
        return f"Lines up with “{text}”."
    if kind == "partial":
        return f"Partly lines up with “{text}”."
    if source == "hedged":
        return f"“{text}” was uncertain, so it did not rule this photo out."
    return "Not used to rule this photo out."


def _headline(judgments: list, status: str) -> str:
    if status == "failed":
        return "This photo could not be read. It stays here so you can still recognise it."
    if status == "pending":
        return "This photo has not been checked yet. It stays visible."
    if status == "weak":
        prefix = "The automatic reading was thin. "
    else:
        prefix = ""
    positives = [item for item in judgments if item["points"] > 0]
    conflicts = [item for item in judgments if item["judgment"] == "contradicted"]
    if not positives and not conflicts:
        return prefix + "Nothing specific lined up. It is still in the set."
    parts = []
    if positives:
        parts.append(_strongest(positives)[0]["reason"].rstrip("."))
    elif conflicts:
        parts.append(conflicts[0]["reason"].rstrip("."))
    return prefix + ". ".join(parts) + "."


def _strongest(judgments: list) -> list:
    """Prefer a supported, specific, user-stated clue over a repeated generic scene clue."""
    specific = [item for item in judgments if item.get("specificity", 1) > 0]
    pool = specific or list(judgments)
    pool.sort(key=lambda item: (
        -item.get("specificity", 0),
        -item.get("points", 0),
        -_SOURCE_RANK.get(item.get("source"), 0),
    ))
    chosen = []
    seen = []
    for item in pool:
        tokens = content_tokens(item.get("clue_text") or "")
        if tokens and any(tokens <= previous or previous <= tokens for previous in seen):
            continue
        chosen.append(item)
        seen.append(tokens)
        if len(chosen) == 2:
            break
    return chosen or pool[:1]


def _explanations(judgments: list, status: str, failure_reason: str) -> list:
    lines = []
    if status == "failed":
        lines.append(failure_reason or "The photo reading failed. Nothing was invented for it.")
    elif status == "weak" and failure_reason:
        lines.append(failure_reason)
    ordered = sorted(
        judgments,
        key=lambda item: (
            0 if item.get("points", 0) > 0 else 1,
            -item.get("specificity", 0),
            -item.get("points", 0),
            -_SOURCE_RANK.get(item.get("source"), 0),
        ),
    )
    for item in ordered:
        if item["judgment"] == "not_visible" and item["source"] not in {"hedged", "ai_inferred"}:
            continue
        if item.get("specificity") == 0 and any(line_item.get("specificity", 0) > 0 and line_item.get("points", 0) > 0 for line_item in judgments):
            continue
        label = {
            "user_stated": "You said",
            "hedged": "You were unsure",
            "ai_inferred": "Interpreted",
            "recognition": "From a photo you said looked closer",
        }.get(item["source"], "Clue")
        lines.append(f"{label}: {item['reason']}")
    if not lines:
        lines.append("No clue was strong enough to move this photo, so it stayed in the set.")
    return lines[:8]


def _status(photo: dict) -> str:
    analysis = photo.get("analysis")
    if not analysis:
        return "pending"
    return analysis.get("analysis_status") or "failed"


def score_photos(memory: dict, photos: list, recognition_clues=None) -> list:
    clues = []
    clues.extend(memory.get("user_stated") or [])
    clues.extend(memory.get("hedged") or [])
    clues.extend(memory.get("ai_inferred") or [])
    clues.extend(recognition_clues or [])
    ranked = []
    for photo in photos:
        status = _status(photo)
        reading = photo.get("analysis") or {}
        if status in {"pending", "failed"}:
            judgments = []
            score = None
        else:
            judgments = []
            for clue in clues:
                judgments.extend(_judgments_for(clue, reading))
            score = round(sum(item["points"] for item in judgments), 2)
            if status == "weak" and score and score > 0:
                score = round(score * 0.75, 2)
        ranked.append({
            "photo_id": photo["id"],
            "filename": photo.get("filename") or "",
            "score": score,
            "group": "unchecked" if score is None else "other",
            "reason": _headline(judgments, status),
            "explanation": _explanations(judgments, status, reading.get("failure_reason", "")),
            "judgments": judgments,
        })
    _assign_groups(ranked)
    ranked.sort(key=lambda item: (
        {"closer": 0, "other": 1, "unchecked": 2}[item["group"]],
        -(item["score"] if item["score"] is not None else -10_000),
        item["filename"],
    ))
    return ranked


def _assign_groups(ranked: list) -> None:
    scored = [item for item in ranked if item["score"] is not None]
    if not scored:
        return
    best = max(item["score"] for item in scored)
    if best <= 0:
        return
    cutoff = best * 0.5
    for item in scored:
        if item["score"] > 0 and item["score"] >= cutoff:
            item["group"] = "closer"


def unranked_photos(photos: list) -> list:
    """Show the collection with no pretended match order."""
    rows = []
    for photo in photos:
        status = _status(photo)
        rows.append({
            "photo_id": photo["id"],
            "filename": photo.get("filename") or "",
            "score": None,
            "group": "unchecked",
            "reason": "These photos are not ranked. The description did not include a usable clue.",
            "explanation": ["Add a visual detail you remember, then search again."],
            "judgments": [],
        })
        if status == "failed":
            rows[-1]["reason"] = "This photo could not be read, and there was no clue to rank with."
    rows.sort(key=lambda item: item["filename"])
    return rows


def recognition_clues_from_photo(photo: dict, limit: int = 4) -> list:
    reading = photo.get("analysis") or {}
    clues = []
    for observation in reading.get("observations") or []:
        if observation.get("confidence") not in {"high", "medium"}:
            continue
        text = (observation.get("text") or "").strip()
        if not text:
            continue
        clues.append({
            "id": f"rec-{photo['id']}-{len(clues) + 1}",
            "source": "recognition",
            "facet": observation.get("facet") or "other",
            "text": text,
            "quote": "",
            "confidence": observation.get("confidence"),
        })
        if len(clues) >= limit:
            break
    if not clues and reading.get("summary"):
        clues.append({
            "id": f"rec-{photo['id']}-1",
            "source": "recognition",
            "facet": "other",
            "text": reading["summary"],
            "quote": "",
            "confidence": "medium",
        })
    return clues
