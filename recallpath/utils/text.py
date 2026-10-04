"""Token helpers shared by clue cleanup and photo scoring."""

import re

STOPWORDS = {
    "a", "an", "the", "of", "us", "my", "we", "were", "was", "it", "from", "with",
    "and", "on", "in", "at", "to", "i", "our", "that", "this", "there", "around",
    "about", "just", "very", "really", "some", "into", "for", "or", "as", "be",
    "been", "is", "are", "am", "me", "had", "have", "has", "when", "where", "what",
    "like", "photo", "picture", "image", "remember", "remembered", "think",
    "maybe", "probably", "possibly", "guess", "wearing", "wear", "wore", "im",
}

SYNONYM_GROUPS = (
    ("cafe", ("cafe", "coffee", "coffeeshop", "coffeehouse", "bistro", "restaurant")),
    ("outside", ("outside", "outdoor", "outdoors", "patio", "terrace")),
    ("plant", ("plant", "plants", "greenery", "leaf", "leaves", "foliage", "flower", "flowers")),
    ("sit", ("sit", "sitting", "seated", "seat", "seats")),
    ("beach", ("beach", "seaside", "shore", "ocean", "sea")),
    ("night", ("night", "evening")),
    ("day", ("daylight", "daytime", "sunny")),
    ("group", ("group", "together")),
    ("table", ("table", "tables")),
    ("mountain", ("mountain", "mountains", "hill", "hills")),
    ("snow", ("snow", "snowy")),
    ("dog", ("dog", "puppy")),
    ("cat", ("cat", "kitten")),
    ("birthday", ("birthday",)),
    ("wedding", ("wedding", "bride", "groom")),
    ("gray", ("gray", "grey")),
    ("1", ("one", "1")),
    ("2", ("two", "2")),
    ("3", ("three", "3")),
    ("4", ("four", "4")),
    ("5", ("five", "5")),
    ("6", ("six", "6")),
)

SYNONYM_CANON = {
    word: canon for canon, words in SYNONYM_GROUPS for word in words
}

COLOR_WORDS = {
    "white", "black", "red", "blue", "green", "yellow", "orange", "pink",
    "purple", "brown", "gray", "beige", "gold", "silver",
}

SOCIAL_WORDS = {
    "cousin", "cousins", "friend", "friends", "family", "mum", "mom", "dad",
    "mother", "father", "sister", "brother", "aunt", "uncle", "grandma",
    "grandfather", "grandmother", "wife", "husband", "partner", "colleague",
}

HEDGE_PATTERNS = (
    r"\bi think\b",
    r"\bi thought\b",
    r"\bmaybe\b",
    r"\bprobably\b",
    r"\bpossibly\b",
    r"\bnot sure\b",
    r"\bi(?:'m| am) not sure\b",
    r"\bmight\b",
    r"\bi guess\b",
    r"\bif i remember\b",
    r"\bi don'?t remember exactly\b",
    r"\bi felt like\b",
)

COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "couple": 2,
    "pair": 2,
}


def canon_token(token: str) -> str:
    mapped = SYNONYM_CANON.get(token, token)
    if mapped.endswith("s") and len(mapped) > 4:
        mapped = SYNONYM_CANON.get(mapped[:-1], mapped[:-1])
    return mapped


def content_tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    tokens = set()
    for word in words:
        if word in STOPWORDS or len(word) < 2:
            continue
        tokens.add(canon_token(word))
    return tokens


def is_hedged(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered) for pattern in HEDGE_PATTERNS)


def split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+|;\s+|\n+", text or "")
    return [part.strip() for part in parts if part and part.strip()]


def colors_in(tokens: set) -> set:
    return {token for token in tokens if token in COLOR_WORDS}


def is_social_only(tokens: set) -> bool:
    if not tokens:
        return False
    allowed = SOCIAL_WORDS | {"people", "person", "group"}
    return all(token in allowed for token in tokens)


def parse_count(text: str):
    lowered = (text or "").lower()
    range_match = re.search(r"\b(\d+)\s*-\s*(\d+)\b", lowered)
    if range_match:
        return int(range_match.group(1))
    for word, count in COUNT_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return count
    number_match = re.search(r"\b(\d+)\b", lowered)
    if number_match:
        return int(number_match.group(1))
    return None


def people_band(text: str):
    """Neutral group size: one person, a pair, or several. No relationship is inferred."""
    count = parse_count(text)
    if count == 1:
        return "one"
    if count == 2:
        return "pair"
    if count is not None and 3 <= count <= 20:
        return "several"
    lowered = (text or "").lower()
    if re.search(r"\b(several|multiple|many|crowd|group|groups)\b", lowered):
        return "several"
    if re.search(r"\bfew\b", lowered):
        return "several"
    if re.search(r"\bsome people\b|\bsome of us\b", lowered):
        return "several"
    return None


def neutral_people_phrase(band: str, evidence: str) -> str:
    """Restate only a group size that is already in the reading."""
    count = parse_count(evidence)
    if band == "one":
        return "one person"
    if band == "pair":
        return "two people"
    if band != "several":
        return ""
    if count is not None and count >= 3:
        return f"{count} people"
    lowered = (evidence or "").lower()
    if re.search(r"\bseveral\b", lowered):
        return "several people"
    if re.search(r"\bmultiple\b", lowered):
        return "multiple people"
    if re.search(r"\bgroup\b", lowered):
        return "a group of people"
    if re.search(r"\bfew\b", lowered):
        return "a few people"
    return "several people"
