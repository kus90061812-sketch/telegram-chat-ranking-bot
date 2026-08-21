from __future__ import annotations

import hashlib
import re
import unicodedata


MEANINGFUL_CHARACTER = re.compile(
    r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff\ua960-\ua97f\ud7b0-\ud7ff]"
)
COMPLETE_CHARACTER = re.compile(r"[0-9A-Za-z가-힣]")
WHITESPACE = re.compile(r"\s+")


def normalized_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    return WHITESPACE.sub(" ", normalized)


def is_countable_text(text: str | None, min_length: int) -> bool:
    if not text or text.lstrip().startswith(("/", ".")):
        return False
    normalized = normalized_text(text)
    compact = normalized.replace(" ", "")
    if len(compact) < min_length:
        return False
    return (
        MEANINGFUL_CHARACTER.search(compact) is not None
        and COMPLETE_CHARACTER.search(compact) is not None
    )


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalized_text(text).encode("utf-8")).hexdigest()


def dot_command(text: str) -> str | None:
    first = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
    return first if first.startswith(".") else None
