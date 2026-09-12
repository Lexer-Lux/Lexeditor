"""Conservative structured editing for tModLoader build.txt files."""

from __future__ import annotations

from dataclasses import dataclass
import re


BOOLEAN_KEYS = frozenset({
    "noCompile",
    "playableOnPreview",
    "translationMod",
    "hideCode",
    "hideResources",
    "includeSource",
})
SIDE_VALUES = ("Both", "Client", "Server", "NoSync")
SCALAR_KEYS = frozenset({"author", "version", "displayName", "homepage", "side"}) | BOOLEAN_KEYS
EDITABLE_KEYS = SCALAR_KEYS
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")


@dataclass(frozen=True)
class BuildMetadata:
    values: dict[str, str]
    duplicates: tuple[str, ...]


def _line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def _property(line: str) -> tuple[str, str] | None:
    body, _ending = _line_ending(line)
    split = body.find("=")
    if split < 0:
        return None
    key = body[:split].strip()
    value = body[split + 1 :].strip()
    if not key or not value:
        return None
    return key, value


def parse_build_text(text: str) -> BuildMetadata:
    """Read recognized scalar metadata while retaining duplicate diagnostics.

    tModLoader itself ignores blank/no-equals/unknown lines. Lexeditor mirrors that
    read behavior, but refuses ambiguous structured writes when a target key occurs
    more than once.
    """
    if "\x00" in text:
        raise ValueError("build.txt contains NUL bytes")

    values: dict[str, str] = {}
    counts: dict[str, int] = {}
    for line in text.splitlines(keepends=True):
        parsed = _property(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in EDITABLE_KEYS:
            continue
        values[key] = value  # tModLoader's sequential parser is effectively last-wins.
        counts[key] = counts.get(key, 0) + 1

    duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
    return BuildMetadata(values=values, duplicates=duplicates)


def _normalize(key: str, value: object) -> str:
    if key not in EDITABLE_KEYS:
        raise ValueError(f"Unsupported structured build.txt key: {key}")

    if key in BOOLEAN_KEYS:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.casefold() in {"true", "false"}:
            return value.casefold()
        raise ValueError(f"{key} must be true or false")

    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{key} cannot be empty")
    if "\r" in normalized or "\n" in normalized or "\x00" in normalized:
        raise ValueError(f"{key} must fit on one build.txt line")

    if key == "side":
        matches = {candidate.casefold(): candidate for candidate in SIDE_VALUES}
        try:
            return matches[normalized.casefold()]
        except KeyError as error:
            raise ValueError("side must be one of Both, Client, Server, NoSync") from error

    if key == "version":
        if not _VERSION.fullmatch(normalized):
            raise ValueError("version must contain 2 to 4 non-negative numeric components")
        components = [int(part) for part in normalized.split(".")]
        if any(part > 2_147_483_647 for part in components):
            raise ValueError("version component exceeds System.Version range")

    return normalized


def update_build_text(text: str, updates: dict[str, object]) -> str:
    """Apply scalar edits without rewriting unrelated build.txt content."""
    if "\x00" in text:
        raise ValueError("build.txt contains NUL bytes")
    if not updates:
        return text

    normalized = {key: _normalize(key, value) for key, value in updates.items()}
    lines = text.splitlines(keepends=True)
    occurrences: dict[str, list[int]] = {key: [] for key in normalized}
    for index, line in enumerate(lines):
        parsed = _property(line)
        if parsed is not None and parsed[0] in occurrences:
            occurrences[parsed[0]].append(index)

    duplicate_targets = sorted(key for key, indexes in occurrences.items() if len(indexes) > 1)
    if duplicate_targets:
        raise ValueError("Ambiguous duplicate build.txt keys: " + ", ".join(duplicate_targets))

    changed = False
    for key, value in normalized.items():
        indexes = occurrences[key]
        if indexes:
            index = indexes[0]
            body, ending = _line_ending(lines[index])
            split = body.find("=")
            right = body[split + 1 :]
            leading = right[: len(right) - len(right.lstrip())]
            trailing = right[len(right.rstrip()) :]
            replacement = body[: split + 1] + leading + value + trailing + ending
            if replacement != lines[index]:
                lines[index] = replacement
                changed = True
            continue

        newline = "\r\n" if "\r\n" in text else "\n"
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += newline
        lines.append(f"{key} = {value}{newline}")
        changed = True

    result = "".join(lines)
    return result if changed else text
