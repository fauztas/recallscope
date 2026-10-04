"""Safe error types for RecallPath. Messages shown to people are fixed sentences."""

import re


class ProviderError(RuntimeError):
    """A model call failed. `kind` is a short code. `message` is already redacted."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


USER_MESSAGES = {
    "missing_key": "A Groq API key is not configured, so nothing was analysed and nothing was invented.",
    "invalid_key": "The Groq key was rejected. It is not shown here. Nothing was invented in its place.",
    "timeout": "The AI service took too long. Photos that did not come back were left blank. Nothing was invented.",
    "rate_limit": "The AI service is limiting requests right now. Photos already described are kept. The rest were not guessed.",
    "bad_response": "The AI reply was not usable. No missing description was filled in.",
    "bad_request": "The AI service rejected the request. No description was invented.",
    "api_error": "The AI service returned an error. No description was invented.",
}


def public_message(error: ProviderError) -> str:
    return USER_MESSAGES.get(error.kind, USER_MESSAGES["api_error"])


def public_detail(text: str) -> str:
    cleaned = redact(text)
    lowered = cleaned.lower()
    if "gsk_" in lowered or "base64," in lowered:
        return ""
    return cleaned


def redact(text: str) -> str:
    """Remove keys, image payloads, and long encoded blobs from an error string."""
    cleaned = text or ""
    cleaned = re.sub(r"gsk_[A-Za-z0-9_\-]+", "[REDACTED]", cleaned)
    cleaned = re.sub(r"org_[A-Za-z0-9]+", "[account]", cleaned)
    cleaned = re.sub(
        r"(?i)(api[_-]?key['\"\s:=]+)[^\s'\"]+",
        r"\1[REDACTED]",
        cleaned,
    )
    cleaned = re.sub(
        r"data:image/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=\r\n]+",
        "[image omitted]",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[A-Za-z0-9+/]{100,}={0,2}", "[omitted]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:240]


def classify_exception(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "too large" in text:
        return "bad_request"
    if "ratelimit" in name or "rate limit" in text or "429" in text:
        return "rate_limit"
    if "timeout" in name or "timed out" in text:
        return "timeout"
    if "authentication" in name or "401" in text:
        return "invalid_key"
    if "badrequest" in name or "400" in text:
        return "bad_request"
    return "api_error"
