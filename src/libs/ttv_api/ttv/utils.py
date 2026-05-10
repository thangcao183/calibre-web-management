from typing import Any

from .constants import UNICODE_ESCAPE_PATTERN


def decode_unicode_escapes(text: str) -> str:
    if not isinstance(text, str):
        return text
    if not UNICODE_ESCAPE_PATTERN.search(text):
        return text
    try:
        return bytes(text, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return text


def normalize_unicode(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize_unicode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_unicode(v) for v in value]
    if isinstance(value, str):
        return decode_unicode_escapes(value)
    return value


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
