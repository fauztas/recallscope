"""Session counters. These are logs for one try, not research results."""


def fresh_diagnostics() -> dict:
    return {
        "started_at": None,
        "found": None,
        "found_photo_id": None,
        "time_to_target_seconds": None,
        "narrowing_interactions": 0,
        "candidate_inspections": 0,
        "not_sure_count": 0,
        "broaden_count": 0,
        "undo_count": 0,
        "not_this_count": 0,
        "closer_count": 0,
        "none_repeat_count": 0,
        "marked_absent": False,
    }


def note_search_started(diagnostics: dict, now: float) -> None:
    if diagnostics.get("started_at") is None:
        diagnostics["started_at"] = now


def note_not_this(diagnostics: dict) -> None:
    diagnostics["not_this_count"] += 1
    diagnostics["narrowing_interactions"] += 1


def note_closer(diagnostics: dict) -> None:
    diagnostics["closer_count"] += 1
    diagnostics["narrowing_interactions"] += 1


def note_broaden(diagnostics: dict, result: str) -> None:
    diagnostics["broaden_count"] += 1
    if result == "already_full":
        diagnostics["none_repeat_count"] += 1


def note_undo(diagnostics: dict) -> None:
    diagnostics["undo_count"] += 1


def note_not_sure(diagnostics: dict) -> None:
    diagnostics["not_sure_count"] += 1


def note_inspection(diagnostics: dict) -> None:
    diagnostics["candidate_inspections"] += 1


def mark_found(diagnostics: dict, photo_id: str, now: float) -> None:
    diagnostics["found"] = True
    diagnostics["found_photo_id"] = photo_id
    diagnostics["marked_absent"] = False
    started = diagnostics.get("started_at")
    if started is not None:
        diagnostics["time_to_target_seconds"] = round(max(0.0, now - started), 1)


def mark_absent(diagnostics: dict) -> None:
    diagnostics["found"] = False
    diagnostics["marked_absent"] = True
    diagnostics["time_to_target_seconds"] = None


def format_duration(seconds) -> str:
    if seconds is None:
        return "Still looking"
    whole = int(seconds)
    if whole < 60:
        return f"{whole} seconds"
    return f"{whole // 60} minutes {whole % 60} seconds"
