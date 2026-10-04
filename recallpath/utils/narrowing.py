"""Recognition actions change the visible window. They do not delete photos."""

import copy


def new_view() -> dict:
    return {
        "hidden_ids": [],
        "anchor_ids": [],
        "narrowed": False,
        "recognition_clues": [],
        "history": [],
        "repeated_full_set": 0,
    }


def _snapshot(view: dict) -> dict:
    return {
        "hidden_ids": list(view["hidden_ids"]),
        "anchor_ids": list(view["anchor_ids"]),
        "narrowed": view["narrowed"],
        "recognition_clues": copy.deepcopy(view["recognition_clues"]),
    }


def _push(view: dict) -> None:
    view["history"].append(_snapshot(view))
    if len(view["history"]) > 30:
        del view["history"][0]


def hide_photo(view: dict, photo_id: str) -> None:
    _push(view)
    if photo_id not in view["hidden_ids"]:
        view["hidden_ids"].append(photo_id)


def mark_closer(view: dict, photo_id: str, clues: list) -> None:
    _push(view)
    if photo_id not in view["anchor_ids"]:
        view["anchor_ids"].append(photo_id)
    existing = {clue.get("text", "").lower() for clue in view["recognition_clues"]}
    for clue in clues:
        if clue.get("text", "").lower() in existing:
            continue
        view["recognition_clues"].append(clue)
        existing.add(clue.get("text", "").lower())
    view["narrowed"] = True


def broaden(view: dict) -> str:
    already_open = not view["hidden_ids"] and not view["narrowed"] and not view["recognition_clues"]
    if already_open:
        view["repeated_full_set"] += 1
        return "already_full"
    _push(view)
    view["hidden_ids"] = []
    view["anchor_ids"] = []
    view["narrowed"] = False
    view["recognition_clues"] = []
    return "broadened"


def undo(view: dict) -> bool:
    if not view["history"]:
        return False
    previous = view["history"].pop()
    view["hidden_ids"] = previous["hidden_ids"]
    view["anchor_ids"] = previous["anchor_ids"]
    view["narrowed"] = previous["narrowed"]
    view["recognition_clues"] = previous["recognition_clues"]
    return True


def visible_ids(ranked: list, view: dict) -> list:
    shown = []
    for item in ranked:
        photo_id = item["photo_id"]
        if photo_id in view["hidden_ids"]:
            continue
        if view["narrowed"] and item["group"] == "other" and photo_id not in view["anchor_ids"]:
            continue
        shown.append(photo_id)
    return shown
