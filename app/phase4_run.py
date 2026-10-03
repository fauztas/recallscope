"""
RecallScope — Phase 4 validation runner

Builds the research analysis from the audited classifications and checks
that evidence files and Unknown values stay intact.
"""

import hashlib
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.research_analysis import build_research_analysis, save_research_analysis

RAW_HASH = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
RELEVANCE_HASH = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"
EXCLUDED_IDS = {"REC_015", "REC_023"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(name: str, passed: bool, detail: str) -> bool:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: {detail}")
    return passed


def main() -> int:
    data = project_root / "data"
    raw_path = data / "public_evidence_raw.csv"
    relevance_path = data / "public_evidence_relevance.csv"
    classified_path = data / "public_evidence_classified.csv"
    raw_before = _sha256(raw_path)
    relevance_before = _sha256(relevance_path)
    classified_before = _sha256(classified_path)

    analysis = build_research_analysis()
    output_path = save_research_analysis(analysis)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    raw_after = _sha256(raw_path)
    relevance_after = _sha256(relevance_path)
    classified_after = _sha256(classified_path)
    classified_ids = set(saved["input"]["classified_record_ids"])
    ok = True

    ok &= _check("Raw hash unchanged", raw_before == raw_after == RAW_HASH, raw_after)
    ok &= _check("Relevance hash unchanged", relevance_before == relevance_after == RELEVANCE_HASH, relevance_after)
    ok &= _check("Classified file unchanged", classified_before == classified_after, classified_after)
    ok &= _check(
        "Classified record count",
        saved["input"]["classified_record_count"] == 22,
        str(saved["input"]["classified_record_count"]),
    )
    ok &= _check(
        "Uncertain records excluded",
        EXCLUDED_IDS.isdisjoint(classified_ids) and set(saved["input"]["uncertain_record_ids"]) == EXCLUDED_IDS,
        ", ".join(saved["input"]["uncertain_record_ids"]),
    )
    ok &= _check(
        "Stage counts match classified records",
        saved["failure_stage_count_check"]["matches"],
        str(saved["failure_stage_count_check"]),
    )

    referenced = []
    for card in saved["pattern_cards"]:
        referenced.extend(card["supporting_record_ids"])
    for candidate in saved["candidate_problem_areas"]:
        referenced.extend(candidate["supporting_record_ids"])
        ok &= _check(
            f"Candidate not selected: {candidate['candidate_problem_area']}",
            candidate["ranked"] is False and candidate["selected"] is False,
            f"{candidate['supporting_record_count']} records",
        )
    missing = sorted(set(referenced) - classified_ids)
    ok &= _check("Supporting IDs exist", not missing, ", ".join(missing) or "all present")
    ok &= _check(
        "Research limitations present",
        len(saved["research_limitations"]) >= 8 and "not population prevalence" in " ".join(saved["research_limitations"]).lower(),
        f"{len(saved['research_limitations'])} statements",
    )

    signal_names = {
        "manual_scroll_signal",
        "candidate_overload_signal",
        "recognition_difficulty_signal",
        "query_difficulty_signal",
    }
    for behaviour in saved["behaviours"]:
        if behaviour["behaviour"] not in signal_names:
            continue
        total = (
            behaviour["explicitly_supported_count"]
            + behaviour["explicitly_contradicted_count"]
            + behaviour["not_established_count"]
        )
        ok &= _check(
            f"Unknown kept separate for {behaviour['behaviour']}",
            total == saved["input"]["classified_record_count"],
            f"Yes {behaviour['explicitly_supported_count']}, No {behaviour['explicitly_contradicted_count']}, Unknown {behaviour['not_established_count']}",
        )

    gave_up = next(item for item in saved["behaviours"] if item["behaviour"] == "Retrieval outcome: Gave Up")
    unknown_outcome = next(item for item in saved["behaviours"] if item["behaviour"] == "Retrieval outcome: Unknown")
    ok &= _check("Gave Up stays explicit", gave_up["explicitly_supported_count"] == 0, "0 records")
    ok &= _check(
        "Unknown outcomes remain",
        unknown_outcome["explicitly_supported_count"] > 0,
        str(unknown_outcome["explicitly_supported_count"]),
    )
    ok &= _check("Analysis artifact written", output_path.exists(), str(output_path))
    print(f"PATTERNS {len(saved['pattern_cards'])}")
    for card in saved["pattern_cards"]:
        print(f"PATTERN {card['pattern_name']} | {card['supporting_record_count']} | {card['confidence']} | {', '.join(card['supporting_record_ids'])}")
    print(f"CANDIDATES {len(saved['candidate_problem_areas'])}")
    for candidate in saved["candidate_problem_areas"]:
        print(f"CANDIDATE {candidate['candidate_problem_area']} | {candidate['supporting_record_count']} | {candidate['confidence']} | {', '.join(candidate['supporting_record_ids'])}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
