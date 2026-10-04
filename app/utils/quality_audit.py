"""
RecallScope — Phase 8 Quality & Integrity audit

Reads the saved research files and checks the Discovery Engine paths.
Running this module does not rewrite evidence, does not call Groq,
and does not print an API key.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
from unittest.mock import patch

import pandas as pd

from app.utils.ask_evidence import ask_evidence, retrieve_records
from app.utils.challenge_insight import challenge_insight, retrieve_for_challenge
from app.utils.data_loader import REQUIRED_COLUMNS
from app.utils.discovery_data import (
    INTERIM_CORPUS_LABEL,
    load_discovery_records,
    load_research_analysis,
    project_root,
)
from app.utils.llm_helper import ClassificationError

APPROVED_HASHES = {
    "public_evidence_raw.csv": "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8",
    "public_evidence_relevance.csv": "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158",
    "public_evidence_classified.csv": "1d94edc9028ca519e22879f910a20f91829d4dfe7afffc689388cb07f0844c63",
    "research_analysis.json": "9837848c0787cfda5533d3bea2f7b6254f310b22f4335cf82e599de0a022e7c6",
}

DOES_NOT_PROVE = [
    "A completed audit does not make this interim corpus representative of Google Photos users.",
    "Matching checksums and traceable excerpts do not turn corpus frequencies into population prevalence.",
    "This audit does not select a final product problem.",
    "This audit does not validate a product solution.",
    "Visible human-review flags are unresolved. The audit does not close them.",
    "Public posts still cannot show everything a person remembered before they searched. Interviews remain necessary for that question.",
]

DANGER_PATTERNS = (
    (re.compile(r"\ball google photos users\b"), "all Google Photos users"),
    (re.compile(r"\ball users\b"), "all users"),
    (re.compile(r"\bmost google photos users\b"), "most Google Photos users"),
    (re.compile(r"\bpopulation prevalence\b"), "population prevalence"),
    (re.compile(r"\b(the main cause|main cause|the main reason|the main problem)\b"), "main-cause wording"),
    (re.compile(r"\bstatistically (certain|significant|proven)\b"), "statistical certainty"),
    (re.compile(r"\bproven\b"), "proven"),
)
SAFE_CONTEXT = re.compile(
    r"\b(not|no|never|cannot|can't|don't|doesn't|isn't|aren't|without)\b"
    r"|blocks any conclusion|does not establish|do not establish|do not show|not proof"
)
SKIP_TEXT_KEYS = {"original_text", "excerpt", "evidence_excerpt", "source_url", "example_excerpts"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False).fillna("")


def _check(check_id: str, name: str, status: str, explanation: str, details: Sequence[str], record_ids: Sequence[str] = ()) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "name": name,
        "status": status,
        "explanation": explanation,
        "details": list(details),
        "record_ids": list(record_ids),
    }


def _excerpt_matches(excerpt: str, original: str) -> bool:
    compact = " ".join(str(original).split())
    body = str(excerpt).strip()
    if body.endswith("…"):
        body = body[:-1].rstrip()
    elif body.endswith("..."):
        body = body[:-3].rstrip()
    return bool(body) and body in compact


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _check_raw(data_dir: Path) -> Dict[str, Any]:
    details = []
    record_ids: List[str] = []
    raw_path = data_dir / "public_evidence_raw.csv"
    if not raw_path.exists():
        return _check("1", "Raw data integrity", "FAIL", "The raw dataset file is missing.", [str(raw_path)], [])
    raw = _read_csv(raw_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        details.append("Missing columns: " + ", ".join(missing))
    duplicate_ids = raw["record_id"][raw["record_id"].duplicated()].tolist() if "record_id" in raw.columns else []
    if duplicate_ids:
        details.append("Duplicate record IDs: " + ", ".join(duplicate_ids))
        record_ids.extend(duplicate_ids)
    full_duplicates = int(raw.duplicated().sum()) if not missing else 0
    if full_duplicates:
        details.append(f"Fully duplicated rows: {full_duplicates}.")
    empty_text = []
    empty_urls = []
    if not missing:
        for _, row in raw.iterrows():
            if not str(row["original_text"]).strip():
                empty_text.append(row["record_id"])
            if not str(row["source_url"]).startswith("http"):
                empty_urls.append(row["record_id"])
    if empty_text:
        details.append("Records with empty original text: " + ", ".join(empty_text))
        record_ids.extend(empty_text)
    if empty_urls:
        details.append("Records with a missing or non-http source URL: " + ", ".join(empty_urls))
        record_ids.extend(empty_urls)
    for name, expected in APPROVED_HASHES.items():
        path = data_dir / name
        if not path.exists():
            details.append(f"{name} is missing.")
            continue
        actual = _sha256(path)
        if actual == expected:
            details.append(f"{name} matches the approved checksum.")
        else:
            details.append(f"{name} does not match the approved checksum. It was not repaired.")
    hash_failures = [line for line in details if "does not match" in line or line.endswith("is missing.")]
    structural_failures = bool(missing or duplicate_ids or full_duplicates or empty_text or empty_urls or hash_failures)
    status = "FAIL" if structural_failures else "PASS"
    explanation = (
        "The raw file, its required columns, record IDs, original text, and source URLs were compared with the saved files. "
        "Approved checksums were used. Nothing was rewritten."
    )
    return _check("1", "Raw data integrity", status, explanation, details, record_ids)


def _check_counts(data_dir: Path, records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    raw = _read_csv(data_dir / "public_evidence_raw.csv")
    relevance = _read_csv(data_dir / "public_evidence_relevance.csv")
    classified = _read_csv(data_dir / "public_evidence_classified.csv")
    raw_ids = set(raw["record_id"])
    relevance_ids = set(relevance["record_id"])
    classified_ids = set(classified["record_id"])
    labels = relevance["relevance_label"].value_counts().to_dict()
    relevant_ids = set(relevance.loc[relevance["relevance_label"] == "Relevant", "record_id"])
    uncertain_ids = set(relevance.loc[relevance["relevance_label"] == "Uncertain", "record_id"])
    review_ids = [row["record_id"] for _, row in classified.iterrows() if _as_bool(row["needs_human_review"])]
    joined_classified = {record["record_id"] for record in records if record.get("classified")}
    analysis_input = analysis.get("input", {})
    stage_sum = sum(int(stage.get("record_count", 0)) for stage in analysis.get("failure_stages", []))
    problems = []
    if raw_ids != relevance_ids:
        problems.append("Raw record IDs and relevance record IDs are not the same set.")
    if classified_ids != relevant_ids:
        problems.append("Classified record IDs are not exactly the Relevant record IDs.")
    if classified_ids & uncertain_ids:
        problems.append("Uncertain records appear in the classified file: " + ", ".join(sorted(classified_ids & uncertain_ids)))
    if joined_classified != classified_ids:
        problems.append("The Discovery join does not match the classified file.")
    if int(analysis_input.get("raw_record_count", -1)) != len(raw):
        problems.append("The analysis raw count does not match the raw file.")
    if int(analysis_input.get("classified_record_count", -1)) != len(classified):
        problems.append("The analysis classified count does not match the classified file.")
    if set(analysis_input.get("uncertain_record_ids", [])) != uncertain_ids:
        problems.append("The analysis uncertain IDs do not match the relevance file.")
    if int(analysis_input.get("human_review_count", -1)) != len(review_ids):
        problems.append("The analysis human-review count does not match the classified file.")
    if stage_sum != len(classified):
        problems.append("Failure-stage counts do not add up to the classified records.")
    details = [
        f"Raw records in the file: {len(raw)}.",
        f"Relevant: {labels.get('Relevant', 0)}. Uncertain: {labels.get('Uncertain', 0)}. Irrelevant: {labels.get('Irrelevant', 0)}.",
        f"AI-classified records: {len(classified)}.",
        f"Classified records with needs_human_review: {len(review_ids)}.",
        "These counts were read from the saved files and compared with each other.",
    ]
    status = "FAIL" if problems else "PASS"
    details.extend(problems)
    return _check(
        "2",
        "Pipeline counts",
        status,
        "Raw, relevance, classification, human-review, and analysis counts were compared. The comparison uses the saved files.",
        details,
        sorted(review_ids) if problems else [],
    )


def _check_traceability(records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    lookup = {record["record_id"]: record for record in records}
    missing = []
    for record in records:
        if not record.get("classified"):
            continue
        if not record.get("record_id") or not str(record.get("original_text", "")).strip():
            missing.append(record.get("record_id", ""))
        if not str(record.get("source", "")).strip() or not str(record.get("source_url", "")).startswith("http"):
            missing.append(record["record_id"])
    referenced = []
    for card in analysis.get("pattern_cards", []):
        referenced.extend(card.get("supporting_record_ids", []))
    for candidate in analysis.get("candidate_problem_areas", []):
        referenced.extend(candidate.get("supporting_record_ids", []))
    for challenge in analysis.get("contradictions_and_evidence_gaps", {}).get("challenges", []):
        referenced.extend(challenge.get("supporting_record_ids", []))
    unknown_refs = sorted({record_id for record_id in referenced if record_id not in lookup})
    ask_retrieval = retrieve_records("What evidence do we have of manual scrolling?", records)
    challenge_retrieval = retrieve_for_challenge(
        "Recognition difficulty is the main reason people fail to retrieve remembered photos.",
        records,
    )
    ask_ids = [record["record_id"] for record in ask_retrieval["selected_records"]]
    challenge_ids = [record["record_id"] for record in challenge_retrieval["selected_records"]]
    bad_ask = [record_id for record_id in ask_ids if record_id not in lookup]
    bad_challenge = [record_id for record_id in challenge_ids if record_id not in lookup]
    uncertain = set(challenge_retrieval["uncertain_record_ids"])
    leaked = sorted(set(challenge_ids) & uncertain)
    details = [
        f"Classified records checked for id, original text, source, and source URL: {sum(1 for record in records if record.get('classified'))}.",
        f"Phase 4 pattern, candidate, and contradiction IDs checked: {len(set(referenced))}.",
        f"Ask the Evidence retrieval sample returned: {', '.join(ask_ids) or 'none'}.",
        f"Challenge an Insight retrieval sample returned: {', '.join(challenge_ids) or 'none'}.",
    ]
    problems = []
    if missing:
        problems.append("Some classified records are missing text, source, or a source URL.")
    if unknown_refs:
        problems.append("Phase 4 references IDs that are not in the raw file: " + ", ".join(unknown_refs))
    if bad_ask or bad_challenge:
        problems.append("A retrieval sample returned an ID that is not in the saved corpus.")
    if leaked:
        problems.append("Uncertain records were included in automatic challenge retrieval: " + ", ".join(leaked))
    if not ask_ids or not challenge_ids:
        problems.append("A retrieval sample returned no saved records.")
    status = "FAIL" if problems else "PASS"
    details.extend(problems)
    return _check(
        "3",
        "Traceability",
        status,
        "Classified records, Phase 4 references, and retrieval samples were traced to saved record IDs. Groq was not called.",
        details,
        sorted(set(missing + unknown_refs + bad_ask + bad_challenge + leaked)),
    )


def _check_verbatim(data_dir: Path, records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    lookup = {record["record_id"]: record for record in records}
    raw = _read_csv(data_dir / "public_evidence_raw.csv")
    relevance = _read_csv(data_dir / "public_evidence_relevance.csv")
    classified = _read_csv(data_dir / "public_evidence_classified.csv")
    raw_text = {row["record_id"]: row["original_text"] for _, row in raw.iterrows()}
    problems = []
    affected = []
    for _, row in relevance.iterrows():
        original = raw_text.get(row["record_id"], "")
        if row["original_text"] != original or not _excerpt_matches(row["evidence_excerpt"], original):
            problems.append(f"{row['record_id']} relevance excerpt or stored text does not match the raw post.")
            affected.append(row["record_id"])
    for _, row in classified.iterrows():
        if row["original_text"] != raw_text.get(row["record_id"], None):
            problems.append(f"{row['record_id']} classified original text does not match the raw post.")
            affected.append(row["record_id"])
    excerpt_count = 0
    for card in analysis.get("pattern_cards", []):
        for example in card.get("example_excerpts", []):
            excerpt_count += 1
            record = lookup.get(example.get("record_id"))
            if record is None or not _excerpt_matches(example.get("excerpt", ""), record["original_text"]):
                problems.append(f"{example.get('record_id')} pattern excerpt is not contained in the saved post.")
                affected.append(str(example.get("record_id")))
    for row in analysis.get("trace_index", []):
        if row.get("original_text") != raw_text.get(row.get("record_id")):
            problems.append(f"{row.get('record_id')} analysis trace text does not match the raw post.")
            affected.append(str(row.get("record_id")))
    status = "FAIL" if problems else "PASS"
    details = [
        f"Relevance excerpts checked: {len(relevance)}.",
        f"Classified original texts checked: {len(classified)}.",
        f"Pattern-card excerpts checked: {excerpt_count}.",
        "Displayed excerpts are accepted only when the text, without a trailing ellipsis, is inside the saved post.",
    ]
    details.extend(problems[:12])
    return _check(
        "4",
        "Verbatim evidence integrity",
        status,
        "Saved excerpts and stored original text were matched back to the raw posts. No quotation was rewritten.",
        details,
        sorted(set(affected)),
    )


def _check_uncertainty(data_dir: Path, records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    classified = _read_csv(data_dir / "public_evidence_classified.csv")
    relevance = _read_csv(data_dir / "public_evidence_relevance.csv")
    uncertain_ids = relevance.loc[relevance["relevance_label"] == "Uncertain", "record_id"].tolist()
    classified_ids = set(classified["record_id"])
    leaked = [record_id for record_id in uncertain_ids if record_id in classified_ids]
    unknown_outcomes = classified.loc[classified["retrieval_outcome"] == "Unknown", "record_id"].tolist()
    f8_ids = classified.loc[classified["primary_failure_stage"].str.startswith("F8"), "record_id"].tolist()
    review_ids = [row["record_id"] for _, row in classified.iterrows() if _as_bool(row["needs_human_review"])]
    allowed_signals = {"Yes", "No", "Unknown", ""}
    signal_problems = []
    for column in (
        "candidate_overload_signal",
        "recognition_difficulty_signal",
        "query_difficulty_signal",
        "manual_scroll_signal",
    ):
        unexpected = sorted(set(classified[column]) - allowed_signals)
        if unexpected:
            signal_problems.append(f"{column} has values outside Yes, No, and Unknown: {unexpected}")
    view_text = (project_root() / "app" / "utils" / "discovery_view.py").read_text(encoding="utf-8")
    challenge_view = (project_root() / "app" / "utils" / "challenge_insight_view.py").read_text(encoding="utf-8")
    visible = "Needs human review" in view_text and "flagged for human review" in challenge_view
    unmarked = []
    for record in records:
        if record.get("needs_human_review") and not record.get("classified"):
            unmarked.append(record["record_id"])
    problems = []
    if leaked:
        problems.append("Uncertain records were classified: " + ", ".join(leaked))
    if signal_problems:
        problems.extend(signal_problems)
    if not visible:
        problems.append("Human-review flags are not shown in the Discovery views.")
    if unmarked:
        problems.append("Human-review flags exist on unclassified records: " + ", ".join(unmarked))
    details = [
        f"Phase 2 Uncertain records outside classification: {', '.join(uncertain_ids) or 'none'}.",
        f"Retrieval outcome Unknown: {len(unknown_outcomes)} records.",
        f"Primary stage F8 — Unknown / Insufficient Evidence: {len(f8_ids)} records.",
        f"needs_human_review is true: {len(review_ids)} records.",
        "Unknown remains a stored value. It was not rewritten to No or to a specific failure stage by this audit.",
    ]
    if problems:
        return _check("5", "Unknown and uncertainty preservation", "FAIL", "Uncertainty was not preserved.", details + problems, leaked + unmarked)
    return _check(
        "5",
        "Unknown and uncertainty preservation",
        "WARNING",
        "Unknown values, Uncertain records, and human-review flags are still present and visible. Their volume is a real limit on what this corpus can support.",
        details,
        sorted(set(unknown_outcomes + f8_ids + review_ids)),
    )


def _sentences(text: str) -> Iterable[str]:
    for part in re.split(r"(?<=[.!?])\s+", text):
        sentence = " ".join(part.split())
        if sentence:
            yield sentence


def _walk_findings(value: Any, key: str, found: List[str]) -> None:
    if key in SKIP_TEXT_KEYS:
        return
    if isinstance(value, dict):
        for child_key, child in value.items():
            _walk_findings(child, child_key, found)
    elif isinstance(value, list):
        for child in value:
            _walk_findings(child, key, found)
    elif isinstance(value, str):
        found.append(value)


def _overclaim_sentences(texts: Sequence[str]) -> List[str]:
    flagged = []
    for text in texts:
        for sentence in _sentences(text):
            lowered = sentence.lower()
            if SAFE_CONTEXT.search(lowered):
                continue
            for pattern, label in DANGER_PATTERNS:
                if pattern.search(lowered):
                    flagged.append(f"{label}: {sentence}")
                    break
    return flagged


def _check_claims(analysis: Dict[str, Any]) -> Dict[str, Any]:
    finding_texts: List[str] = []
    _walk_findings(analysis, "", finding_texts)
    surfaces = [
        project_root() / "app" / "utils" / "discovery_view.py",
        project_root() / "app" / "utils" / "primary_research_view.py",
        project_root() / "app" / "utils" / "ask_evidence_view.py",
        project_root() / "app" / "utils" / "challenge_insight_view.py",
        project_root() / "app" / "main.py",
        project_root() / "README.md",
    ]
    page_texts = [path.read_text(encoding="utf-8") for path in surfaces]
    flagged = _overclaim_sentences(finding_texts + page_texts)
    details = [
        "Limitation sentences that deny a population claim, a main cause, or proof were not flagged.",
        "Original posts and verbatim excerpts were not scanned, because those are source quotations.",
        f"Sentences flagged for review: {len(flagged)}.",
    ]
    if flagged:
        return _check(
            "6",
            "Claim safety",
            "WARNING",
            "Some evaluator-facing sentences use strong claim language without a nearby limitation. They need review. They were not deleted.",
            details + flagged[:8],
        )
    return _check(
        "6",
        "Claim safety",
        "PASS",
        "Saved findings and Discovery pages were scanned. Affirmative population, main-cause, and certainty claims were not found. Limitation statements were left in place.",
        details,
    )


def _check_contradictions(records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    challenges = analysis.get("contradictions_and_evidence_gaps", {}).get("challenges", [])
    view_text = (project_root() / "app" / "utils" / "discovery_view.py").read_text(encoding="utf-8")
    visible = "Contradictions and gaps" in view_text and "contradictions_and_evidence_gaps" in view_text
    insight = "Recognition difficulty is the main reason people fail to retrieve remembered photos."
    fake_answer = json.dumps({
        "assessment": "Supported by current evidence",
        "assessment_reason": "This is the main reason.",
        "supporting": [{"record_id": "REC_999", "reason": "A manufactured quotation that is not in the post."}],
        "challenging": [],
        "evidence_gaps": "None.",
        "next_research_questions": ["What do people try after a search misses?"],
    })
    with patch("app.utils.challenge_insight.is_groq_configured", return_value=True), patch(
        "app.utils.challenge_insight._call_model",
        return_value=fake_answer,
    ):
        result = challenge_insight(insight, records, analysis)
    challenging_ids = [card["record_id"] for card in result.get("challenging", [])]
    supporting_ids = [card["record_id"] for card in result.get("supporting", [])]
    problems = []
    if len(challenges) < 1:
        problems.append("The saved analysis has no contradiction or evidence-gap entries.")
    if not visible:
        problems.append("The Discovery Engine does not expose the contradictions section.")
    if not challenging_ids:
        problems.append("Challenge an Insight did not keep a challenging side for the recognition claim.")
    if "REC_999" in supporting_ids or "REC_999" in challenging_ids:
        problems.append("A manufactured record ID was kept.")
    if result.get("assessment") == "Supported by current evidence":
        problems.append("The recognition main-reason claim was treated as supported.")
    details = [
        f"Saved contradiction and evidence-gap notes: {len(challenges)}.",
        f"Challenge sample assessment: {result.get('assessment')}.",
        f"Supporting IDs in the sample: {', '.join(supporting_ids) or 'none'}.",
        f"Challenging IDs in the sample: {', '.join(challenging_ids) or 'none'}.",
        "The sample used a stand-in model response so Groq was not called.",
    ]
    status = "FAIL" if problems else "PASS"
    details.extend(problems)
    return _check(
        "7",
        "Contradiction preservation",
        status,
        "Phase 4 contradictions remain in the Discovery Engine, and Challenge an Insight can show evidence that weakens a claim.",
        details,
        challenging_ids,
    )


def _check_secrets() -> Dict[str, Any]:
    root = project_root()
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    example = (root / ".env.example").read_text(encoding="utf-8")
    ignored = any(line.strip() == ".env" for line in gitignore.splitlines())
    placeholder_ok = "GROQ_API_KEY=your_groq_api_key_here" in example and "gsk_" not in example
    secret_hits = []
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "env"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts) or path.name == ".env":
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".csv", ".txt", ".example"} and path.name != ".env.example":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"gsk_[A-Za-z0-9_\-]+", text):
            secret_hits.append(str(path.relative_to(root)))
    problems = []
    if not ignored:
        problems.append(".env is not listed in .gitignore.")
    if not placeholder_ok:
        problems.append(".env.example does not contain only the placeholder Groq key.")
    if secret_hits:
        problems.append("A secret-like token was found in: " + ", ".join(secret_hits))
    details = [
        ".env is gitignored." if ignored else ".env is not gitignored.",
        ".env.example uses the placeholder key." if placeholder_ok else ".env.example failed the placeholder check.",
        "The real key was not printed. The .env file was not opened for this report.",
        f"Files with a secret-like token: {len(secret_hits)}.",
    ]
    status = "FAIL" if problems else "PASS"
    details.extend(problems)
    return _check(
        "8",
        "API and secret safety",
        status,
        "Git ignore, the example environment file, and project text files were checked for a real Groq key.",
        details,
    )


def _no_secret(payload: Dict[str, Any]) -> bool:
    return "gsk_" not in json.dumps(payload)


def _check_failure_handling(records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    problems = []
    empty_question = ask_evidence("", records, analysis)
    if empty_question.get("called_model") or empty_question.get("supporting_record_ids"):
        problems.append("An empty question produced an evidence answer.")
    empty_insight = challenge_insight("", records, analysis)
    if empty_insight.get("called_model") or empty_insight.get("assessment") != "Insufficient evidence":
        problems.append("An empty insight produced a substantive assessment.")

    with patch("app.utils.ask_evidence._call_model", side_effect=AssertionError("network")), patch(
        "app.utils.challenge_insight._call_model",
        side_effect=AssertionError("network"),
    ):
        thin_question = ask_evidence("zzzz quantum lattice subscription price", records, analysis)
        thin_insight = challenge_insight("zzzz quantum lattice hypothesis", records, analysis)
    if thin_question.get("called_model") or thin_question.get("supporting_record_ids"):
        problems.append("A question with no saved match invented supporting records.")
    if not thin_question.get("evidence_is_insufficient"):
        problems.append("A question with no saved match was not marked insufficient.")
    if thin_insight.get("called_model") or thin_insight.get("supporting"):
        problems.append("An insight with no saved match invented supporting records.")
    if thin_insight.get("assessment") != "Insufficient evidence":
        problems.append("An insight with no saved match was not marked insufficient.")

    with patch("app.utils.ask_evidence.is_groq_configured", return_value=False), patch(
        "app.utils.ask_evidence._call_model",
        side_effect=AssertionError("network"),
    ):
        missing_key = ask_evidence("What evidence do we have of manual scrolling?", records, analysis)
    if missing_key.get("called_model") or missing_key.get("supporting_excerpts") or not missing_key.get("error"):
        problems.append("A missing Groq key did not stop Ask the Evidence cleanly.")
    if not _no_secret(missing_key):
        problems.append("Ask the Evidence included secret-like text in an error state.")

    with patch("app.utils.challenge_insight.is_groq_configured", return_value=False), patch(
        "app.utils.challenge_insight._call_model",
        side_effect=AssertionError("network"),
    ):
        missing_challenge = challenge_insight(
            "Manual scrolling is a common workaround after search does not help.",
            records,
            analysis,
        )
    if missing_challenge.get("called_model") or missing_challenge.get("supporting") or not missing_challenge.get("error"):
        problems.append("A missing Groq key did not stop Challenge an Insight cleanly.")

    with patch("app.utils.ask_evidence.is_groq_configured", return_value=True), patch(
        "app.utils.ask_evidence._call_model",
        side_effect=ClassificationError("request failed"),
    ):
        failed = ask_evidence("What evidence do we have of manual scrolling?", records, analysis)
    if failed.get("status") != "error" or failed.get("supporting_excerpts"):
        problems.append("A failed Groq request fabricated supporting excerpts.")
    if not _no_secret(failed):
        problems.append("A failed request leaked secret-like text.")

    with patch("app.utils.ask_evidence.is_groq_configured", return_value=True), patch(
        "app.utils.ask_evidence._call_model",
        return_value="this is not json",
    ):
        malformed = ask_evidence("What evidence do we have of manual scrolling?", records, analysis)
    if malformed.get("supporting_record_ids") or malformed.get("status") != "error":
        problems.append("Malformed model output was treated as evidence.")

    fake = json.dumps({
        "short_answer": "Yes.",
        "evidence_summary": "Invented.",
        "supporting_record_ids": ["REC_999", "REC_001"],
        "limiting_record_ids": ["REC_FAKE"],
        "evidence_is_mixed": False,
        "evidence_is_insufficient": False,
        "evidence_strength_note": "High",
    })
    with patch("app.utils.ask_evidence.is_groq_configured", return_value=True), patch(
        "app.utils.ask_evidence._call_model",
        return_value=fake,
    ):
        grounded = ask_evidence("What evidence do we have of manual scrolling?", records, analysis)
    if "REC_999" in grounded.get("supporting_record_ids", []) or "REC_FAKE" in grounded.get("limiting_record_ids", []):
        problems.append("Ask the Evidence kept a record ID that is not in the retrieved set.")
    lookup = {record["record_id"]: record for record in records}
    for card in grounded.get("supporting_excerpts", []) + grounded.get("limiting_excerpts", []):
        source = lookup.get(card["record_id"])
        if source is None or not _excerpt_matches(card["excerpt"], source["original_text"]):
            problems.append(f"Ask excerpt for {card.get('record_id')} is not verbatim.")

    details = [
        "Empty question, empty insight, thin retrieval, missing key, request failure, malformed output, and a fabricated record ID were exercised with stand-ins.",
        "Groq was not contacted.",
        f"Missing-key Ask status: {missing_key.get('status')}.",
        f"Malformed Ask status: {malformed.get('status')}.",
        f"Grounded Ask kept IDs: {', '.join(grounded.get('supporting_record_ids', [])) or 'none'}.",
    ]
    status = "FAIL" if problems else "PASS"
    details.extend(problems)
    return _check(
        "9",
        "Failure handling",
        status,
        "The tools were checked for honest insufficient-evidence and error states. They were not allowed to invent a record.",
        details,
    )


def _check_limitations(records: Sequence[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
    view_text = (project_root() / "app" / "utils" / "discovery_view.py").read_text(encoding="utf-8").lower()
    limitation_text = " ".join(analysis.get("research_limitations", [])).lower()
    disclaimer = str(analysis.get("disclaimer", "")).lower()
    visible = " ".join([view_text, limitation_text, disclaimer, INTERIM_CORPUS_LABEL.lower()])
    required = {
        "interim corpus label": "interim" in visible,
        "not representative of all Google Photos users": "not representative of all google photos users" in visible or "not all google photos users" in visible,
        "corpus frequencies are not population prevalence": "not population prevalence" in visible or "not prevalence" in visible,
        "AI classifications are interpretations": "interpretation" in visible,
        "human review remains visible": "human review" in visible,
        "public posts do not show all pre-search memory": "remembered before" in visible,
        "interviews are still required": "interview" in visible,
    }
    missing = [name for name, present in required.items() if not present]
    sources = sorted({record["source"] for record in records if record.get("source")})
    classified = [record for record in records if record.get("classified")]
    f5 = [record["record_id"] for record in classified if str(record.get("primary_failure_stage", "")).startswith("F5")]
    review = [record["record_id"] for record in classified if record.get("needs_human_review")]
    unknown_outcomes = [record["record_id"] for record in classified if record.get("retrieval_outcome") == "Unknown"]
    details = [
        f"Saved raw records: {len(records)}.",
        f"Public source types in the raw file: {len(sources)} ({', '.join(sources)}).",
        f"Classified records needing human review: {len(review)}.",
        f"Classified records with retrieval outcome Unknown: {len(unknown_outcomes)}.",
        f"Classified records audited as F5 — Recognition Gap: {len(f5)} ({', '.join(f5) or 'none'}).",
        "These limits are reported because they are true of the saved corpus. They were not removed to produce a clean pass.",
    ]
    if missing:
        return _check(
            "10",
            "Research limitations",
            "FAIL",
            "A required limitation statement is missing from the Discovery Engine.",
            details + ["Missing: " + "; ".join(missing)],
            review,
        )
    return _check(
        "10",
        "Research limitations",
        "WARNING",
        "The required limitation statements are visible. The corpus is still small, drawn from few public source types, and too uncertain to support a population or main-cause claim.",
        details,
        sorted(set(review + unknown_outcomes + f5)),
    )


def run_quality_audit() -> Dict[str, Any]:
    """Run all Phase 8 checks. Does not write research files and does not call Groq."""
    data_dir = project_root() / "data"
    records = load_discovery_records()
    analysis = load_research_analysis()
    checks = [
        _check_raw(data_dir),
        _check_counts(data_dir, records, analysis),
        _check_traceability(records, analysis),
        _check_verbatim(data_dir, records, analysis),
        _check_uncertainty(data_dir, records),
        _check_claims(analysis),
        _check_contradictions(records, analysis),
        _check_secrets(),
        _check_failure_handling(records, analysis),
        _check_limitations(records, analysis),
    ]
    failures = sum(1 for check in checks if check["status"] == "FAIL")
    warnings = sum(1 for check in checks if check["status"] == "WARNING")
    passed = sum(1 for check in checks if check["status"] == "PASS")
    if failures:
        overall = "FAIL"
    elif warnings:
        overall = "WARNING"
    else:
        overall = "PASS"
    return {
        "overall": overall,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "warnings": warnings,
        "failures": failures,
        "checks": checks,
        "does_not_prove": DOES_NOT_PROVE,
    }
