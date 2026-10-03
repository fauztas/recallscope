"""
Phase 3 runner and validation.

Classifies Relevant records with Groq and checks that the immutable research
files and record traceability are unchanged. Does not print the API key.
"""

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.classify_pipeline import load_classified_dataset, run_classification_pipeline
from app.utils.data_loader import load_raw_dataset
from app.utils.llm_helper import FAILURE_STAGES, SIGNALS, unknown_value_self_check
from app.utils.relevance_filter import load_relevance_dataset


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_phase3() -> bool:
    """Run the requested Phase 3 checks. Returns True when every check passes."""
    root = project_root
    raw_path = root / "data" / "public_evidence_raw.csv"
    relevance_path = root / "data" / "public_evidence_relevance.csv"
    classified_path = root / "data" / "public_evidence_classified.csv"

    expected_raw_hash = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
    expected_relevance_hash = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"
    checks = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append(passed)
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    raw_hash = _sha256(raw_path)
    relevance_hash = _sha256(relevance_path)
    record("Raw CSV unchanged", raw_hash == expected_raw_hash, raw_hash)
    record("Relevance CSV unchanged", relevance_hash == expected_relevance_hash, relevance_hash)
    record("Unknown values accepted", unknown_value_self_check(), "validator accepts Unknown")

    raw_df, raw_report = load_raw_dataset()
    relevance_df, relevance_metrics = load_relevance_dataset()
    classified_df, classified_metrics = load_classified_dataset()

    record(
        "Phase 1 still loads",
        raw_report.get("is_valid_schema") and len(raw_df) == 24,
        f"{len(raw_df)} raw records, status={raw_report.get('status')}",
    )
    record(
        "Phase 2 metrics unchanged",
        relevance_metrics["total_records"] == 24
        and relevance_metrics["relevant_count"] == 22
        and relevance_metrics["irrelevant_count"] == 0
        and relevance_metrics["uncertain_count"] == 2
        and relevance_metrics["review_required_count"] == 3,
        (
            f"total={relevance_metrics['total_records']}, relevant={relevance_metrics['relevant_count']}, "
            f"irrelevant={relevance_metrics['irrelevant_count']}, uncertain={relevance_metrics['uncertain_count']}, "
            f"review={relevance_metrics['review_required_count']}"
        ),
    )

    relevant_ids = set(relevance_df.loc[relevance_df["relevance_label"] == "Relevant", "record_id"])
    uncertain_ids = set(relevance_df.loc[relevance_df["relevance_label"] == "Uncertain", "record_id"])
    classified_ids = set(classified_df["record_id"]) if not classified_df.empty else set()
    raw_ids = set(raw_df["record_id"])

    record("Classified file exists", classified_path.exists() and classified_metrics.get("available"), str(classified_path))
    record("Only relevant records were classified", classified_ids == relevant_ids, f"{len(classified_ids)} classified IDs")
    record("Uncertain records were not auto-classified", uncertain_ids.isdisjoint(classified_ids), ", ".join(sorted(uncertain_ids)))
    record("No invented record IDs", classified_ids.issubset(raw_ids), f"{len(classified_ids)} IDs are present in the raw file")

    text_matches = True
    review_021 = False
    stages_ok = True
    for _, row in classified_df.iterrows():
        raw_match = raw_df.loc[raw_df["record_id"] == row["record_id"]]
        relevance_match = relevance_df.loc[relevance_df["record_id"] == row["record_id"]]
        if raw_match.empty or relevance_match.empty:
            text_matches = False
            continue
        raw_row = raw_match.iloc[0]
        relevance_row = relevance_match.iloc[0]
        if str(row["original_text"]) != str(raw_row["original_text"]):
            text_matches = False
        if str(row["source"]) != str(raw_row["source"]) or str(row["source_url"]) != str(raw_row["source_url"]):
            text_matches = False
        if str(row["relevance_label"]) != "Relevant":
            text_matches = False
        if str(row["relevance_reason"]) != str(relevance_row["relevance_reason"]):
            text_matches = False
        if row["record_id"] == "REC_021":
            review_021 = bool(row["review_required"]) and str(relevance_row["relevance_label"]) == "Relevant"
        stage = str(row["primary_failure_stage"])
        secondary = str(row["secondary_failure_stage"])
        if row["classification_status"] == "classified" and stage not in FAILURE_STAGES:
            stages_ok = False
        if secondary not in FAILURE_STAGES + ["None", "Unknown"]:
            stages_ok = False
        for signal_field in (
            "candidate_overload_signal",
            "recognition_difficulty_signal",
            "query_difficulty_signal",
            "manual_scroll_signal",
        ):
            if str(row[signal_field]) not in SIGNALS:
                stages_ok = False

    record("Record text and IDs stay traceable", text_matches, "original text, source, URL, and relevance reason match")
    record("REC_021 remains Relevant + review required", review_021, "review_required preserved")
    record("Failure stages and signals are valid", stages_ok, "schema values checked")
    record(
        "Classified output is a new file",
        classified_path.name == "public_evidence_classified.csv" and classified_path != raw_path and classified_path != relevance_path,
        classified_path.name,
    )

    print(
        "Summary: "
        f"eligible={classified_metrics.get('eligible_count')}, "
        f"successful={classified_metrics.get('successful_count')}, "
        f"human_review={classified_metrics.get('human_review_count')}"
    )
    return all(checks)


if __name__ == "__main__":
    summary = run_classification_pipeline()
    print(
        "Pipeline: "
        f"newly_classified={summary.get('newly_classified')}, "
        f"successful={summary.get('successful_count')}, "
        f"human_review={summary.get('human_review_count')}"
    )
    ok = validate_phase3()
    if not ok:
        sys.exit(1)
