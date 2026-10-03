"""
RecallScope — Phase 5 read-only data access

Loads the saved raw, relevance, classification, and analysis artifacts.
This module does not classify evidence and does not write research files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

INTERIM_CORPUS_LABEL = (
    "INTERIM PUBLIC-EVIDENCE CORPUS — not representative of all Google Photos users"
)
SHARE_LABEL = "Share of this interim classified public-evidence corpus"

STAGE_MEANINGS = {
    "F1 — Recall Gap": "The person cannot remember enough useful detail.",
    "F2 — Expression Gap": "The person remembers something useful but struggles to turn it into a search.",
    "F3 — Interpretation Gap": "The person states a clue, and the results look like the search handled that clue poorly.",
    "F4 — Candidate Gap": "The wanted photo does not show up among the results.",
    "F5 — Recognition Gap": "Results are present, but picking out the right photo is difficult.",
    "F6 — Refinement Gap": "After a miss, the person struggles to improve the search.",
    "F7 — Coverage / Indexing Gap": "The report is read as a coverage or indexing problem. The report alone does not prove that cause.",
    "F8 — Unknown / Insufficient Evidence": "The report does not support a specific failure stage.",
}

CLASSIFICATION_FIELDS = [
    "photo_type",
    "remembered_clues",
    "missing_or_forgotten_clues",
    "search_or_browse_behavior",
    "reformulation_behavior",
    "manual_browsing_behavior",
    "workaround",
    "failure_reason",
    "ai_interpretation",
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
    "classification_status",
]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False).fillna("")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_research_analysis() -> Dict[str, Any]:
    """Read the approved Phase 4 artifact. Does not rebuild or rewrite it."""
    path = project_root() / "data" / "research_analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_discovery_records() -> List[Dict[str, Any]]:
    """
    Join saved raw evidence, relevance decisions, and audited classifications.
    Records without a classification stay unclassified. Their fields are not filled with guesses.
    """
    root = project_root() / "data"
    raw = _read_csv(root / "public_evidence_raw.csv")
    relevance = _read_csv(root / "public_evidence_relevance.csv")
    classified = _read_csv(root / "public_evidence_classified.csv")

    relevance_by_id = {row["record_id"]: row for _, row in relevance.iterrows()}
    classified_by_id = {row["record_id"]: row for _, row in classified.iterrows()}
    records = []
    for _, source in raw.iterrows():
        record_id = source["record_id"]
        decision = relevance_by_id.get(record_id)
        audit = classified_by_id.get(record_id)
        item = {
            "record_id": record_id,
            "source": source["source"],
            "date": source["date"],
            "original_text": source["original_text"],
            "source_url": source["source_url"],
            "relevance_label": decision["relevance_label"] if decision is not None else "",
            "relevance_reason": decision["relevance_reason"] if decision is not None else "",
            "review_required": _as_bool(decision["review_required"]) if decision is not None else False,
            "classified": audit is not None,
        }
        for field in CLASSIFICATION_FIELDS:
            if audit is None:
                item[field] = ""
            elif field == "needs_human_review":
                item[field] = _as_bool(audit[field])
            else:
                item[field] = audit[field]
        records.append(item)
    return records


def classified_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [record for record in records if record["classified"]]


def count_by(records: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        value = str(record.get(field, "")).strip() or "Not recorded"
        counts[value] = counts.get(value, 0) + 1
    return counts
