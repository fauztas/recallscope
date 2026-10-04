"""Describe uploaded photos in batches of at most three."""

from recallpath.services.groq_client import complete_vision, vision_user_content
from recallpath.utils.errors import USER_MESSAGES, ProviderError, public_message
from recallpath.utils.schema import (
    failed_reading,
    normalize_photo_reading,
    parse_json_object,
    readings_from_response,
)

VISION_SYSTEM = """You describe photographs for a personal photo search.

Return one JSON object:
{"photos":[{"photo_id":"","people_count":"unknown","people_arrangement":"","setting":"","objects":[],"appearance":[],"activity":"","time_cues":"","not_visible":[],"summary":"","confidence":"medium","observations":[{"facet":"setting","text":"","confidence":"high"}]}]}

Rules:
- Describe only what is visible.
- Do not name people.
- Do not guess a city, country, landmark name, or calendar date.
- people_count is a number, a short range such as 3-4, or unknown.
- time_cues may be day, night, or indoors. Do not invent a year.
- If you cannot tell, leave the field empty or unknown and lower confidence.
- If the image cannot be read, return empty fields and confidence unknown. Do not invent a scene.
- Use the photo_id values you were given, in the same order.
- Facets: people, setting, objects, appearance, event, time, other.
"""

_STOP_KINDS = {"rate_limit", "timeout", "missing_key", "invalid_key"}


def iter_batches(items: list, size: int):
    """Yield groups of at most 3. A larger requested size is lowered."""
    bounded = max(1, min(3, int(size or 3)))
    for start in range(0, len(items), bounded):
        yield items[start : start + bounded]


def _prompt(images: list) -> str:
    lines = [
        "Describe every photo below.",
        "Return one JSON object with a photos array in this order.",
    ]
    for index, image in enumerate(images, start=1):
        lines.append(f"Photo {index} photo_id: {image['id']}")
    return "\n".join(lines)


def _messages(images: list) -> list:
    return [
        {"role": "system", "content": VISION_SYSTEM},
        {"role": "user", "content": vision_user_content(_prompt(images), images)},
    ]


def _slim(photo: dict) -> dict:
    return {"id": photo["id"], "mime": photo.get("mime") or "image/jpeg", "bytes": photo["bytes"]}


def _aligned(images: list, readings: list) -> bool:
    if len(readings) != len(images):
        return False
    found = [str(item.get("photo_id") or "").strip() for item in readings]
    wanted = [image["id"] for image in images]
    if not any(found):
        return True
    return found == wanted or set(found) == set(wanted)


def _ordered(images: list, readings: list) -> list:
    found = {str(item.get("photo_id") or "").strip(): item for item in readings}
    wanted = [image["id"] for image in images]
    if set(found) == set(wanted):
        chosen = [found[photo_id] for photo_id in wanted]
    else:
        chosen = readings
    return [normalize_photo_reading(item, image["id"]) for image, item in zip(images, chosen)]


def _parse(images: list, raw: str) -> list:
    readings = readings_from_response(parse_json_object(raw))
    if not _aligned(images, readings):
        raise ValueError("Photo readings did not match the batch.")
    return _ordered(images, readings)


def _call(images: list, complete_fn) -> list:
    if len(images) > 3:
        raise ProviderError("bad_request", "Refusing to send more than 3 photos in one vision request.")
    raw = complete_fn(_messages(images))
    return _parse(images, raw)


def _mark_failed(photo: dict, reason: str) -> None:
    photo["analysis"] = failed_reading(photo["id"], reason)


def _remember_error(outcome: dict, exc: ProviderError) -> None:
    outcome["halt"] = exc.kind
    outcome["message"] = public_message(exc)
    outcome["detail"] = str(exc)


def _analyse_one(photo: dict, complete_fn, outcome: dict) -> bool:
    image = _slim(photo)
    try:
        readings = _call([image], complete_fn)
    except ProviderError as exc:
        if exc.kind in _STOP_KINDS:
            _remember_error(outcome, exc)
            return True
        _mark_failed(photo, public_message(exc))
        return False
    except ValueError:
        _mark_failed(photo, USER_MESSAGES["bad_response"])
        return False
    photo["analysis"] = readings[0]
    return False


def _analyse_batch(batch: list, complete_fn, outcome: dict) -> bool:
    images = [_slim(photo) for photo in batch]
    try:
        readings = _call(images, complete_fn)
    except ProviderError as exc:
        if exc.kind in _STOP_KINDS or len(batch) == 1:
            if exc.kind in _STOP_KINDS:
                _remember_error(outcome, exc)
                return True
            _mark_failed(batch[0], public_message(exc))
            return False
        for photo in batch:
            if _analyse_one(photo, complete_fn, outcome):
                return True
        return False
    except ValueError:
        if len(batch) == 1:
            _mark_failed(batch[0], USER_MESSAGES["bad_response"])
            return False
        for photo in batch:
            if _analyse_one(photo, complete_fn, outcome):
                return True
        return False
    for photo, reading in zip(batch, readings):
        photo["analysis"] = reading
    return False


def photos_needing_analysis(photos: list) -> list:
    needed = []
    for photo in photos:
        analysis = photo.get("analysis")
        status = analysis.get("analysis_status") if isinstance(analysis, dict) else ""
        if status not in {"ok", "weak"}:
            needed.append(photo)
    return needed


def analyse_photos(photos: list, complete_fn, batch_size: int = 3, on_progress=None) -> dict:
    """Fill photo['analysis']. Stop on rate limit, timeout, or a missing key without inventing readings."""
    outcome = {"halt": None, "message": "", "detail": ""}
    pending = photos_needing_analysis(photos)

    def report() -> None:
        if on_progress:
            finished = sum(1 for photo in photos if photo.get("analysis"))
            on_progress(finished, len(photos))

    report()
    for batch in iter_batches(pending, batch_size):
        if _analyse_batch(batch, complete_fn, outcome):
            report()
            break
        report()
    return outcome


def groq_vision_complete(messages: list) -> str:
    return complete_vision(messages)
