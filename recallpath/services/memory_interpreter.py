"""Turn a natural-language memory into stated, hedged, and inferred clues."""

from recallpath.utils.errors import USER_MESSAGES, ProviderError
from recallpath.utils.schema import parse_json_object, sanitize_memory

SYSTEM_PROMPT = """You extract search clues from one personal photo memory.

Return one JSON object with these keys:
- user_stated: details the person stated as facts
- hedged: details they marked as unsure, including "I think", "maybe", "probably", "not sure", "might"
- ai_inferred: short paraphrases that stay tied to their words
- missing: useful details they did not provide

Each clue is an object with facet, text, and quote.
Facets: people, setting, objects, appearance, event, time, other.
ai_inferred also has basis and confidence (high, medium, or low).

Rules:
- Copy quotes from the person's words.
- A hedged detail must stay in hedged. Never copy it into user_stated as a fact.
- "I think it was Goa" is hedged text "Goa". It is not a known location.
- Do not invent a place, date, name, or object they did not mention.
- Do not turn "cousins" into a claim that specific faces are cousins.
- Vague time such as "a few years ago" is hedged.
- If the memory has no usable visual or situational detail, return empty lists.
- Return JSON only.
"""


def _user_prompt(memory_text: str) -> str:
    return (
        "Memory:\n"
        f'"""\n{memory_text.strip()}\n"""\n\n'
        "Return JSON with user_stated, hedged, ai_inferred, and missing. "
        "Keep uncertainty in the hedged list."
    )


def interpret_memory(memory_text: str, complete_fn) -> dict:
    text = (memory_text or "").strip()
    if not text:
        raise ProviderError("bad_request", "Describe the photo before it can be read.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(text)},
    ]
    for attempt in range(2):
        raw = complete_fn(messages)
        try:
            return sanitize_memory(parse_json_object(raw), text)
        except (ValueError, TypeError):
            if attempt == 1:
                break
            messages.append({
                "role": "user",
                "content": (
                    "That response was not usable. Return one JSON object with "
                    "user_stated, hedged, ai_inferred, and missing. "
                    "Put unsure details in hedged. Do not invent details."
                ),
            })
    raise ProviderError("bad_response", USER_MESSAGES["bad_response"])
