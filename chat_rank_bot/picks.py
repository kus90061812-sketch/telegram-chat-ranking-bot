from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ParsedSlashCommand:
    argument: str
    argument_start: int


def parse_slash_command(text: str, command: str) -> ParsedSlashCommand | None:
    match = re.fullmatch(
        rf"/{re.escape(command)}(?:@[A-Za-z0-9_]+)?(?:\s+(?P<argument>[\s\S]*))?",
        text,
    )
    if not match:
        return None

    raw_argument = match.group("argument") or ""
    argument = raw_argument.strip()
    if not raw_argument:
        return ParsedSlashCommand("", len(text))

    left_trim = len(raw_argument) - len(raw_argument.lstrip())
    return ParsedSlashCommand(
        argument=argument,
        argument_start=match.start("argument") + left_trim,
    )


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset < 0:
        raise ValueError("UTF-16 offset cannot be negative")
    raw = text.encode("utf-16-le")
    boundary = offset * 2
    if boundary > len(raw):
        raise ValueError("UTF-16 offset is outside the text")
    return len(raw[:boundary].decode("utf-16-le"))


def custom_emoji_prefix_html(
    text: str,
    entities: Iterable[Any],
    command: str = "픽이모지설정",
) -> str:
    parsed = parse_slash_command(text, command)
    if parsed is None or not parsed.argument:
        raise ValueError("프리미엄 이모지를 함께 보내주세요.")

    argument_end = parsed.argument_start + len(parsed.argument)
    custom_entities: list[tuple[int, int, str]] = []
    for entity in entities:
        entity_type = getattr(entity.type, "value", entity.type)
        if entity_type != "custom_emoji" or not entity.custom_emoji_id:
            continue
        start = _utf16_offset_to_index(text, int(entity.offset))
        end = _utf16_offset_to_index(
            text, int(entity.offset) + int(entity.length)
        )
        if start < parsed.argument_start or end > argument_end:
            continue
        custom_entities.append(
            (
                start - parsed.argument_start,
                end - parsed.argument_start,
                str(entity.custom_emoji_id),
            )
        )

    if not custom_entities:
        raise ValueError("프리미엄 이모지가 인식되지 않았습니다.")

    parts: list[str] = []
    cursor = 0
    for start, end, custom_emoji_id in sorted(custom_entities):
        if start < cursor:
            raise ValueError("겹치는 프리미엄 이모지는 저장할 수 없습니다.")
        parts.append(html.escape(parsed.argument[cursor:start]))
        fallback = html.escape(parsed.argument[start:end])
        emoji_id = html.escape(custom_emoji_id, quote=True)
        parts.append(f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>')
        cursor = end
    parts.append(html.escape(parsed.argument[cursor:]))
    return "".join(parts)


def pick_message_html(prefix_html: str, content: str) -> str:
    return f"{prefix_html}\n\n{html.escape(content.strip())}"
