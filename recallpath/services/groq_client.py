"""Groq calls for RecallPath. The API key is never logged or returned to the UI."""

import base64

from recallpath.utils.config import (
    TEXT_MODEL,
    TEXT_TIMEOUT_SECONDS,
    VISION_MODEL,
    VISION_TIMEOUT_SECONDS,
    TEXT_MAX_TOKENS,
    VISION_MAX_TOKENS,
    get_groq_api_key,
    is_groq_configured,
)
from recallpath.utils.errors import (
    USER_MESSAGES,
    ProviderError,
    classify_exception,
    redact,
)


def complete_messages(model: str, messages: list, timeout: float, json_mode: bool = True, max_tokens: int = TEXT_MAX_TOKENS) -> str:
    if not is_groq_configured():
        raise ProviderError("missing_key", USER_MESSAGES["missing_key"])
    try:
        from groq import Groq

        client = Groq(api_key=get_groq_api_key(), timeout=timeout, max_retries=0)
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message if response.choices else None
        content = _message_text(message)
        if not content.strip():
            raise ProviderError("bad_response", USER_MESSAGES["bad_response"])
        return content
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError(classify_exception(exc), redact(f"{type(exc).__name__}: {exc}")) from None


def complete_text(messages: list) -> str:
    return complete_messages(TEXT_MODEL, messages, TEXT_TIMEOUT_SECONDS, True, TEXT_MAX_TOKENS)


def complete_vision(messages: list) -> str:
    try:
        return complete_messages(VISION_MODEL, messages, VISION_TIMEOUT_SECONDS, True, VISION_MAX_TOKENS)
    except ProviderError as exc:
        if exc.kind != "bad_request":
            raise
        return complete_messages(VISION_MODEL, messages, VISION_TIMEOUT_SECONDS, False, VISION_MAX_TOKENS)


def vision_user_content(prompt: str, images: list) -> list:
    if len(images) > 3:
        raise ProviderError("bad_request", "A vision request was blocked because it included more than 3 photos.")
    content = [{"type": "text", "text": prompt}]
    for image in images:
        encoded = base64.b64encode(image["bytes"]).decode("ascii")
        mime = image.get("mime") or "image/jpeg"
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{encoded}"},
        })
    return content


def _message_text(message) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content and str(content).strip():
        return str(content)
    for attr in ("reasoning", "reasoning_content"):
        extra = getattr(message, attr, None)
        if extra and str(extra).strip():
            return str(extra)
    return ""
