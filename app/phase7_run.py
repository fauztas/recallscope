"""
RecallScope — Phase 7 checks

Runs the two required Challenge an Insight tests and confirms the saved
research files do not change. Groq is called only for these two insights.
"""

import hashlib
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.challenge_insight import ASSESSMENTS, challenge_insight
from app.utils.discovery_data import load_discovery_records

RAW_HASH = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
RELEVANCE_HASH = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"
CLASSIFIED_HASH = "1d94edc9028ca519e22879f910a20f91829d4dfe7afffc689388cb07f0844c63"
ANALYSIS_HASH = "9837848c0787cfda5533d3bea2f7b6254f310b22f4335cf82e599de0a022e7c6"

TESTS = [
    (
        "recognition",
        "Recognition difficulty is the main reason people fail to retrieve remembered photos.",
    ),
    (
        "scrolling",
        "Manual scrolling is used when search does not help users find a remembered photo.",
    ),
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
    review_ids = [
        record["record_id"] for record in records
        if record.get("needs_human_review")
    ]
    ok = True

    for label, insight in TESTS:
        result = challenge_insight(insight, records)
        print(f"TEST {label}")
        print(f"  called_model={result['called_model']} status={result['status']}")
        print(f"  assessment={result['assessment']}")
        print(f"  reason={result['assessment_reason'][:500]}")
        print(f"  retrieved={result['retrieved_record_ids']}")
        print(f"  supporting={[card['record_id'] for card in result['supporting']]}")
        print(f"  challenging={[card['record_id'] for card in result['challenging']]}")
        print(f"  uncertain={result['uncertain_record_ids']}")
        print(f"  questions={len(result['next_research_questions'])}")
        for question in result["next_research_questions"]:
            print(f"    Q: {question[:180]}")
        if result.get("error"):
            print(f"  error={result['error'][:300]}")
            ok = False
        dumped = str(result)
        if "gsk_" in dumped:
            print("  SECRET APPEARED IN RESULT")
            ok = False
        if result["assessment"] not in ASSESSMENTS:
            print("  BAD ASSESSMENT LABEL")
            ok &= False
        if set(result["uncertain_record_ids"]) != {"REC_015", "REC_023"}:
            print("  UNCERTAIN IDS CHANGED")
            ok &= False
        cited = {card["record_id"] for card in result["supporting"] + result["challenging"]}
        if cited & set(result["uncertain_record_ids"]):
            print("  UNCERTAIN RECORD USED AS EVIDENCE")
            ok &= False
        for card in result["supporting"] + result["challenging"]:
            record = lookup.get(card["record_id"])
            exists = record is not None
            quote_ok = exists and _quote_ok(card["excerpt"], record["original_text"])
            url_ok = exists and card["source_url"] == record["source_url"] and bool(card["source_url"])
            review_ok = exists and bool(card["needs_human_review"]) == bool(record["needs_human_review"])
            in_retrieved = card["record_id"] in result["retrieved_record_ids"]
            print(
                f"  trace {card['record_id']} exists={exists} quote={quote_ok} "
                f"url={url_ok} review={review_ok} retrieved={in_retrieved}"
            )
            ok &= exists and quote_ok and url_ok and review_ok and in_retrieved
        if label == "recognition":
            supported = result["assessment"] == "Supported by current evidence"
            has_rec_004 = "REC_004" in {card["record_id"] for card in result["supporting"]}
            has_challenge = bool(result["challenging"])
            print(f"  not_confidently_supported={not supported} rec_004={has_rec_004} challenge={has_challenge}")
            ok &= (not supported) and has_rec_004 and has_challenge and result["called_model"]
        productish = (
            "product", "feature", "intervention", "solution", "recommend",
            "design element", "alleviate", "ai suggestion",
        )
        for question in result["next_research_questions"]:
            if any(marker in question.lower() for marker in productish):
                print("  PRODUCT QUESTION", question)
                ok &= False
        if label == "scrolling":
            support_ids = {card["record_id"] for card in result["supporting"]}
            real_scroll = bool(support_ids & {"REC_001", "REC_002", "REC_004", "REC_010", "REC_014", "REC_019", "REC_022"})
            prevalence = "prevalence" in result["assessment"].lower() or "all google photos users" in result["assessment_reason"].lower()
            print(f"  real_scroll_records={real_scroll} prevalence_claim={prevalence}")
            ok &= result["called_model"] and real_scroll and bool(result["supporting"]) and not prevalence
            ok &= 2 <= len(result["next_research_questions"]) <= 4

    after = {name: _sha256(path) for name, path in paths.items()}
    expected = {
        "raw": RAW_HASH,
        "relevance": RELEVANCE_HASH,
        "classified": CLASSIFIED_HASH,
        "analysis": ANALYSIS_HASH,
    }
    hashes_ok = before == after == expected
    print("HASHES", hashes_ok, after)
    print("HUMAN_REVIEW", ", ".join(review_ids))
    print("OVERALL", "PASS" if ok and hashes_ok else "FAIL")
    return 0 if ok and hashes_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
