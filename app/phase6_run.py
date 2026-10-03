"""
RecallScope — Phase 6 checks

Runs four Ask the Evidence questions and confirms the saved research files
do not change. Groq is called only for questions that match saved evidence.
"""

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.ask_evidence import ask_evidence
from app.utils.discovery_data import load_discovery_records

RAW_HASH = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
RELEVANCE_HASH = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"
CLASSIFIED_HASH = "1d94edc9028ca519e22879f910a20f91829d4dfe7afffc689388cb07f0844c63"
ANALYSIS_HASH = "9837848c0787cfda5533d3bea2f7b6254f310b22f4335cf82e599de0a022e7c6"

QUESTIONS = [
    ("supported", "What evidence do we have of manual scrolling?"),
    ("mixed", "What evidence supports candidate overload or recognition difficulty?"),
    ("unanswerable", "What is the average Google Photos subscription price?"),
    ("leading", "Does this prove recognition failure is the main Google Photos problem?"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quote_ok(excerpt: str, original: str) -> bool:
    compact = " ".join(original.split())
    body = excerpt[:-1] if excerpt.endswith("…") else excerpt
    return bool(body) and body in compact


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
    lookup = {record["record_id"]: record for record in records}
    ok = True

    for label, question in QUESTIONS:
        result = ask_evidence(question, records)
        print(f"TEST {label}")
        print(f"  called_model={result['called_model']} status={result['status']}")
        print(f"  ids={result['supporting_record_ids']}")
        print(f"  limiting={result['limiting_record_ids']}")
        print(f"  mixed={result['evidence_is_mixed']} insufficient={result['evidence_is_insufficient']}")
        print(f"  answer={result['short_answer'][:400]}")
        if result.get("error"):
            print(f"  error={result['error'][:300]}")
        for card in result["supporting_excerpts"] + result["limiting_excerpts"]:
            record = lookup.get(card["record_id"])
            exists = record is not None
            quote_ok = exists and _quote_ok(card["excerpt"], record["original_text"])
            url_ok = exists and card["source_url"] == record["source_url"]
            print(f"  trace {card['record_id']} exists={exists} quote={quote_ok} url={url_ok}")
            ok &= exists and quote_ok and url_ok
        if label == "supported":
            ok &= result["called_model"] and bool(result["supporting_record_ids"]) and not result["evidence_is_insufficient"]
        if label == "mixed":
            ok &= result["called_model"] and (result["evidence_is_mixed"] or bool(result["limiting_record_ids"]) or "mixed" in result["short_answer"].lower() or "one" in result["short_answer"].lower())
        if label == "unanswerable":
            ok &= (not result["called_model"]) and result["evidence_is_insufficient"] and not result["supporting_record_ids"]
        if label == "leading":
            answer = result["short_answer"].lower()
            refused = answer.startswith("no") or "does not establish" in answer or "not establish" in answer or "cannot" in answer
            agreed = answer.startswith("yes")
            print(f"  refused={refused} agreed={agreed}")
            ok &= result["called_model"] and refused and not agreed
        print()

    after = {name: _sha256(path) for name, path in paths.items()}
    expected = {
        "raw": RAW_HASH,
        "relevance": RELEVANCE_HASH,
        "classified": CLASSIFIED_HASH,
        "analysis": ANALYSIS_HASH,
    }
    for name in paths:
        unchanged = before[name] == after[name] == expected[name]
        print(f"[{'PASS' if unchanged else 'FAIL'}] {name} unchanged: {after[name]}")
        ok &= unchanged
    print("OVERALL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
