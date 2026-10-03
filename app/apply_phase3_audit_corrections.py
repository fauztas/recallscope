"""
One-time Phase 3 audit correction pass.

Changes only AI-derived fields identified by the completed research-quality audit.
Does not call Groq. Does not write the raw or relevance research files.
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.utils.llm_helper import (  # noqa: E402
    FAILURE_STAGES,
    OUTCOMES,
    SIGNALS,
    validate_classification,
)

RAW_PATH = project_root / "data" / "public_evidence_raw.csv"
RELEVANCE_PATH = project_root / "data" / "public_evidence_relevance.csv"
CLASSIFIED_PATH = project_root / "data" / "public_evidence_classified.csv"
LOG_PATH = project_root / "data" / "phase3_audit_corrections.csv"

EXPECTED_RAW_HASH = "e1bc94b3fef4b8a0d26a01b4a2e63a048eddb8bd1d00451a4a4ee80dcf3fdea8"
EXPECTED_RELEVANCE_HASH = "a4f6c17df44fc832aea5f2ed788c202213caf670541080256d0279b1ff5bb158"

F1 = "F1 — Recall Gap"
F3 = "F3 — Interpretation Gap"
F4 = "F4 — Candidate Gap"
F5 = "F5 — Recognition Gap"
F7 = "F7 — Coverage / Indexing Gap"
F8 = "F8 — Unknown / Insufficient Evidence"

PRESERVED = [
    "record_id",
    "source",
    "date",
    "original_text",
    "source_url",
    "relevance_label",
    "relevance_reason",
    "review_required",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False)


# record_id -> field -> (new_value, reason, audit_basis)
CORRECTIONS = {
    "REC_001": {
        "photo_type": (
            "Unknown",
            "The text names Grandma's cat. It does not call the photo a family photo.",
            "High-strength audit: photo type inferred",
        ),
        "remembered_clues": (
            "Grandma; cat; a remembered time frame",
            "Grandma, the cat, and a remembered time frame are stated. '(years)' described the length of scrolling.",
            "High-strength audit: remembered-clue paraphrase",
        ),
    },
    "REC_002": {
        "primary_failure_stage": (
            F8,
            "The post says a date must be remembered and the history scrolled. It does not say the date was forgotten.",
            "Stage audit: F1 not supported; F8 safer",
        ),
        "remembered_clues": (
            "Unknown",
            "The post does not say the capture date is remembered. It says the date has to be remembered.",
            "Stage audit: remembered clue contradicted F1 and is not explicit",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "Candidate volume is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition difficulty is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "Query wording is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "confidence": (
            "Low",
            "The stage is no longer a specific gap.",
            "Stage audit: F8",
        ),
        "human_review_reason": (
            "Phase 3 audit: a required date and scrolling are stated, but a forgotten date is not, so F1 was changed to F8.",
            "The previous review reason described a missing failure reason. The stage itself was unsupported.",
            "Human-review audit: REC_002",
        ),
    },
    "REC_003": {
        "primary_failure_stage": (
            F1,
            "The person states they do not remember when the older photo was taken. No candidate results are described, so F5 is not kept.",
            "F5 audit: REC_003 over-attributed; forgotten date is explicit",
        ),
        "secondary_failure_stage": (
            "None",
            "The supported recall gap is now the primary stage, so it is not repeated as secondary.",
            "F5 audit: REC_003",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "A large library is mentioned. Returned candidates are not described.",
            "F5 audit: overload signal inferred",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "The post does not show the person failing to recognize surfaced candidates.",
            "F5 audit: recognition signal inferred",
        ),
        "failure_reason": (
            "The person does not remember when the older photo was taken and cannot find it among many photos.",
            "The reason now follows the stated forgotten date and the stated large library, without a recognition claim.",
            "F5 audit: REC_003",
        ),
        "human_review_reason": (
            "Phase 3 audit: F5 was removed because no candidate results are described. F1 remains because the date is explicitly forgotten. How the large library blocks retrieval is still unresolved.",
            "Review stays on because the large-library part is not a demonstrated recognition failure.",
            "Human-review audit: REC_003",
        ),
    },
    "REC_004": {
        "failure_reason": (
            "The person cannot easily find specific photos while looking through an album of more than 1400 pictures.",
            "The album size and looking through it are stated. Visual similarity is not stated.",
            "F5 audit: REC_004 supported, but 'similar images' was inferred",
        ),
        "manual_browsing_behavior": (
            "Looking through more than 1400 pictures in an album",
            "The post says 'looking thru 1400 pics.' It does not say thumbnails.",
            "F5 audit: thumbnail wording inferred",
        ),
        "retrieval_outcome": (
            "Unknown",
            "The post says the pictures are not easy to find. It does not say they were not found.",
            "F5 audit: Not Found was stronger than the text",
        ),
    },
    "REC_005": {
        "photo_type": (
            "Unknown",
            "Bike is the search term. The photo type is not specified.",
            "Stage audit: generic photo type",
        ),
        "retrieval_outcome": (
            "Unknown",
            "Unrelated photos were returned. The post does not say a particular photo was absent.",
            "Stage audit: Not Found was stronger than unrelated results",
        ),
    },
    "REC_006": {
        "primary_failure_stage": (
            F8,
            "Six dog photos were returned and date search works. That does not separate a candidate gap from an indexing gap.",
            "F7 audit: REC_006 ambiguous, indexing not proven",
        ),
        "failure_reason": (
            "Searching for dog returns only 6 pictures although the person is sure more dog photos exist. Searching by date works.",
            "The previous reason said the photos were not indexed. The text does not say that.",
            "F7 audit: 'not indexed' inferred",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "The post does not say whether forming the query was difficult.",
            "Signal rule: No was absence of evidence",
        ),
        "manual_scroll_signal": (
            "Unknown",
            "Scrolling is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "confidence": (
            "Low",
            "The observed search result does not identify one failure stage.",
            "F7 audit: REC_006",
        ),
        "needs_human_review": (
            "True",
            "The stage is unresolved between not surfacing the photos and an indexing explanation.",
            "F7 audit: REC_006 ambiguous",
        ),
        "human_review_reason": (
            "Phase 3 audit: keyword search returned 6 dog photos and date search works. That does not establish an indexing failure.",
            "This record was not previously flagged. The F7 label was ambiguous.",
            "F7 audit: REC_006",
        ),
    },
    "REC_007": {
        "primary_failure_stage": (
            F8,
            "The person says renamed keywords no longer look like they work. No specific search result is shown.",
            "F7 audit: REC_007 ambiguous and tentative",
        ),
        "retrieval_outcome": (
            "Unknown",
            "The post does not report a completed search result.",
            "F7 audit: REC_007",
        ),
        "failure_reason": (
            "The person says renaming photos or videos with keywords no longer looks like it works for finding them.",
            "The previous reason stated a definite retrieval failure. The text says it does not look like it will work anymore.",
            "F7 audit: REC_007",
        ),
        "ai_interpretation": (
            "The person asks how to search for specific photos or videos and says keyword renaming no longer looks like it works.",
            "The previous interpretation said the person cannot find the files. The text is more tentative.",
            "F7 audit: REC_007",
        ),
        "confidence": (
            "Low",
            "The evidence does not identify a failure stage.",
            "F7 audit: REC_007",
        ),
        "needs_human_review": (
            "True",
            "The stage is unresolved.",
            "F7 audit: REC_007",
        ),
        "human_review_reason": (
            "Phase 3 audit: renamed keywords are said to no longer look usable. No indexing failure or specific result is shown.",
            "This record needed a safer stage than F7.",
            "F7 audit: REC_007",
        ),
    },
    "REC_008": {
        "primary_failure_stage": (
            F8,
            "Search is described as now feeling nearly impossible. No query, result, or indexing detail is given.",
            "F7 audit: REC_008 over-attributed; F8 safer",
        ),
        "retrieval_outcome": (
            "Unknown",
            "Nearly impossible is not a stated not-found result.",
            "Human-review audit: REC_008 outcome too definite",
        ),
        "failure_reason": (
            "The person says that finding photos with search now feels nearly impossible.",
            "The previous reason said photos could not be located. The text describes a feeling that search has become nearly impossible.",
            "F7 audit: REC_008",
        ),
        "confidence": (
            "Low",
            "The evidence does not identify a failure stage.",
            "F7 audit: REC_008",
        ),
        "human_review_reason": (
            "Phase 3 audit: the comment says search now feels nearly impossible. That is too general for an indexing stage. F8 is safer.",
            "The previous review note said the evidence was brief. The stage was also an unsupported indexing label.",
            "Human-review audit: REC_008",
        ),
    },
    "REC_009": {
        "primary_failure_stage": (
            F8,
            "A basic search said not found. That does not show why, and it does not show an indexing failure.",
            "F7 audit: REC_009 over-attributed; F8 safer",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "No candidates are described, so recognition was not observed either way.",
            "Signal rule: No was absence of evidence",
        ),
        "manual_scroll_signal": (
            "Unknown",
            "Scrolling is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "confidence": (
            "Low",
            "One not-found result does not identify a failure stage.",
            "F7 audit: REC_009",
        ),
        "needs_human_review": (
            "True",
            "The stage is unresolved.",
            "F7 audit: REC_009",
        ),
        "human_review_reason": (
            "Phase 3 audit: the search said not found. A missing result is not evidence of an indexing failure.",
            "This record was not previously flagged. The audit named it as a clear F8 case.",
            "F7 audit: REC_009 was a clear candidate for F8",
        ),
    },
    "REC_010": {
        "primary_failure_stage": (
            F8,
            "Older photos cannot be viewed for long and the place in the library is lost. That is not evidence the photo was absent from search results.",
            "Stage audit: REC_010 F4 ambiguous; F8 safer",
        ),
        "retrieval_outcome": (
            "Unknown",
            "The post does not say whether the photo was found.",
            "Stage audit: REC_010",
        ),
        "evidence_strength_reason": (
            "Brief statement that older photos cannot be viewed for long and the place in browsing is lost.",
            "The previous reason suggested a candidate gap. The audit did not accept that stage.",
            "Stage audit: REC_010",
        ),
        "ai_interpretation": (
            "The person says older photos cannot be viewed for long and they lose their place while looking for something.",
            "The previous interpretation added that retrieval was hindered beyond what the sentence says.",
            "Stage audit: REC_010",
        ),
        "confidence": (
            "Low",
            "The browsing problem does not map cleanly onto one failure stage.",
            "Stage audit: REC_010",
        ),
        "needs_human_review": (
            "True",
            "The stage is unresolved.",
            "Stage audit: REC_010 ambiguous",
        ),
        "human_review_reason": (
            "Phase 3 audit: losing one's place while viewing older photos does not show that the photo was missing from candidates.",
            "This record was not previously flagged. F4 was ambiguous.",
            "Stage audit: REC_010",
        ),
    },
    "REC_011": {
        "primary_failure_stage": (
            F8,
            "Search for Sunfish found nothing. That shows the photos were not surfaced. It does not show an indexing failure, and F4 would also be an unforced choice.",
            "F7 audit: REC_011 over-attributed; mechanism left unknown",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "No candidates were described.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "A query was stated. Difficulty forming it was not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "manual_scroll_signal": (
            "Unknown",
            "The post says scrolling half a million photos is not practical. It does not report whether scrolling happened.",
            "Signal rule: No was absence of evidence",
        ),
        "ai_interpretation": (
            "The person searched for Sunfish in a library of over half a million photos and the search found nothing, although they say they have hundreds of close-up photos.",
            "The previous interpretation added a likely indexing or coverage issue. The text does not say that.",
            "High-strength audit: REC_011 indexing inference",
        ),
        "confidence": (
            "Low",
            "The failed search is specific, but the failure stage is not.",
            "High-strength audit: High confidence in F7 was too strong",
        ),
        "needs_human_review": (
            "True",
            "Not surfaced and not indexed cannot be separated here.",
            "F7 audit: REC_011",
        ),
        "human_review_reason": (
            "Phase 3 audit: Sunfish search found nothing. That does not prove an indexing or coverage failure.",
            "High confidence in F7 was stronger than a not-found search.",
            "F7 audit: REC_011 reads as not surfaced, without a proven mechanism",
        ),
    },
    "REC_012": {
        "primary_failure_stage": (
            F8,
            "Yellow-truck search returns 2 of 10 days, and pickup-truck phrasing changes which trucks remain. F3 and F4 both fit, so neither is forced.",
            "High-strength and human-review audit: REC_012 ambiguous between F3 and F4",
        ),
        "reformulation_behavior": (
            "Tried a different phrasing, 'pickup truck', after 'yellow truck'.",
            "The phrasing change is explicit. Unknown had hidden that stated behavior after a bare Yes/No answer was rejected.",
            "Human-review audit: REC_012 reformulation is explicit",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "Two phrasings are stated. The post does not say forming the query was difficult.",
            "REC_012 audit: preserve only explicit behavior",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "The post describes too few days, not too many candidates.",
            "Signal rule: No was not established",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition difficulty is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "ai_interpretation": (
            "The person asks for yellow truck and gets 2 of 10 days of yellow-truck photos. Trying pickup truck adds some trucks and also drops some yellow trucks found first.",
            "The previous interpretation concluded that the query was not capturing all relevant photos. The correction keeps the stated results only.",
            "REC_012 audit: do not infer an unsupported mechanism",
        ),
        "confidence": (
            "Low",
            "The evidence is specific, but it does not choose between F3 and F4.",
            "High-strength audit: High confidence on F3 alone was too strong",
        ),
        "human_review_reason": (
            "Phase 3 audit: the change from yellow truck to pickup truck is explicit. The partial, unstable results fit both an interpretation gap and a candidate gap, so the stage is F8.",
            "The earlier review note only explained a Yes/No reformulation value. The stage is also ambiguous.",
            "Human-review audit: REC_012",
        ),
    },
    "REC_013": {
        "primary_failure_stage": (
            F8,
            "Dog search returns a subset. Blowtorch search returns eight photos with no blowtorch. One indexing stage does not cover both.",
            "F7 audit: REC_013 over-attributed",
        ),
        "retrieval_outcome": (
            "Partially Found",
            "The dog search returns a tiny subset, so Not Found is too strong for the record as a whole.",
            "High-strength audit: REC_013 outcome",
        ),
        "failure_reason": (
            "Dog search returns a tiny subset of the photos previously returned. Blowtorch search returns eight photos, none of which contains a blowtorch.",
            "The previous reason collapsed both searches into missing expected photos and an indexing stage.",
            "F7 audit: REC_013",
        ),
        "ai_interpretation": (
            "Searching for dog now returns a tiny subset of the photos previously returned. Searching for blowtorch returns eight photos, none of which contains a blowtorch.",
            "The previous interpretation added a general retrieval-difficulty conclusion beyond the two stated searches.",
            "High-strength audit: REC_013",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "Result counts are small. Overload is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition difficulty is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "The queries are stated. Difficulty forming them is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "confidence": (
            "Low",
            "The two searches are specific, but they do not support one failure stage.",
            "High-strength audit: High confidence in one F7 label was too strong",
        ),
        "needs_human_review": (
            "True",
            "The two searches point in different directions.",
            "F7 audit: REC_013",
        ),
        "human_review_reason": (
            "Phase 3 audit: the dog search is partial and the blowtorch search returns the wrong photos. Neither result establishes one indexing failure.",
            "This record was not previously flagged. One F7 label did not fit both searches.",
            "F7 audit: REC_013",
        ),
    },
    "REC_014": {
        "primary_failure_stage": (
            F8,
            "Keywords now return screenshots of text, and the photo can still be found manually. That fits both poor interpretation and the photo not being surfaced.",
            "Stage audit: REC_014 ambiguous between F3 and F4",
        ),
        "retrieval_outcome": (
            "Unknown",
            "Keyword search does not find the photo, but the person says they can still find it manually.",
            "Stage audit: REC_014 mixed outcome",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "Overload is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition difficulty is not discussed.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "The post does not say the keywords were hard to choose.",
            "Signal rule: No was absence of evidence",
        ),
        "confidence": (
            "Low",
            "The screenshot result is clear, but the failure stage is not unique.",
            "Stage audit: REC_014",
        ),
        "needs_human_review": (
            "True",
            "F3 and F4 both remain available.",
            "Stage audit: REC_014 ambiguous",
        ),
        "human_review_reason": (
            "Phase 3 audit: keyword search now returns screenshots containing the words, while the photo can still be found manually. The stage is not forced.",
            "This record was not previously flagged. F3 and F4 both remain possible.",
            "Stage audit: REC_014",
        ),
    },
    "REC_017": {
        "recognition_difficulty_signal": (
            "Unknown",
            "The post does not describe difficulty recognizing a photo among the date's photos.",
            "Signal rule: No was absence of evidence",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "Several options were tried. The post does not say the query was hard to express.",
            "Signal rule: No was absence of evidence",
        ),
    },
    "REC_019": {
        "manual_scroll_signal": (
            "Unknown",
            "The person says they dug for a long time. Scrolling is not stated.",
            "High-strength audit: scroll inferred from digging",
        ),
        "workaround": (
            "Digging for a long time",
            "The text says the video was located by digging for a long time. It does not say this was digging through results.",
            "High-strength audit: REC_019",
        ),
        "ai_interpretation": (
            "The person tagged a video in the info field, searched the exact phrase, and Photos located nothing. They later located it by digging for a long time.",
            "The previous interpretation called the digging manual scrolling. Scrolling is not stated.",
            "High-strength audit: REC_019 scroll inference",
        ),
    },
    "REC_020": {
        "primary_failure_stage": (
            F8,
            "Searching the remembered yellow-sticky-note words usually finds nothing. That does not prove an indexing failure, and it also does not have to be forced into F4.",
            "F7 audit: REC_020 over-attributed; forgotten clues stay Unknown",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "Candidate volume is not discussed.",
            "Human-review audit: REC_020 No signals",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition is not discussed.",
            "Human-review audit: REC_020 No signals",
        ),
        "manual_scroll_signal": (
            "Unknown",
            "Scrolling is not discussed.",
            "Human-review audit: REC_020 No signals",
        ),
        "confidence": (
            "Low",
            "The not-found search is clear. The failure stage is not.",
            "F7 audit: REC_020",
        ),
        "human_review_reason": (
            "Phase 3 audit: forgotten clues stay Unknown. The yellow-sticky-note search usually finds nothing, which does not establish an indexing failure.",
            "The earlier review note corrected invented forgotten clues. The F7 stage was also unsupported.",
            "Human-review audit: REC_020",
        ),
    },
    "REC_021": {
        "primary_failure_stage": (
            F8,
            "A long list makes a specific photo hard to search. The post does not show candidates being recognized or missed.",
            "F5 audit: REC_021 over-attributed; F8 safer",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "A long list is mentioned. It is not shown to be a set of surfaced candidates.",
            "F5 audit: REC_021 signal inferred",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "Recognition difficulty is not described.",
            "F5 audit: REC_021 signal inferred",
        ),
        "failure_reason": (
            "Unknown",
            "The previous reason turned a long list into many results and a recognition problem.",
            "F5 audit: REC_021",
        ),
        "ai_interpretation": (
            "The person says it is very difficult to search for a specific photo in a very long list.",
            "The previous interpretation added a long list of results and a recognition problem.",
            "F5 audit: REC_021",
        ),
        "confidence": (
            "Low",
            "The sentence is too brief for a failure stage.",
            "Human-review audit: REC_021",
        ),
        "human_review_reason": (
            "Phase 3 audit: the sentence is too brief for a recognition stage. Phase 2 manual review remains relevant. F8 is safer.",
            "The earlier review note already marked the sentence as too brief. F5 is now removed.",
            "Human-review audit: REC_021",
        ),
    },
    "REC_022": {
        "primary_failure_stage": (
            F8,
            "The sought photo is found. Later scrolling is for other photos from the same event, which is not recognition of the original target.",
            "F5 audit: REC_022 over-attributed",
        ),
        "retrieval_outcome": (
            "Found",
            "The post says once a looked-for photo is found. Not Found contradicts that sentence.",
            "F5 audit: REC_022 outcome contradicted the text",
        ),
        "candidate_overload_signal": (
            "Unknown",
            "The large set is the library timeline after leaving search, not a described candidate list.",
            "F5 audit: REC_022",
        ),
        "recognition_difficulty_signal": (
            "Unknown",
            "The target photo was found. Recognition difficulty is not described.",
            "F5 audit: REC_022",
        ),
        "failure_reason": (
            "After a looked-for photo is found, seeing other photos from the same event requires noting the date and time, leaving search, and scrolling through tens of thousands of photos.",
            "The scrolling steps are explicit. The previous reason framed them as a recognition failure.",
            "F5 audit: REC_022",
        ),
        "ai_interpretation": (
            "Once a looked-for photo is found, the person notes the date and time, leaves search, and scrolls through tens of thousands of photos to see others from the same event.",
            "The previous interpretation called this a recognition challenge. The text does not say that.",
            "F5 audit: REC_022",
        ),
        "confidence": (
            "Low",
            "The behavior is clear, but it does not fit a recognition stage.",
            "F5 audit: REC_022",
        ),
        "needs_human_review": (
            "True",
            "The taxonomy does not clearly name this post-retrieval browsing step.",
            "F5 audit: REC_022",
        ),
        "human_review_reason": (
            "Phase 3 audit: the first photo is found. The remaining difficulty is scrolling to other event photos, which is not a recognition gap.",
            "This record was not previously flagged. The saved outcome also contradicted the text.",
            "F5 audit: REC_022",
        ),
    },
    "REC_024": {
        "failure_reason": (
            "Photos do not appear when the person searches the words from descriptions they added.",
            "The previous reason said the descriptions were not indexed. The text says the photos do not appear.",
            "High-strength audit: REC_024 indexed wording inferred",
        ),
        "query_difficulty_signal": (
            "Unknown",
            "The post does not discuss whether the description words were hard to turn into a query.",
            "Signal rule: No was absence of evidence",
        ),
    },
}


def apply_corrections() -> pd.DataFrame:
    raw_hash = _sha256(RAW_PATH)
    relevance_hash = _sha256(RELEVANCE_PATH)
    if raw_hash != EXPECTED_RAW_HASH or relevance_hash != EXPECTED_RELEVANCE_HASH:
        raise RuntimeError("Immutable research file hash changed before corrections. No write was made.")

    classified = _read(CLASSIFIED_PATH)
    raw = _read(RAW_PATH)
    relevance = _read(RELEVANCE_PATH)
    log_rows = []

    for record_id, fields in CORRECTIONS.items():
        matches = classified.index[classified["record_id"] == record_id].tolist()
        if len(matches) != 1:
            raise RuntimeError(f"{record_id} was not found exactly once.")
        index = matches[0]
        for field, (new_value, reason, basis) in fields.items():
            previous = str(classified.at[index, field])
            corrected = str(new_value)
            if previous == corrected:
                continue
            classified.at[index, field] = corrected
            log_rows.append({
                "record_id": record_id,
                "field_changed": field,
                "previous_value": previous,
                "corrected_value": corrected,
                "reason": reason,
                "audit_basis": basis,
            })

    for column in PRESERVED:
        if not classified[column].equals(
            classified[column]  # placeholder to keep linters from dropping the name
        ):
            pass
        for _, row in classified.iterrows():
            raw_row = raw.loc[raw["record_id"] == row["record_id"]].iloc[0]
            relevance_row = relevance.loc[relevance["record_id"] == row["record_id"]].iloc[0]
            for source_field in ("record_id", "source", "date", "original_text", "source_url"):
                if row[source_field] != raw_row[source_field] or row[source_field] != relevance_row[source_field]:
                    raise RuntimeError(f"Preserved field changed or mismatched for {row['record_id']} {source_field}.")

    log = pd.DataFrame(log_rows, columns=[
        "record_id",
        "field_changed",
        "previous_value",
        "corrected_value",
        "reason",
        "audit_basis",
    ])
    temporary_classified = CLASSIFIED_PATH.with_suffix(".csv.tmp")
    temporary_log = LOG_PATH.with_suffix(".csv.tmp")
    classified.to_csv(temporary_classified, index=False, encoding="utf-8")
    log.to_csv(temporary_log, index=False, encoding="utf-8")
    temporary_classified.replace(CLASSIFIED_PATH)
    temporary_log.replace(LOG_PATH)

    if _sha256(RAW_PATH) != raw_hash or _sha256(RELEVANCE_PATH) != relevance_hash:
        raise RuntimeError("An immutable research file changed during the correction pass.")
    return log


def validate(log: pd.DataFrame) -> None:
    classified = _read(CLASSIFIED_PATH)
    raw = _read(RAW_PATH)
    relevance = _read(RELEVANCE_PATH)
    relevant_ids = set(relevance.loc[relevance["relevance_label"] == "Relevant", "record_id"])
    uncertain_ids = set(relevance.loc[relevance["relevance_label"] == "Uncertain", "record_id"])
    classified_ids = classified["record_id"].tolist()

    checks = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append(passed)
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    record("Exactly 22 classified records", len(classified) == 22 and len(set(classified_ids)) == 22, str(len(classified)))
    record("IDs match Relevant records", set(classified_ids) == relevant_ids, f"{len(set(classified_ids))} IDs")
    record("Uncertain records excluded", uncertain_ids.isdisjoint(classified_ids), ", ".join(sorted(uncertain_ids)))
    record("No invented IDs", set(classified_ids).issubset(set(raw["record_id"])), "checked against raw IDs")
    record("Raw hash unchanged", _sha256(RAW_PATH) == EXPECTED_RAW_HASH, _sha256(RAW_PATH))
    record("Relevance hash unchanged", _sha256(RELEVANCE_PATH) == EXPECTED_RELEVANCE_HASH, _sha256(RELEVANCE_PATH))

    preserved_ok = True
    schema_ok = True
    for _, row in classified.iterrows():
        raw_row = raw.loc[raw["record_id"] == row["record_id"]].iloc[0]
        for field in ("source", "date", "original_text", "source_url"):
            if row[field] != raw_row[field]:
                preserved_ok = False
        if row["primary_failure_stage"] not in FAILURE_STAGES:
            schema_ok = False
        if row["secondary_failure_stage"] not in FAILURE_STAGES + ["None", "Unknown"]:
            schema_ok = False
        if row["retrieval_outcome"] not in OUTCOMES:
            schema_ok = False
        for signal in (
            "candidate_overload_signal",
            "recognition_difficulty_signal",
            "query_difficulty_signal",
            "manual_scroll_signal",
        ):
            if row[signal] not in SIGNALS:
                schema_ok = False
        if row["evidence_strength"] not in {"High", "Medium", "Low"}:
            schema_ok = False
        if row["confidence"] not in {"High", "Medium", "Low"}:
            schema_ok = False
        if row["needs_human_review"] not in {"True", "False"}:
            schema_ok = False
        if row["needs_human_review"] == "True" and not str(row["human_review_reason"]).strip():
            schema_ok = False
        payload = {
            "retrieval_intent": row["retrieval_intent"],
            "retrieval_scenario": row["retrieval_scenario"],
            "photo_type": row["photo_type"],
            "remembered_clues": row["remembered_clues"],
            "missing_or_forgotten_clues": row["missing_or_forgotten_clues"],
            "search_or_browse_behavior": row["search_or_browse_behavior"],
            "reformulation_behavior": row["reformulation_behavior"],
            "manual_browsing_behavior": row["manual_browsing_behavior"],
            "workaround": row["workaround"],
            "failure_reason": row["failure_reason"],
            "evidence_strength_reason": row["evidence_strength_reason"],
            "ai_interpretation": row["ai_interpretation"],
            "retrieval_outcome": row["retrieval_outcome"],
            "primary_failure_stage": row["primary_failure_stage"],
            "secondary_failure_stage": row["secondary_failure_stage"],
            "candidate_overload_signal": row["candidate_overload_signal"],
            "recognition_difficulty_signal": row["recognition_difficulty_signal"],
            "query_difficulty_signal": row["query_difficulty_signal"],
            "manual_scroll_signal": row["manual_scroll_signal"],
            "evidence_strength": row["evidence_strength"],
            "confidence": row["confidence"],
            "needs_human_review": row["needs_human_review"] == "True",
            "human_review_reason": row["human_review_reason"],
        }
        _, errors = validate_classification(payload)
        if errors:
            schema_ok = False
            print(row["record_id"], errors)

    record("Original evidence fields unchanged", preserved_ok, "source, date, text, and URL match raw")
    record("Corrected rows pass schema validation", schema_ok, "stages, signals, outcomes, and review reasons")
    record(
        "REC_020 forgotten clues remain Unknown",
        classified.loc[classified["record_id"] == "REC_020", "missing_or_forgotten_clues"].iloc[0] == "Unknown",
        "Unknown",
    )
    record("Correction log has only changes", len(log) > 0 and log["previous_value"].ne(log["corrected_value"]).all(), f"{len(log)} rows")

    print("STAGE_DISTRIBUTION")
    print(classified["primary_failure_stage"].value_counts().to_string())
    print("STRENGTH_DISTRIBUTION")
    print(classified["evidence_strength"].value_counts().to_string())
    print("HUMAN_REVIEW", int((classified["needs_human_review"] == "True").sum()))
    print("RECORDS_CHANGED", log["record_id"].nunique())
    print("FIELDS_CHANGED", len(log))
    print("STAGE_CHANGES")
    stage_log = log[log["field_changed"] == "primary_failure_stage"]
    for _, row in stage_log.iterrows():
        print(f"{row['record_id']}: {row['previous_value']} -> {row['corrected_value']}")
    if not all(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    correction_log = apply_corrections()
    validate(correction_log)
