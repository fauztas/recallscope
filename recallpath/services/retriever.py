"""Build the ordered candidate list from a memory and photo readings."""

from recallpath.utils.scoring import score_photos, unranked_photos


def rank_collection(memory: dict, photos: list, recognition_clues=None) -> list:
    if not memory or memory.get("no_useful_clues"):
        return unranked_photos(photos)
    return score_photos(memory, photos, recognition_clues or [])
