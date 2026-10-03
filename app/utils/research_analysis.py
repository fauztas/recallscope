"""
RecallScope — Phase 4 research analysis

Aggregates the audited Phase 3 classifications. Counts are calculated from
data/public_evidence_classified.csv. This module does not call an LLM, does
not modify raw or relevance evidence, and does not treat Unknown as No.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from app.classify_pipeline import load_classified_dataset
from app.utils.llm_helper import FAILURE_STAGES

CORPUS_SHARE_LABEL = "Share of this interim classified public-evidence corpus"
SMALL_COUNT_NOTE = "Directional signal only — small evidence count."
SMALL_COUNT_THRESHOLD = 5
DISCLAIMER = (
    "Frequencies in this analysis describe this interim public-evidence corpus only. "
    "They are not prevalence among Google Photos users."
)

UNSTATED_MARKERS = {
    "",
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

# Substring groups applied only to saved clue fields. This is not a new
# memory taxonomy and it is not applied to the original post text.
CLUE_COMPARISONS = [
    ("People", ["grandma"]),
    ("Objects", ["sticky note", "blowtorch", "sunfish", "truck", "bike", "cat", "dog"]),
    ("Place or location", ["museum"]),
    ("Event or context", ["visit", "event"]),
    ("Approximate or relative time", ["time frame", "years gone by", "years"]),
    ("Exact or stated date", ["date"]),
    ("Visible text or added words", ["filename", "description", "phrase", "keyword"]),
    ("Visual characteristics", ["yellow", "close-up"]),
    ("Sequence or relationship to another memory", ["older photo", "recent photo", "same item", "same event"]),
]

ADDED_WORD_TERMS = ("filename", "description", "phrase", "tag", "renam")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def analysis_output_path() -> Path:
    return _project_root() / "data" / "research_analysis.json"


def _raw_record_count() -> int:
    raw_path = _project_root() / "data" / "public_evidence_raw.csv"
    if not raw_path.exists():
        return 0
    raw = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
    return int(len(raw))


def _is_unstated(value: Any) -> bool:
    return str(value).strip().lower() in UNSTATED_MARKERS


def _is_substantive(value: Any) -> bool:
    return not _is_unstated(value)


def _as_text(value: Any) -> str:
    return str(value).strip()


def _stage_code(stage: Any) -> str:
    text = _as_text(stage)
    return text.split(" ")[0] if text.startswith("F") else text


def _mix(values: Sequence[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        key = _as_text(value) if _as_text(value) else "Unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _share(count: int, total: int) -> Dict[str, Any]:
    percentage = round((count / total) * 100, 1) if total else 0.0
    return {
        "count": int(count),
        "total": int(total),
        "percentage_one_decimal": percentage,
        "label": CORPUS_SHARE_LABEL,
        "display": f"{count} of {total} ({percentage:.1f}%)",
    }


def _small_note(count: int) -> str:
    if count < SMALL_COUNT_THRESHOLD:
        return SMALL_COUNT_NOTE
    return ""


def _excerpt(text: Any, limit: int = 220) -> str:
    compact = " ".join(_as_text(text).split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _ids(frame: pd.DataFrame) -> List[str]:
    return frame["record_id"].astype(str).tolist()


def _source_mix(frame: pd.DataFrame) -> Dict[str, int]:
    if frame.empty:
        return {}
    return _mix(frame["source"].tolist())


def _strength_mix(frame: pd.DataFrame) -> Dict[str, int]:
    if frame.empty:
        return {}
    return _mix(frame["evidence_strength"].tolist())


def _examples(frame: pd.DataFrame, limit: int = 2) -> List[Dict[str, str]]:
    if frame.empty:
        return []
    strength_rank = {"High": 0, "Medium": 1, "Low": 2}
    ordered = frame.copy()
    ordered["_rank"] = ordered["evidence_strength"].map(lambda value: strength_rank.get(_as_text(value), 3))
    ordered = ordered.sort_values(["_rank", "record_id"])
    examples = []
    for _, row in ordered.head(limit).iterrows():
        examples.append({
            "record_id": _as_text(row["record_id"]),
            "source": _as_text(row["source"]),
            "source_url": _as_text(row["source_url"]),
            "evidence_strength": _as_text(row["evidence_strength"]),
            "primary_failure_stage": _as_text(row["primary_failure_stage"]),
            "excerpt": _excerpt(row["original_text"]),
        })
    return examples


def _describes_query(value: Any) -> bool:
    """True only when the saved behaviour field describes a search or query."""
    if not _is_substantive(value):
        return False
    text = _as_text(value).lower()
    if "searches through" in text or "searching within" in text:
        return False
    markers = (
        "search parameter",
        "keyword",
        "typed",
        "query",
        "searched",
        "search for",
        "search function",
        "phrase search",
        "exact phrase",
    )
    if any(marker in text for marker in markers):
        return True
    return text.startswith("search")


def _contains_any(value: Any, terms: Sequence[str]) -> bool:
    if not _is_substantive(value):
        return False
    text = _as_text(value).lower()
    return any(term in text for term in terms)


def _matched_terms(value: Any, terms: Sequence[str]) -> List[str]:
    if not _is_substantive(value):
        return []
    text = _as_text(value).lower()
    return [term for term in terms if term in text]


def _signal_counts(frame: pd.DataFrame, column: str) -> Dict[str, int]:
    counts = {"Yes": 0, "No": 0, "Unknown": 0}
    for value in frame[column].tolist():
        text = _as_text(value)
        if text in counts:
            counts[text] += 1
        elif _is_unstated(text):
            counts["Unknown"] += 1
        else:
            counts["Unknown"] += 1
    return counts


def _review_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    return int(frame["needs_human_review"].sum())


def _confidence(frame: pd.DataFrame, *, direct_count: bool = False) -> str:
    """Conservative confidence. A direct field count can be Medium. Causal claims stay Low when evidence is thin."""
    count = int(len(frame))
    if count < 3:
        return "Low"
    low_share = float((frame["evidence_strength"] == "Low").mean()) if count else 1.0
    review_share = float(frame["needs_human_review"].mean()) if count else 1.0
    # Direct field counts can support a medium descriptive claim.
    # They do not receive High, because this corpus does not identify a cause.
    if direct_count and count >= 5 and low_share <= 0.5:
        return "Medium"
    if count >= 5 and review_share < 0.35 and low_share < 0.35:
        return "Medium"
    return "Low"


def _stage_rows(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    total = int(len(frame))
    rows = []
    for stage in FAILURE_STAGES:
        subset = frame[frame["primary_failure_stage"] == stage]
        count = int(len(subset))
        rows.append({
            "failure_stage": stage,
            "observed": count > 0,
            "record_count": count,
            "share": _share(count, total),
            "evidence_strength_mix": _strength_mix(subset),
            "source_mix": _source_mix(subset),
            "human_review_count": _review_count(subset),
            "supporting_record_ids": _ids(subset),
        })
    return rows


def _behaviour_row(
    name: str,
    supported: pd.DataFrame,
    contradicted: Optional[pd.DataFrame],
    not_established: pd.DataFrame,
    note: str,
) -> Dict[str, Any]:
    return {
        "behaviour": name,
        "explicitly_supported_count": int(len(supported)),
        "explicitly_supported_record_ids": _ids(supported),
        "explicitly_contradicted_count": None if contradicted is None else int(len(contradicted)),
        "explicitly_contradicted_record_ids": [] if contradicted is None else _ids(contradicted),
        "not_established_count": int(len(not_established)),
        "not_established_record_ids": _ids(not_established),
        "note": note,
        "small_count_note": _small_note(int(len(supported))),
    }


def _behaviours(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    query = frame[frame["search_or_browse_behavior"].map(_describes_query)]
    query_unknown = frame[frame["search_or_browse_behavior"].map(_is_unstated)]
    reform = frame[frame["reformulation_behavior"].map(_is_substantive)]
    reform_unknown = frame[frame["reformulation_behavior"].map(_is_unstated)]
    manual_text = frame[frame["manual_browsing_behavior"].map(_is_substantive)]
    manual_unknown = frame[frame["manual_browsing_behavior"].map(_is_unstated)]
    remembered = frame[frame["remembered_clues"].map(_is_substantive)]
    remembered_unknown = frame[frame["remembered_clues"].map(_is_unstated)]
    forgotten = frame[frame["missing_or_forgotten_clues"].map(_is_substantive)]
    forgotten_unknown = frame[frame["missing_or_forgotten_clues"].map(_is_unstated)]
    workaround = frame[frame["workaround"].map(_is_substantive)]
    workaround_unknown = frame[frame["workaround"].map(_is_unstated)]
    review = frame[frame["needs_human_review"] == True]
    not_review = frame[frame["needs_human_review"] == False]

    rows = [
        _behaviour_row(
            "Query or search attempt described in search_or_browse_behavior",
            query,
            None,
            query_unknown,
            "Supported only when the saved behaviour text describes a search or query. Unknown means the behaviour was not established, not that no search occurred.",
        ),
        _behaviour_row(
            "Query reformulation described in reformulation_behavior",
            reform,
            None,
            reform_unknown,
            "A substantive reformulation field is required. Unknown is not counted as no reformulation.",
        ),
        _behaviour_row(
            "Manual browsing described in manual_browsing_behavior",
            manual_text,
            None,
            manual_unknown,
            "Counted from the saved manual-browsing field. A missing description is Unknown, not evidence that browsing did not happen.",
        ),
    ]

    signal_notes = {
        "manual_scroll_signal": "Yes, No, and Unknown are kept separate. Unknown is not converted to No.",
        "candidate_overload_signal": "Yes, No, and Unknown are kept separate. Unknown is not converted to No.",
        "recognition_difficulty_signal": "Yes means the saved signal says recognition was difficult. Unknown means it was not established.",
        "query_difficulty_signal": "Yes, No, and Unknown are kept separate. One explicit No does not describe the rest of the corpus.",
    }
    for column, note in signal_notes.items():
        yes = frame[frame[column] == "Yes"]
        no = frame[frame[column] == "No"]
        unknown = frame[~frame[column].isin(["Yes", "No"])]
        rows.append(_behaviour_row(column, yes, no, unknown, note))

    rows.extend([
        _behaviour_row(
            "Remembered clues stated",
            remembered,
            None,
            remembered_unknown,
            "Counted when remembered_clues is a substantive saved value.",
        ),
        _behaviour_row(
            "Forgotten or uncertain clues stated",
            forgotten,
            None,
            forgotten_unknown,
            "Counted only when missing_or_forgotten_clues explicitly states something forgotten. Unknown means the post did not establish a forgotten clue.",
        ),
        _behaviour_row(
            "Workaround stated",
            workaround,
            None,
            workaround_unknown,
            "Counted when the saved workaround field describes a behaviour. Unknown is not treated as no workaround.",
        ),
        _behaviour_row(
            "Human review required",
            review,
            None,
            not_review,
            "needs_human_review remains the Phase 3 flag. Records without that flag are not evidence that the classification is certain.",
        ),
    ])

    for outcome in ["Found", "Not Found", "Partially Found", "Gave Up", "Unknown"]:
        matched = frame[frame["retrieval_outcome"] == outcome]
        others = frame[frame["retrieval_outcome"] != outcome]
        rows.append(_behaviour_row(
            f"Retrieval outcome: {outcome}",
            matched,
            None,
            others if outcome == "Unknown" else frame.iloc[0:0],
            "Outcome values are kept distinct. Unknown is not counted as Not Found or Gave Up. Gave Up is used only when that outcome was saved.",
        ))
    return rows


def _clue_phrases(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    phrases = []
    for column in ("remembered_clues", "missing_or_forgotten_clues"):
        for _, row in frame.iterrows():
            value = _as_text(row[column])
            if not _is_substantive(value):
                continue
            phrases.append({
                "record_id": _as_text(row["record_id"]),
                "field": column,
                "saved_clue_text": value,
                "primary_failure_stage": _as_text(row["primary_failure_stage"]),
                "evidence_strength": _as_text(row["evidence_strength"]),
                "source": _as_text(row["source"]),
            })
    return phrases


def _clue_groups(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    groups = []
    for label, terms in CLUE_COMPARISONS:
        matched_rows = []
        for _, row in frame.iterrows():
            remembered_hits = _matched_terms(row["remembered_clues"], terms)
            forgotten_hits = _matched_terms(row["missing_or_forgotten_clues"], terms)
            hits = remembered_hits + [term for term in forgotten_hits if term not in remembered_hits]
            if not hits:
                continue
            matched_rows.append((row, hits, remembered_hits, forgotten_hits))
        subset = frame[frame["record_id"].isin([row["record_id"] for row, _, _, _ in matched_rows])]
        groups.append({
            "comparison_label": label,
            "match_terms": list(terms),
            "record_count": int(len(subset)),
            "share": _share(int(len(subset)), int(len(frame))),
            "supporting_record_ids": _ids(subset),
            "matches": [
                {
                    "record_id": _as_text(row["record_id"]),
                    "matched_terms": hits,
                    "remembered_clues": _as_text(row["remembered_clues"]),
                    "missing_or_forgotten_clues": _as_text(row["missing_or_forgotten_clues"]),
                    "matched_in_remembered_clues": bool(remembered_hits),
                    "matched_in_forgotten_clues": bool(forgotten_hits),
                }
                for row, hits, remembered_hits, forgotten_hits in matched_rows
            ],
            "evidence_strength_mix": _strength_mix(subset),
            "failure_stage_mix": _mix(subset["primary_failure_stage"].tolist()) if not subset.empty else {},
            "small_count_note": _small_note(int(len(subset))),
            "absence_note": (
                "No saved clue field matched these terms. That is not evidence this clue type was absent for the person."
                if subset.empty
                else "Matches are substring hits on saved clue fields only."
            ),
        })
    return groups


def _memory(frame: pd.DataFrame) -> Dict[str, Any]:
    remembered = frame[frame["remembered_clues"].map(_is_substantive)]
    forgotten = frame[frame["missing_or_forgotten_clues"].map(_is_substantive)]
    return {
        "schema_note": (
            "The Phase 3 schema stores free-text remembered_clues and missing_or_forgotten_clues. "
            "It does not store a clue-type enum. Comparison labels are substring matches on those saved fields. "
            "They are not a new taxonomy and they are not claimed to be the most common memory cues among all users."
        ),
        "remembered_clues_stated_count": int(len(remembered)),
        "remembered_clues_unknown_count": int(len(frame) - len(remembered)),
        "forgotten_clues_stated_count": int(len(forgotten)),
        "forgotten_clues_unknown_count": int(len(frame) - len(forgotten)),
        "saved_clue_phrases": _clue_phrases(frame),
        "comparison_groups": _clue_groups(frame),
    }


def _cross_item(
    question: str,
    observation: str,
    subset: pd.DataFrame,
    total: int,
    does_not_establish: str,
) -> Dict[str, Any]:
    count = int(len(subset))
    return {
        "question": question,
        "observation": observation,
        "record_count": count,
        "share": _share(count, total),
        "supporting_record_ids": _ids(subset),
        "source_mix": _source_mix(subset),
        "evidence_strength_mix": _strength_mix(subset),
        "failure_stage_mix": _mix(subset["primary_failure_stage"].tolist()) if count else {},
        "what_this_does_not_establish": does_not_establish,
        "small_count_note": _small_note(count),
    }


def _cross_patterns(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    total = int(len(frame))
    scroll_yes = frame[frame["manual_scroll_signal"] == "Yes"]
    manual_text = frame[frame["manual_browsing_behavior"].map(_is_substantive)]
    remembered = frame["remembered_clues"].map(_is_substantive)
    failed_outcome = frame["retrieval_outcome"].isin(["Not Found", "Partially Found"])
    clues_and_failed = frame[remembered & failed_outcome]
    reform = frame[frame["reformulation_behavior"].map(_is_substantive)]
    query_mask = frame["search_or_browse_behavior"].map(_describes_query)
    not_surfaced_outcome = frame[query_mask & frame["retrieval_outcome"].isin(["Not Found", "Partially Found"])]
    recognition = frame[(frame["primary_failure_stage"].str.startswith("F5")) | (frame["recognition_difficulty_signal"] == "Yes")]
    ambiguous = frame[frame["primary_failure_stage"].str.startswith("F8")]
    stated_photo = frame[frame["photo_type"].map(_is_substantive)]
    items = [
        _cross_item(
            "Which failure stages coexist with an explicit manual-scroll signal?",
            "manual_scroll_signal is Yes on the records listed. Stages are the audited primary stage for those same records.",
            scroll_yes,
            total,
            "A Yes scroll signal does not show that scrolling caused the failure, or that people who have no signal did not scroll.",
        ),
        _cross_item(
            "Which failure stages coexist with a described manual-browsing behaviour?",
            "manual_browsing_behavior contains a saved description on these records.",
            manual_text,
            total,
            "Described browsing is not evidence that search was impossible, and Unknown browsing fields are not evidence that browsing did not occur.",
        ),
        _cross_item(
            "Which remembered clues appear where the saved outcome is Not Found or Partially Found?",
            "Both a substantive remembered_clues value and an explicit Not Found or Partially Found outcome are present.",
            clues_and_failed,
            total,
            "This does not show that the clue caused the miss, or that retrieval failed where the outcome is Unknown.",
        ),
        _cross_item(
            "Where do the saved classifications describe query reformulation?",
            "reformulation_behavior is substantive only for the listed records.",
            reform,
            total,
            "Two or fewer reformulation descriptions cannot support a reformulation pattern beyond those records.",
        ),
        _cross_item(
            "Where does a described search have an explicit not-found or partial outcome?",
            "The saved behaviour describes a search, and retrieval_outcome is Not Found or Partially Found.",
            not_surfaced_outcome,
            total,
            "A not-found or partial outcome does not establish an indexing failure, a candidate gap, or an interpretation gap.",
        ),
        _cross_item(
            "Where are candidates surfaced but recognition marked difficult?",
            "Included only when the audited stage is F5 or recognition_difficulty_signal is Yes.",
            recognition,
            total,
            "A single recognition record is not a corpus pattern. Other records do not become recognition gaps by default.",
        ),
        _cross_item(
            "Where is the failure mechanism classified as ambiguous?",
            "The audited primary stage is F8 — Unknown / Insufficient Evidence.",
            ambiguous,
            total,
            "F8 means the stage is not established. It does not mean retrieval succeeded, and it does not identify a cause.",
        ),
    ]
    photo_item = _cross_item(
        "Are stated photo types associated with particular failure stages?",
        "Photo type is counted only when photo_type is substantive. Unknown photo types are excluded from this intersection.",
        stated_photo,
        total,
        "Most photo types in this corpus occur once. A repeated type is a directional signal, not an association among users.",
    )
    photo_item["photo_type_by_stage"] = [
        {
            "record_id": _as_text(row["record_id"]),
            "photo_type": _as_text(row["photo_type"]),
            "primary_failure_stage": _as_text(row["primary_failure_stage"]),
            "evidence_strength": _as_text(row["evidence_strength"]),
        }
        for _, row in stated_photo.sort_values("record_id").iterrows()
    ]
    items.append(photo_item)
    return items


def _card(
    name: str,
    observed: str,
    subset: pd.DataFrame,
    total: int,
    supports: str,
    does_not: str,
    limiting: str,
    *,
    direct_count: bool = False,
    confidence: Optional[str] = None,
) -> Dict[str, Any]:
    count = int(len(subset))
    return {
        "pattern_name": name,
        "what_was_observed": observed,
        "supporting_record_count": count,
        "supporting_record_ids": _ids(subset),
        "share": _share(count, total),
        "source_mix": _source_mix(subset),
        "evidence_strength_mix": _strength_mix(subset),
        "failure_stage_mix": _mix(subset["primary_failure_stage"].tolist()) if count else {},
        "example_excerpts": _examples(subset),
        "what_the_evidence_supports": supports,
        "what_the_evidence_does_not_establish": does_not,
        "confidence": confidence or _confidence(subset, direct_count=direct_count),
        "contradictory_or_limiting_evidence": limiting,
        "small_count_note": _small_note(count),
    }


def _pattern_cards(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    total = int(len(frame))
    query = frame["search_or_browse_behavior"].map(_describes_query)
    unsuccessful = frame[query & frame["retrieval_outcome"].isin(["Not Found", "Partially Found"])]
    manual = frame[
        frame["manual_browsing_behavior"].map(_is_substantive)
        | (frame["manual_scroll_signal"] == "Yes")
    ]
    added = frame[
        frame["remembered_clues"].map(lambda value: _contains_any(value, ADDED_WORD_TERMS))
        | frame["missing_or_forgotten_clues"].map(lambda value: _contains_any(value, ADDED_WORD_TERMS))
    ]
    ambiguous = frame[frame["primary_failure_stage"].str.startswith("F8")]
    interpretation = frame[frame["primary_failure_stage"].str.startswith("F3")]
    coverage = frame[frame["primary_failure_stage"].str.startswith("F7")]
    found = frame[frame["retrieval_outcome"] == "Found"]
    cards = [
        _card(
            "A described search ends not found or only partly found",
            "The saved search behaviour and the saved outcome both say the search missed photos or returned only some of them.",
            unsuccessful,
            total,
            "These posts explicitly describe a search whose saved outcome is Not Found or Partially Found.",
            "They do not establish why the photo was missing from the results. Most of these records remain F8 after audit.",
            "REC_019 records a search that initially failed and a later find. REC_006 says date search works. REC_022 records a found photo before a later scrolling task. Those records are not in this card.",
            direct_count=True,
        ),
        _card(
            "Manual scrolling or manual lookup is described",
            "The saved manual-browsing field is substantive, or manual_scroll_signal is Yes.",
            manual,
            total,
            "These records explicitly describe scrolling, album scanning, or a long manual lookup.",
            "They do not establish one shared failure stage. Some lookups follow a failed search, and some are the lookup itself.",
            "REC_004 is an album of more than 1,400 photos, which the audit kept as recognition difficulty. REC_022 describes scrolling after the looked-for photo was already found. Unknown scroll signals were not treated as No.",
            direct_count=True,
        ),
        _card(
            "Saved clue text names a filename, description, phrase, or tag",
            "remembered_clues contains filename, description, phrase, tag, or a rename wording.",
            added,
            total,
            "These classifications explicitly store a filename, description, phrase, or tag as a clue.",
            "They do not establish that metadata was unindexed. The audited stages differ.",
            "REC_014 says former keywords now return screenshots and that the photo can still be found manually. Its clue text is 'Keywords that formerly worked', which does not match the filename, description, phrase, or tag terms, so it is not included here.",
        ),
        _card(
            "The audited stage does not identify a specific mechanism",
            "primary_failure_stage is F8 — Unknown / Insufficient Evidence.",
            ambiguous,
            total,
            "For these records the audited classification does not support a stage from F1 through F7.",
            "F8 does not show that retrieval worked, and it does not show that the cause was indexing, recognition, or any other single stage.",
            "Eight classified records do have a specific audited stage. Those records are the limiting set for any claim that every post is ambiguous.",
            direct_count=True,
            confidence="High",
        ),
        _card(
            "Audited interpretation-gap records",
            "primary_failure_stage remains F3 — Interpretation Gap after the Phase 3 audit.",
            interpretation,
            total,
            "These three records kept an interpretation stage because the post describes a stated query and results the person treats as the wrong set.",
            "Three records do not show that interpretation is the main retrieval problem in this corpus or among Google Photos users.",
            "The other 19 classified records are not F3. REC_012 and REC_014 were moved to F8 because interpretation and a candidate gap both remained possible.",
        ),
        _card(
            "Audited coverage or indexing records",
            "primary_failure_stage remains F7 — Coverage / Indexing Gap after the Phase 3 audit.",
            coverage,
            total,
            "Two records still use F7. Both describe words added to a photo or video that did not bring the item back in search.",
            "Two records do not show an indexing failure across the corpus. The audit kept F7 as the closest reading, not as proof of an index defect.",
            "Seven earlier F7 labels were changed to F8 because a missing photo, by itself, did not show an indexing failure.",
        ),
        _card(
            "Explicit found outcome despite remaining friction",
            "retrieval_outcome is Found.",
            found,
            total,
            "These posts explicitly describe locating the item, while also describing friction before or after that find.",
            "A found outcome does not mean retrieval was easy, and it does not describe the records whose outcome is Unknown.",
            "Most classified outcomes are Not Found, Partially Found, or Unknown. Found is the exception in this corpus.",
        ),
    ]
    return [card for card in cards if card["supporting_record_count"] >= 2]


def _candidate(
    name: str,
    description: str,
    subset: pd.DataFrame,
    behaviours: str,
    consequence: str,
    alternative: str,
    gaps: str,
) -> Dict[str, Any]:
    return {
        "candidate_problem_area": name,
        "evidence_supported_description": description,
        "supporting_record_count": int(len(subset)),
        "supporting_record_ids": _ids(subset),
        "evidence_strength_profile": _strength_mix(subset),
        "failure_stage_mix": _mix(subset["primary_failure_stage"].tolist()) if not subset.empty else {},
        "relevant_observed_behaviours": behaviours,
        "user_consequence_visible_in_evidence": consequence,
        "alternative_explanation": alternative,
        "evidence_gaps": gaps,
        "confidence": _confidence(subset, direct_count=True),
        "small_count_note": _small_note(int(len(subset))),
        "ranked": False,
        "selected": False,
    }


def _candidates(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    query = frame["search_or_browse_behavior"].map(_describes_query)
    unsuccessful = frame[query & frame["retrieval_outcome"].isin(["Not Found", "Partially Found"])]
    manual = frame[
        frame["manual_browsing_behavior"].map(_is_substantive)
        | (frame["manual_scroll_signal"] == "Yes")
    ]
    added = frame[frame["remembered_clues"].map(lambda value: _contains_any(value, ADDED_WORD_TERMS))]
    candidates = [
        _candidate(
            "A described search does not return the photos the person expects",
            "In the supporting records, the saved behaviour describes a search and the saved outcome is Not Found or Partially Found.",
            unsuccessful,
            "Query attempt described; outcome Not Found or Partially Found. Reformulation is described in only a subset.",
            "The person reports missing photos, a subset of the expected photos, or results that do not include the looked-for item.",
            "The photo may be absent from the library, the query may be broader or narrower than the person assumes, or the post may not reveal which retrieval stage failed.",
            "Most supporting records are F8. The corpus cannot separate interpretation, candidate coverage, and indexing for this group.",
        ),
        _candidate(
            "Locating a remembered photo is described as manual scanning",
            "The supporting records have a saved manual-browsing description or an explicit Yes manual-scroll signal.",
            manual,
            "Manual scrolling, album scanning, or a long manual lookup is described. Some records also describe a search.",
            "The person describes scrolling through a long history, a large album, or a long lookup in order to reach the photo or nearby photos.",
            "Some records may be browse-first rather than a failed search. REC_004 is a large-album scanning problem. REC_022 scrolls after the first photo was found.",
            "The group mixes F4, F5, F7, and F8. It does not establish that manual scanning is the dominant failure mechanism.",
        ),
        _candidate(
            "A filename, description, phrase, or tag does not bring the item back",
            "The saved remembered clue names a filename, description, phrase, or tag.",
            added,
            "The person uses an exact filename, added description words, a phrase tag, or filename keywords. Workarounds are not established for every record.",
            "Search using those words fails, returns the wrong set, or requires a long manual lookup.",
            "The words may never have been searchable, the query may be handled as a date or as visible text, or the item may be present and reached another way.",
            "Only four records match. Their audited stages are F3, F7, and F8, so one technical explanation is not supported.",
        ),
    ]
    return [item for item in candidates if item["supporting_record_count"] >= 2]


def _found_challenge_detail(frame: pd.DataFrame, found: pd.DataFrame) -> str:
    detail = "Saved Found outcomes contradict a claim that retrieval always fails in this corpus."
    manual_success = frame[frame["record_id"] == "REC_014"]
    if not manual_success.empty:
        outcome = _as_text(manual_success.iloc[0]["retrieval_outcome"])
        detail += (
            " REC_014 says the photo can still be found manually while keyword search returns screenshots. "
            f"Its saved retrieval outcome is {outcome}, so that manual find is not counted as a Found outcome."
        )
    if found.empty:
        detail += " No classified record has retrieval_outcome Found."
    return detail


def _contradictions(frame: pd.DataFrame) -> Dict[str, Any]:
    total = int(len(frame))
    f8 = frame[frame["primary_failure_stage"].str.startswith("F8")]
    f5 = frame[frame["primary_failure_stage"].str.startswith("F5")]
    f7 = frame[frame["primary_failure_stage"].str.startswith("F7")]
    low = frame[frame["evidence_strength"] == "Low"]
    review = frame[frame["needs_human_review"] == True]
    found = frame[frame["retrieval_outcome"] == "Found"]
    outcome_unknown = frame[frame["retrieval_outcome"] == "Unknown"]
    forgotten = frame[frame["missing_or_forgotten_clues"].map(_is_substantive)]
    unobserved = [
        stage for stage in FAILURE_STAGES
        if int((frame["primary_failure_stage"] == stage).sum()) == 0
    ]
    challenges = [
        {
            "challenge": "A single failure stage does not dominate this corpus.",
            "record_count": int(len(f8)),
            "supporting_record_ids": _ids(f8),
            "detail": (
                f"{len(f8)} of {total} audited records are F8. "
                "That blocks any conclusion that recognition, indexing, or interpretation is the main breakdown."
            ),
        },
        {
            "challenge": "Recognition gap is a single-record observation.",
            "record_count": int(len(f5)),
            "supporting_record_ids": _ids(f5),
            "detail": (
                "Only the listed record remains F5. "
                "recognition_difficulty_signal is Yes there and is not Yes across the corpus. "
                "This does not support treating recognition as the research answer."
            ),
        },
        {
            "challenge": "Coverage or indexing remains a two-record reading.",
            "record_count": int(len(f7)),
            "supporting_record_ids": _ids(f7),
            "detail": (
                "REC_019 and REC_024, where present, describe added words that did not surface the item. "
                "A user report that search missed a photo does not establish an indexing defect. "
                + SMALL_COUNT_NOTE
            ),
        },
        {
            "challenge": "Some records show the item was found, or could still be found manually.",
            "record_count": int(len(found)),
            "supporting_record_ids": _ids(found),
            "detail": _found_challenge_detail(frame, found),
        },
        {
            "challenge": "Low evidence strength limits how hard the findings can be pressed.",
            "record_count": int(len(low)),
            "supporting_record_ids": _ids(low),
            "detail": "These records are short or general. Their stage and behaviour fields should not be pooled with high-strength records as if they were equal proof.",
        },
        {
            "challenge": "Human review remains open on a large part of the classified corpus.",
            "record_count": int(len(review)),
            "supporting_record_ids": _ids(review),
            "detail": "Review flags mark ambiguity, thin text, or a stage that was safer as F8. They are unresolved, not confirmed causes.",
        },
        {
            "challenge": "Many outcomes do not establish whether retrieval failed.",
            "record_count": int(len(outcome_unknown)),
            "supporting_record_ids": _ids(outcome_unknown),
            "detail": "retrieval_outcome Unknown was not converted to Not Found or Gave Up.",
        },
        {
            "challenge": "An explicit forgotten clue is rare in the saved fields.",
            "record_count": int(len(forgotten)),
            "supporting_record_ids": _ids(forgotten),
            "detail": (
                "Only records with a substantive missing_or_forgotten_clues value are listed. "
                "Unknown forgotten clues are not evidence that nothing was forgotten."
            ),
        },
        {
            "challenge": "Some failure stages were not observed.",
            "record_count": 0,
            "supporting_record_ids": [],
            "detail": (
                "Unobserved stages: "
                + (", ".join(unobserved) if unobserved else "none")
                + ". Absence from this corpus is not evidence those stages do not occur."
            ),
        },
    ]
    return {
        "title": "Contradictions & Evidence Gaps",
        "challenges": challenges,
    }


def _limitations(frame: pd.DataFrame, raw_count: int, uncertain_ids: Sequence[str]) -> List[str]:
    source_mix = _source_mix(frame)
    source_text = ", ".join(f"{name}: {count}" for name, count in source_mix.items()) or "none"
    return [
        f"The current raw corpus contains {raw_count} records.",
        f"{len(frame)} records were classified as Relevant and are the Phase 4 analysis input.",
        (
            f"{len(list(uncertain_ids))} records remain Uncertain and outside automatic Phase 3 classification: "
            + (", ".join(uncertain_ids) if uncertain_ids else "none")
            + "."
        ),
        f"The classified source mix is limited ({source_text}).",
        "Public complaint posts are self-selected.",
        "Complaint evidence may overrepresent severe or unresolved retrieval experiences.",
        "This corpus is qualitative and directional.",
        "Corpus percentages are not population prevalence among Google Photos users.",
        "Public posts often show what the person tried. They often do not show everything the person remembered before searching.",
        "A report that a photo did not appear cannot, by itself, establish a cause such as an indexing failure.",
        DISCLAIMER,
    ]


def _trace_index(frame: pd.DataFrame) -> List[Dict[str, str]]:
    rows = []
    for _, row in frame.sort_values("record_id").iterrows():
        rows.append({
            "record_id": _as_text(row["record_id"]),
            "source": _as_text(row["source"]),
            "date": _as_text(row["date"]),
            "source_url": _as_text(row["source_url"]),
            "original_text": _as_text(row["original_text"]),
            "primary_failure_stage": _as_text(row["primary_failure_stage"]),
            "evidence_strength": _as_text(row["evidence_strength"]),
            "retrieval_outcome": _as_text(row["retrieval_outcome"]),
            "needs_human_review": bool(row["needs_human_review"]),
        })
    return rows


def build_research_analysis(frame: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Build the Phase 4 analysis from the corrected classified CSV.
    Passing a frame is supported for tests. The default path does not call an LLM.
    """
    loaded, metrics = load_classified_dataset()
    if frame is None:
        frame = loaded
    else:
        frame = frame.copy()
    if "needs_human_review" in frame.columns:
        frame["needs_human_review"] = frame["needs_human_review"].map(
            lambda value: value if isinstance(value, bool) else str(value).strip().lower() in {"true", "1", "yes"}
        )

    classified = frame[frame["classification_status"] == "classified"].copy() if "classification_status" in frame.columns else frame.copy()
    total = int(len(classified))
    raw_count = _raw_record_count()
    uncertain_ids = [item["record_id"] for item in metrics.get("uncertain_records", [])]
    stage_rows = _stage_rows(classified)
    observed_stage_total = sum(row["record_count"] for row in stage_rows)

    analysis = {
        "phase": "Phase 4 — Research Analysis",
        "disclaimer": DISCLAIMER,
        "share_label": CORPUS_SHARE_LABEL,
        "input": {
            "classified_record_count": total,
            "raw_record_count": raw_count,
            "uncertain_record_ids": uncertain_ids,
            "classified_record_ids": _ids(classified),
            "source_distribution": _source_mix(classified),
            "evidence_strength_distribution": _strength_mix(classified),
            "human_review_count": _review_count(classified),
        },
        "failure_stages": stage_rows,
        "failure_stage_count_check": {
            "sum_of_stage_counts": observed_stage_total,
            "classified_record_count": total,
            "matches": observed_stage_total == total,
        },
        "behaviours": _behaviours(classified),
        "memory_clues": _memory(classified),
        "cross_patterns": _cross_patterns(classified),
        "pattern_cards": _pattern_cards(classified),
        "candidate_problem_areas": _candidates(classified),
        "contradictions_and_evidence_gaps": _contradictions(classified),
        "research_limitations": _limitations(classified, raw_count, uncertain_ids),
        "trace_index": _trace_index(classified),
    }
    return analysis


def save_research_analysis(analysis: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> Path:
    """Write the reproducible analysis artifact. Does not modify evidence files."""
    if analysis is None:
        analysis = build_research_analysis()
    output = path or analysis_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(output)
    return output
