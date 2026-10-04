"""
RecallScope — primary interview research

Reads data/primary_research_interviews.json. It does not classify public
evidence, does not call Groq, and does not write research files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

EXPECTED_IDS = ["INT_001", "INT_002", "INT_003", "INT_004", "INT_005"]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def interview_path() -> Path:
    return project_root() / "data" / "primary_research_interviews.json"


def participant_text(participant: Dict[str, Any]) -> str:
    parts = [
        participant.get("unaided_memory", ""),
        participant.get("hardest_part", ""),
        participant.get("after_first_search", ""),
        participant.get("fallback", ""),
        participant.get("memory_during_search", ""),
        participant.get("outcome_note", ""),
        participant.get("retrieval_target", ""),
    ]
    for step in participant.get("search_sequence", []):
        parts.append(step.get("query", ""))
        parts.append(step.get("reaction", ""))
    return "\n".join(part for part in parts if part)


def validate_primary_research(payload: Dict[str, Any]) -> List[str]:
    """Return faithfulness problems. An empty list means the file is usable."""
    problems: List[str] = []
    participants = payload.get("participants", [])
    ids = [person.get("participant_id") for person in participants]
    if ids != EXPECTED_IDS:
        problems.append("Participant IDs are not the five supplied sessions in order.")
    lookup = {person.get("participant_id"): person for person in participants}
    for observation in payload.get("observations", []):
        for item in observation.get("evidence", []):
            participant = lookup.get(item.get("participant_id"))
            quote = item.get("quote", "")
            if participant is None or quote not in participant_text(participant):
                problems.append(f"{item.get('participant_id')} evidence is not in the session record: {quote}")
    return problems


def load_primary_research() -> Dict[str, Any]:
    payload = json.loads(interview_path().read_text(encoding="utf-8"))
    problems = validate_primary_research(payload)
    if problems:
        raise ValueError(" ".join(problems))
    return payload


def category_counts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Count sessions that mention a clue category. Hedged clues remain included."""
    rows = []
    for category in payload.get("clue_categories", []):
        matched = []
        hedged = []
        for person in payload["participants"]:
            clues = [clue for clue in person["remembered_clues"] if category in clue.get("categories", [])]
            if clues:
                matched.append(person["participant_id"])
            if any(clue.get("certainty") == "hedged" for clue in clues):
                hedged.append(person["participant_id"])
        rows.append({
            "category": category,
            "count": len(matched),
            "participant_ids": matched,
            "hedged_participant_ids": hedged,
        })
    return rows


def sessions_where(payload: Dict[str, Any], flag: str, expected: Any) -> List[str]:
    return [
        person["participant_id"]
        for person in payload["participants"]
        if person.get("behaviour_flags", {}).get(flag) == expected
    ]
