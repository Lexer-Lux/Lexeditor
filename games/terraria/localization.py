"""Conservative structured editing for tModLoader HJSON localization files."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re


KNOWN_CULTURES = frozenset({
    "en-US", "de-DE", "it-IT", "fr-FR", "es-ES", "ru-RU",
    "zh-Hans", "pt-BR", "pl-PL", "ja-JP", "ko-KR", "zh-Hant",
})
_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


@dataclass(frozen=True)
class LocalizationEntry:
    key: str
    source_key: str
    value: str
    line: int
    editable: bool
    kind: str
    quote: str
    line_index: int
    token_start: int
    token_end: int

    def public(self) -> dict:
        return {
            "key": self.key,
            "sourceKey": self.source_key,
            "value": self.value,
            "line": self.line,
            "editable": self.editable,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class LocalizationDocument:
    entries: tuple[LocalizationEntry, ...]
    duplicates: tuple[str, ...]
    unsupported: int


def try_get_culture_and_prefix(path: str) -> tuple[str, str] | None:
    """Mirror tModLoader's culture/prefix inference for .hjson paths."""
    normalized = str(path).replace("\\", "/")
    if normalized.casefold().endswith(".hjson"):
        normalized = normalized[:-6]

    culture: str | None = None
    for path_part in normalized.split("/"):
        pieces = path_part.split("_")
        for index, piece in enumerate(pieces):
            if piece in KNOWN_CULTURES:
                culture = piece
                continue
            if culture is not None:
                return culture, "_".join(pieces[index:])
    if culture is not None:
        return culture, ""
    return None


def _line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def _comment_start(value: str) -> int | None:
    for index, character in enumerate(value):
        if character == "#" and (index == 0 or value[index - 1].isspace()):
            return index
        if value.startswith("//", index) and (index == 0 or value[index - 1].isspace()):
            return index
    return None


def _without_comment(value: str) -> str:
    comment = _comment_start(value)
    if comment is not None:
        value = value[:comment]
    return value.strip().removesuffix(",").rstrip()


def _decode_key(token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    if token.startswith('"'):
        try:
            value, end = json.JSONDecoder().raw_decode(token)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(value, str) or token[end:].strip():
            return None
        return value
    if token.startswith("'"):
        return None
    return token


def _effective_key(prefix: str, source_key: str) -> str:
    value = source_key.replace(".$parentVal", "")
    return f"{prefix}.{value}" if prefix else value


def _bare_safe(value: str) -> bool:
    if not value or value != value.strip() or "\r" in value or "\n" in value or "\x00" in value:
        return False
    if value[0] in "{[\"'" or "," in value or "#" in value:
        return False
    if re.search(r"\s//", value):
        return False
    if value in {"true", "false", "null"} or _NUMBER.fullmatch(value):
        return False
    return True


def _scalar_layout(body: str, colon: int) -> tuple[str, str, int, int, bool] | None:
    start = colon + 1
    while start < len(body) and body[start].isspace():
        start += 1
    if start >= len(body):
        return None

    tail = body[start:]
    if tail.startswith('"'):
        try:
            value, end = json.JSONDecoder().raw_decode(tail)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(value, str):
            return str(value), "typed", start, start + end, False
        suffix = tail[end:]
        suffix_check = _without_comment(suffix)
        if suffix_check:
            return value, "double", start, start + end, False
        return value, "double", start, start + end, True

    if tail.startswith("'''"):
        return None
    comment = _comment_start(tail)
    value_region = tail if comment is None else tail[:comment]
    trimmed = value_region.rstrip()
    if trimmed.endswith(","):
        trimmed = trimmed[:-1].rstrip()
    if not trimmed:
        return None
    token_end = start + len(trimmed)
    value = body[start:token_end]
    if value in {"true", "false", "null"} or _NUMBER.fullmatch(value):
        return value, "typed", start, token_end, False
    return value, "bare", start, token_end, True


def parse_localization_text(text: str, prefix: str = "") -> LocalizationDocument:
    """Flatten common tModLoader HJSON leaves without normalizing source text.

    Existing single-line string leaves are editable. Multiline strings and
    complex object/array expressions are surfaced read-only. This deliberately
    does not attempt to replace tModLoader's HJSON parser.
    """
    if "\x00" in text:
        raise ValueError("Localization file contains NUL bytes")

    lines = text.splitlines(keepends=True)
    stack: list[str] = []
    entries: list[LocalizationEntry] = []
    unsupported = 0
    multiline_key: tuple[str, int] | None = None
    multiline_lines: list[str] = []
    pending_key: tuple[str, int] | None = None
    complex_depth = 0

    for index, line in enumerate(lines):
        body, _ending = _line_ending(line)
        stripped = body.strip()

        if multiline_key is not None:
            if stripped == "'''":
                source_key, start_line = multiline_key
                entries.append(LocalizationEntry(
                    key=_effective_key(prefix, source_key),
                    source_key=source_key,
                    value="\n".join(multiline_lines),
                    line=start_line,
                    editable=False,
                    kind="multiline",
                    quote="triple",
                    line_index=index,
                    token_start=0,
                    token_end=0,
                ))
                multiline_key = None
                multiline_lines = []
            else:
                multiline_lines.append(body)
            continue

        if complex_depth:
            complex_depth += stripped.count("[") + stripped.count("{")
            complex_depth -= stripped.count("]") + stripped.count("}")
            if complex_depth <= 0:
                complex_depth = 0
            continue

        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        if pending_key is not None:
            if stripped == "'''":
                multiline_key = pending_key
                pending_key = None
                multiline_lines = []
                continue
            pending_key = None

        structural = _without_comment(stripped)
        if structural and set(structural) <= {"}"}:
            for _ in structural:
                if stack:
                    stack.pop()
                else:
                    unsupported += 1
            continue

        colon = body.find(":")
        if colon < 0:
            unsupported += 1
            continue
        key = _decode_key(body[:colon])
        if key is None:
            unsupported += 1
            continue
        source_key = ".".join((*stack, key)) if stack else key
        rhs = body[colon + 1 :]
        structural_rhs = _without_comment(rhs)

        if structural_rhs == "{":
            stack.append(key)
            continue
        if structural_rhs == "":
            pending_key = (source_key, index + 1)
            continue
        if structural_rhs.startswith("[") or (
            structural_rhs.startswith("{") and structural_rhs != "{"
        ):
            entries.append(LocalizationEntry(
                key=_effective_key(prefix, source_key),
                source_key=source_key,
                value=structural_rhs,
                line=index + 1,
                editable=False,
                kind="complex",
                quote="complex",
                line_index=index,
                token_start=0,
                token_end=0,
            ))
            complex_depth = max(
                0,
                structural_rhs.count("[") + structural_rhs.count("{")
                - structural_rhs.count("]") - structural_rhs.count("}"),
            )
            unsupported += 1
            continue
        if structural_rhs.startswith("'''"):
            entries.append(LocalizationEntry(
                key=_effective_key(prefix, source_key),
                source_key=source_key,
                value=structural_rhs,
                line=index + 1,
                editable=False,
                kind="multiline",
                quote="triple",
                line_index=index,
                token_start=0,
                token_end=0,
            ))
            unsupported += 1
            continue

        scalar = _scalar_layout(body, colon)
        if scalar is None:
            entries.append(LocalizationEntry(
                key=_effective_key(prefix, source_key),
                source_key=source_key,
                value=structural_rhs,
                line=index + 1,
                editable=False,
                kind="unsupported",
                quote="unsupported",
                line_index=index,
                token_start=0,
                token_end=0,
            ))
            unsupported += 1
            continue
        value, quote, token_start, token_end, editable = scalar
        entries.append(LocalizationEntry(
            key=_effective_key(prefix, source_key),
            source_key=source_key,
            value=value,
            line=index + 1,
            editable=editable,
            kind="string" if editable else "typed",
            quote=quote,
            line_index=index,
            token_start=token_start,
            token_end=token_end,
        ))
        if not editable:
            unsupported += 1

    if multiline_key is not None or pending_key is not None or stack:
        unsupported += 1

    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.key] = counts.get(entry.key, 0) + 1
    duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
    return LocalizationDocument(tuple(entries), duplicates, unsupported)


def update_localization_text(text: str, updates: dict[str, object], prefix: str = "") -> str:
    """Rewrite only existing editable localization leaf values."""
    if not isinstance(updates, dict):
        raise ValueError("Localization updates must be an object")
    if not updates:
        return text

    document = parse_localization_text(text, prefix)
    if document.duplicates:
        raise ValueError("Ambiguous duplicate localization keys: " + ", ".join(document.duplicates))
    by_key = {entry.key: entry for entry in document.entries}

    normalized: dict[str, str] = {}
    for key, value in updates.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Localization keys must be non-empty text")
        if not isinstance(value, str):
            raise ValueError(f"Localization value for {key} must be text")
        if "\r" in value or "\n" in value or "\x00" in value:
            raise ValueError(f"Localization value for {key} must fit on one line")
        entry = by_key.get(key)
        if entry is None:
            raise ValueError(f"Localization key is not present in this file: {key}")
        if not entry.editable:
            raise ValueError(f"Localization key is not safely editable: {key}")
        normalized[key] = value

    lines = text.splitlines(keepends=True)
    changed = False
    for key, value in normalized.items():
        entry = by_key[key]
        if value == entry.value:
            continue
        body, ending = _line_ending(lines[entry.line_index])
        serialized = (
            json.dumps(value, ensure_ascii=False)
            if entry.quote == "double" or not _bare_safe(value)
            else value
        )
        lines[entry.line_index] = (
            body[:entry.token_start] + serialized + body[entry.token_end:] + ending
        )
        changed = True
    return "".join(lines) if changed else text
