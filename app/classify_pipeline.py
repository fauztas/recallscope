"""
RecallScope — Phase 3 classification pipeline

Reads relevance decisions, asks Groq to classify Relevant records only, and
writes a new CSV. Raw evidence and the Phase 2 relevance file are read-only.
Uncertain records are not sent to the model.
"""

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.utils.llm_helper import (
    AI_FIELDS,
    LLM_MODEL,
    LLM_PROVIDER,
    apply_phase2_review_flag,
    classify_evidence_record,
    repair_classification_integrity,
)

PRESERVED_FIELDS = [
    "record_id",
    "source",
    "date",
    "original_text",
    "source_url",
    "relevance_label",
    "relevance_reason",
    "review_required",
]

OUTPUT_FIELDS = PRESERVED_FIELDS + AI_FIELDS + [
    "classification_status",
    "classification_error",
    "llm_provider",
    "llm_model",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _data_paths() -> Dict[str, Path]:
    data_dir = _project_root() / "data"
    return {
        "raw": data_dir / "public_evidence_raw.csv",
        "relevance": data_dir / "public_evidence_relevance.csv",
        "classified": data_dir / "public_evidence_classified.csv",
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_csv(path: Path) -> pd.DataFrame:
    # keep_default_na=False preserves the legitimate value "None".
    return pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False).fillna("")


def _write_classified(rows: List[Dict[str, Any]], output_path: Path) -> None:
    frame = pd.DataFrame(rows, columns=OUTPUT_FIELDS)
    temporary_path = output_path.with_suffix(".csv.tmp")
    frame.to_csv(temporary_path, index=False, encoding="utf-8")
    temporary_path.replace(output_path)


def _preserved_fields(source_row: pd.Series) -> Dict[str, Any]:
    preserved = {field: str(source_row[field]) for field in PRESERVED_FIELDS if field != "review_required"}
    preserved["review_required"] = _as_bool(source_row["review_required"])
    return preserved


def _completed_row(source_row: pd.Series, ai_fields: Dict[str, Any]) -> Dict[str, Any]:
    completed = _preserved_fields(source_row)
    for field in AI_FIELDS:
        completed[field] = ai_fields.get(field, "Unknown")
    completed["needs_human_review"] = _as_bool(completed["needs_human_review"])
    completed["classification_status"] = str(ai_fields.get("classification_status", "classified"))
    completed["classification_error"] = str(ai_fields.get("classification_error", ""))
    completed["llm_provider"] = str(ai_fields.get("llm_provider", LLM_PROVIDER))
    completed["llm_model"] = str(ai_fields.get("llm_model", LLM_MODEL))
    return completed


def load_classified_dataset() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load saved Phase 3 classifications. Does not call the LLM.
    Returns an empty frame and an unavailable status when the file is missing.
    """
    paths = _data_paths()
    relevance_path = paths["relevance"]
    classified_path = paths["classified"]

    eligible_count = 0
    uncertain_records: List[Dict[str, str]] = []
    if relevance_path.exists():
        relevance = _read_csv(relevance_path)
        eligible_count = int((relevance["relevance_label"] == "Relevant").sum())
        uncertain = relevance[relevance["relevance_label"] == "Uncertain"]
        for _, row in uncertain.iterrows():
            uncertain_records.append({
                "record_id": row["record_id"],
                "source": row["source"],
                "relevance_reason": row["relevance_reason"],
            })

    if not classified_path.exists():
        return pd.DataFrame(columns=OUTPUT_FIELDS), {
            "available": False,
            "eligible_count": eligible_count,
            "classified_count": 0,
            "successful_count": 0,
            "human_review_count": 0,
            "evidence_strength_distribution": {},
            "failure_stage_distribution": {},
            "uncertain_records": uncertain_records,
            "output_csv_path": str(classified_path),
        }

    frame = _read_csv(classified_path)
    if "needs_human_review" in frame.columns:
        frame["needs_human_review"] = frame["needs_human_review"].map(_as_bool)
    if "review_required" in frame.columns:
        frame["review_required"] = frame["review_required"].map(_as_bool)

    successful = frame[frame["classification_status"] == "classified"] if "classification_status" in frame.columns else frame
    human_review_count = int(frame["needs_human_review"].sum()) if "needs_human_review" in frame.columns else 0
    strength_distribution = {}
    stage_distribution = {}
    if not frame.empty and "evidence_strength" in frame.columns:
        strength_distribution = frame["evidence_strength"].value_counts().to_dict()
    if not successful.empty and "primary_failure_stage" in successful.columns:
        stage_distribution = successful["primary_failure_stage"].value_counts().to_dict()

    return frame, {
        "available": True,
        "eligible_count": eligible_count,
        "classified_count": int(len(frame)),
        "successful_count": int(len(successful)),
        "human_review_count": human_review_count,
        "evidence_strength_distribution": strength_distribution,
        "failure_stage_distribution": stage_distribution,
        "uncertain_records": uncertain_records,
        "output_csv_path": str(classified_path),
    }


def run_classification_pipeline() -> Dict[str, Any]:
    """
    Classify Relevant records that do not already have a saved successful result.
    Uncertain records are skipped. Immutable research files are only read.
    """
    paths = _data_paths()
    raw_hash = _file_sha256(paths["raw"])
    relevance_hash = _file_sha256(paths["relevance"])

    relevance = _read_csv(paths["relevance"])
    relevant = relevance[relevance["relevance_label"] == "Relevant"].copy()
    ordered_ids = relevant["record_id"].tolist()

    assembled: Dict[str, Dict[str, Any]] = {}
    if paths["classified"].exists():
        existing = _read_csv(paths["classified"])
        for _, saved in existing.iterrows():
            if saved["record_id"] in ordered_ids and saved.get("classification_status") == "classified":
                assembled[saved["record_id"]] = saved.to_dict()

    newly_classified = 0
    for _, source_row in relevant.iterrows():
        record_id = str(source_row["record_id"])
        if record_id in assembled:
            repaired = repair_classification_integrity(
                str(source_row["original_text"]),
                assembled[record_id],
            )
            repaired = apply_phase2_review_flag(repaired, _as_bool(source_row["review_required"]))
            assembled[record_id] = _completed_row(source_row, repaired)
            print(f"Reused saved classification for {record_id}", flush=True)
        else:
            print(f"Classifying {record_id}", flush=True)
            ai_fields = classify_evidence_record(
                record_id=record_id,
                source=str(source_row["source"]),
                date=str(source_row["date"]),
                original_text=str(source_row["original_text"]),
            )
            ai_fields = repair_classification_integrity(str(source_row["original_text"]), ai_fields)
            ai_fields = apply_phase2_review_flag(ai_fields, _as_bool(source_row["review_required"]))
            ai_fields["llm_provider"] = LLM_PROVIDER
            ai_fields["llm_model"] = LLM_MODEL
            assembled[record_id] = _completed_row(source_row, ai_fields)
            newly_classified += 1
            time.sleep(0.6)

        ordered_rows = [assembled[record] for record in ordered_ids if record in assembled]
        _write_classified(ordered_rows, paths["classified"])

    if _file_sha256(paths["raw"]) != raw_hash or _file_sha256(paths["relevance"]) != relevance_hash:
        raise RuntimeError("An immutable research file changed during classification.")

    _, metrics = load_classified_dataset()
    metrics["newly_classified"] = newly_classified
    return metrics
