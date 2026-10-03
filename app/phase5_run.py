"""
RecallScope — Phase 5 integrity check

Confirms the Discovery Interface can read the saved artifacts without
changing them and without calling the classifier.
"""

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.discovery_data import classified_records, load_discovery_records, load_research_analysis

RAW_HASH = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
RELEVANCE_HASH = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"
CLASSIFIED_HASH = "1d94edc9028ca519e22879f910a20f91829d4dfe7afffc689388cb07f0844c63"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(name: str, passed: bool, detail: str) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def main() -> int:
    data = project_root / "data"
    paths = {
        "raw": data / "public_evidence_raw.csv",
        "relevance": data / "public_evidence_relevance.csv",
        "classified": data / "public_evidence_classified.csv",
        "analysis": data / "research_analysis.json",
    }
    before = {name: _sha256(path) for name, path in paths.items()}
    records = load_discovery_records()
    analysis = load_research_analysis()
    after = {name: _sha256(path) for name, path in paths.items()}

    classified = classified_records(records)
    classified_ids = {record["record_id"] for record in classified}
    uncertain_ids = {record["record_id"] for record in records if record["relevance_label"] == "Uncertain"}
    referenced = []
    for card in analysis["pattern_cards"]:
        referenced.extend(card["supporting_record_ids"])
    for candidate in analysis["candidate_problem_areas"]:
        referenced.extend(candidate["supporting_record_ids"])

    discovery_source = (project_root / "app" / "utils" / "discovery_view.py").read_text(encoding="utf-8")
    discovery_data = (project_root / "app" / "utils" / "discovery_data.py").read_text(encoding="utf-8")
    combined = discovery_source + discovery_data

    ok = True
    ok &= _check("Raw file unchanged", before["raw"] == after["raw"] == RAW_HASH, after["raw"])
    ok &= _check("Relevance file unchanged", before["relevance"] == after["relevance"] == RELEVANCE_HASH, after["relevance"])
    ok &= _check("Classified file unchanged", before["classified"] == after["classified"] == CLASSIFIED_HASH, after["classified"])
    ok &= _check("Analysis artifact unchanged", before["analysis"] == after["analysis"], after["analysis"])
    ok &= _check("Raw record count", len(records) == 24, str(len(records)))
    ok &= _check("Classified record count", len(classified) == 22, str(len(classified)))
    ok &= _check("Uncertain records excluded from classification", uncertain_ids == {"REC_015", "REC_023"}, ", ".join(sorted(uncertain_ids)))
    ok &= _check("Pattern cards loaded from artifact", len(analysis["pattern_cards"]) == 7, str(len(analysis["pattern_cards"])))
    ok &= _check(
        "Candidates remain unranked",
        len(analysis["candidate_problem_areas"]) == 3 and all(not item["ranked"] and not item["selected"] for item in analysis["candidate_problem_areas"]),
        str(len(analysis["candidate_problem_areas"])),
    )
    missing = sorted(set(referenced) - classified_ids)
    ok &= _check("Pattern and candidate IDs exist", not missing, ", ".join(missing) or "all present")
    ok &= _check(
        "Discovery code does not call Groq",
        "groq" not in combined.lower() and "classify_evidence_record" not in combined and "save_research_analysis" not in combined,
        "no classifier or analysis rewrite",
    )
    unknown_outcomes = sum(1 for record in classified if record["retrieval_outcome"] == "Unknown")
    ok &= _check("Unknown outcomes preserved", unknown_outcomes == 10, str(unknown_outcomes))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
