"""
RecallScope — Dataset Ingestion & Validation Module
Phase 1: Dataset Ingestion and Validation

Provides reusable loading, schema verification, data quality auditing,
and health metrics calculation for raw research datasets.
Treats all loaded raw evidence as immutable.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List
import re
import warnings

# Suppress optional binary warnings from older conda C-extensions
warnings.filterwarnings("ignore", category=Warning)

import pandas as pd

# Required columns for the raw public evidence schema
REQUIRED_COLUMNS = [
    "record_id",
    "source",
    "date",
    "original_text",
    "source_url"
]

# Configurable review thresholds
SHORT_TEXT_CHAR_THRESHOLD = 30
SHORT_TEXT_WORD_THRESHOLD = 5

URL_PATTERN = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
    r"localhost|"  # localhost
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$", re.IGNORECASE
)


def validate_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Audit a raw research DataFrame against quality and integrity rules.
    Does NOT modify or drop any records.
    Returns a comprehensive validation report dictionary.
    """
    report: Dict[str, Any] = {
        "is_valid_schema": True,
        "schema_errors": [],
        "total_records": 0,
        "unique_record_ids": 0,
        "duplicate_record_ids_count": 0,
        "duplicate_record_ids": [],
        "duplicate_rows_count": 0,
        "duplicate_text_count": 0,
        "missing_record_ids": 0,
        "missing_sources": 0,
        "missing_dates": 0,
        "missing_original_texts": 0,
        "missing_source_urls": 0,
        "empty_or_whitespace_texts": 0,
        "malformed_urls_count": 0,
        "short_texts_count": 0,
        "flagged_records": [],
        "source_distribution": {},
        "status": "Dataset Valid",
        "status_message": "All schema and data integrity validations passed."
    }

    if df is None or not isinstance(df, pd.DataFrame):
        report["is_valid_schema"] = False
        report["status"] = "Dataset Requires Review"
        report["status_message"] = "Invalid data format or DataFrame is None."
        return report

    # 1. Schema check
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        report["is_valid_schema"] = False
        report["schema_errors"].append(f"Missing required columns: {', '.join(missing_cols)}")
        report["status"] = "Dataset Requires Review"
        report["status_message"] = f"Missing required column(s): {', '.join(missing_cols)}"
        return report

    report["total_records"] = len(df)
    if report["total_records"] == 0:
        report["status"] = "Dataset Requires Review"
        report["status_message"] = "Dataset is empty (0 rows)."
        return report

    # 2. Record IDs check
    # Check for null / blank record_ids
    null_ids = df["record_id"].isna() | (df["record_id"].astype(str).str.strip() == "")
    report["missing_record_ids"] = int(null_ids.sum())

    # Check uniqueness
    id_counts = df["record_id"].dropna().value_counts()
    dup_ids = id_counts[id_counts > 1].index.tolist()
    report["unique_record_ids"] = int(df["record_id"].nunique(dropna=True))
    report["duplicate_record_ids_count"] = len(dup_ids)
    report["duplicate_record_ids"] = dup_ids

    # 3. Completely duplicate rows
    report["duplicate_rows_count"] = int(df.duplicated().sum())

    # 4. Duplicate text check (different IDs sharing identical text)
    text_counts = df["original_text"].dropna().astype(str).str.strip().value_counts()
    dup_texts = text_counts[text_counts > 1]
    report["duplicate_text_count"] = len(dup_texts)

    # 5. Missing critical fields
    report["missing_sources"] = int(
        (df["source"].isna() | (df["source"].astype(str).str.strip() == "")).sum()
    )
    report["missing_dates"] = int(
        (df["date"].isna() | (df["date"].astype(str).str.strip() == "")).sum()
    )
    report["missing_original_texts"] = int(
        (df["original_text"].isna() | (df["original_text"].astype(str).str.strip() == "")).sum()
    )
    report["missing_source_urls"] = int(
        (df["source_url"].isna() | (df["source_url"].astype(str).str.strip() == "")).sum()
    )

    # 6. Flagged record audit (row-by-row inspection without altering data)
    flagged: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        rec_id = str(row.get("record_id", f"ROW_{idx}"))
        text = str(row.get("original_text", "")) if pd.notna(row.get("original_text")) else ""
        url = str(row.get("source_url", "")) if pd.notna(row.get("source_url")) else ""
        source = str(row.get("source", "")) if pd.notna(row.get("source")) else ""

        issues = []

        # Missing ID
        if pd.isna(row.get("record_id")) or str(row.get("record_id", "")).strip() == "":
            issues.append("Missing record_id")

        # Duplicate ID
        if rec_id in dup_ids:
            issues.append(f"Duplicate record_id '{rec_id}'")

        # Empty / whitespace-only text
        if text.strip() == "":
            issues.append("Empty or whitespace-only original_text")
            report["empty_or_whitespace_texts"] += 1
        else:
            # Extremely short text check (< 30 chars or < 5 words)
            word_count = len(text.strip().split())
            char_count = len(text.strip())
            if char_count < SHORT_TEXT_CHAR_THRESHOLD or word_count < SHORT_TEXT_WORD_THRESHOLD:
                issues.append(f"Extremely short text ({char_count} chars, {word_count} words)")
                report["short_texts_count"] += 1

        # Missing or malformed URL check
        if url.strip() == "":
            issues.append("Missing source_url")
        elif not URL_PATTERN.match(url.strip()):
            issues.append(f"Malformed source_url format: {url}")
            report["malformed_urls_count"] += 1

        # Missing source
        if source.strip() == "":
            issues.append("Missing source name")

        if issues:
            flagged.append({
                "record_id": rec_id,
                "row_index": idx,
                "issues": issues,
                "original_text_preview": text[:80] + ("..." if len(text) > 80 else "")
            })

    report["flagged_records"] = flagged

    # 7. Source distribution
    if "source" in df.columns:
        source_counts = df["source"].fillna("Unknown").value_counts()
        report["source_distribution"] = source_counts.to_dict()

    # 8. Overall status decision
    critical_errors = (
        report["missing_record_ids"] > 0
        or report["duplicate_record_ids_count"] > 0
        or report["missing_original_texts"] > 0
        or report["missing_sources"] > 0
        or report["missing_source_urls"] > 0
        or report["empty_or_whitespace_texts"] > 0
    )

    if critical_errors or len(flagged) > 0:
        report["status"] = "Dataset Requires Review"
        reasons = []
        if report["missing_record_ids"] > 0:
            reasons.append(f"{report['missing_record_ids']} missing IDs")
        if report["duplicate_record_ids_count"] > 0:
            reasons.append(f"{report['duplicate_record_ids_count']} duplicate IDs")
        if report["missing_original_texts"] > 0:
            reasons.append(f"{report['missing_original_texts']} missing texts")
        if report["short_texts_count"] > 0:
            reasons.append(f"{report['short_texts_count']} extremely short records")
        if report["malformed_urls_count"] > 0:
            reasons.append(f"{report['malformed_urls_count']} malformed URLs")
        report["status_message"] = f"Review recommended: {', '.join(reasons)}."
    else:
        report["status"] = "Dataset Valid"
        report["status_message"] = (
            f"Dataset validated successfully ({report['total_records']} records, "
            f"{report['unique_record_ids']} unique IDs, {len(report['source_distribution'])} sources)."
        )

    return report


def load_raw_dataset(csv_path: str = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Safely load and validate the raw public research dataset from disk.
    Ensures the original file on disk is read-only and never modified.

    Returns:
        (df, validation_report): Tuple of loaded DataFrame and validation results dict.
    """
    if csv_path is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        primary_csv = base_dir / "data" / "public_evidence_raw.csv"
        batch1_csv = base_dir / "data" / "public_evidence_raw_batch1.csv"
        csv_path = primary_csv if primary_csv.exists() else batch1_csv
    else:
        csv_path = Path(csv_path)

    if not csv_path.exists():
        err_report = {
            "is_valid_schema": False,
            "status": "Dataset Missing",
            "status_message": f"Raw evidence file not found at: {csv_path}",
            "total_records": 0,
            "unique_record_ids": 0,
            "duplicate_record_ids_count": 0,
            "missing_critical_fields": 0,
            "flagged_records": [],
            "source_distribution": {}
        }
        return pd.DataFrame(), err_report

    try:
        # Read CSV with UTF-8 encoding; do not alter raw file
        df = pd.read_csv(csv_path, encoding="utf-8", dtype=str)
    except Exception as e:
        err_report = {
            "is_valid_schema": False,
            "status": "Dataset Unreadable",
            "status_message": f"Error reading CSV file: {str(e)}",
            "total_records": 0,
            "unique_record_ids": 0,
            "duplicate_record_ids_count": 0,
            "missing_critical_fields": 0,
            "flagged_records": [],
            "source_distribution": {}
        }
        return pd.DataFrame(), err_report

    # Perform validation
    report = validate_dataset(df)
    return df, report
