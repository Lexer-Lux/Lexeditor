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
LIST_KEYS = frozenset({
    "dllReferences",
    "modReferences",
    "weakReferences",
    "sortBefore",
    "sortAfter",
    "buildIgnore",
})
REFERENCE_KEYS = frozenset({"modReferences", "weakReferences"})
SIDE_VALUES = ("Both", "Client", "Server", "NoSync")
SCALAR_KEYS = frozenset({"author", "version", "displayName", "homepage", "side"}) | BOOLEAN_KEYS
EDITABLE_KEYS = SCALAR_KEYS | LIST_KEYS
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")


@dataclass(frozen=True)
class BuildMetadata:
    values: dict[str, object]
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


def _read_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_build_text(text: str) -> BuildMetadata:
    """Read recognized metadata while retaining duplicate diagnostics.

    tModLoader itself ignores blank/no-equals/unknown lines. Lexeditor mirrors that
    read behavior, but refuses ambiguous structured writes when a modeled key occurs
    more than once.
    """
    if "\x00" in text:
        raise ValueError("build.txt contains NUL bytes")

    values: dict[str, object] = {}
    counts: dict[str, int] = {}
    for line in text.splitlines(keepends=True):
        parsed = _property(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in EDITABLE_KEYS:
            continue
        values[key] = _read_list(value) if key in LIST_KEYS else value
        counts[key] = counts.get(key, 0) + 1

    duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
    return BuildMetadata(values=values, duplicates=duplicates)


def _normalize_version(value: str, label: str = "version") -> str:
    if not _VERSION.fullmatch(value):
        raise ValueError(f"{label} must contain 2 to 4 non-negative numeric components")
    components = [int(part) for part in value.split(".")]
    if any(part > 2_147_483_647 for part in components):
        raise ValueError(f"{label} component exceeds System.Version range")
    return value


def _parse_mod_reference(spec: str) -> tuple[str, str | None]:
    parts = spec.split("@")
    if len(parts) == 1:
        return parts[0], None
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid mod reference: {spec}")
    return parts[0], _normalize_version(parts[1], f"Reference version for {parts[0]}")


def _normalize_list(key: str, value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{key} entries must be text")
        entry = item.strip()
        if not entry:
            continue
        if any(character in entry for character in (",", "\r", "\n", "\x00")):
            raise ValueError(f"{key} entries cannot contain commas, newlines, or NUL bytes")
        if key in REFERENCE_KEYS:
            _parse_mod_reference(entry)
        normalized.append(entry)
    return normalized


def _normalize(key: str, value: object) -> object:
    if key not in EDITABLE_KEYS:
        raise ValueError(f"Unsupported structured build.txt key: {key}")

    if key in LIST_KEYS:
        return _normalize_list(key, value)

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
        return _normalize_version(normalized)

    return normalized


def _validate_reference_constraints(values: dict[str, object]) -> None:
    strong_specs = list(values.get("modReferences", []))
    weak_specs = list(values.get("weakReferences", []))
    dll_references = list(values.get("dllReferences", []))

    strong_names = [_parse_mod_reference(str(spec))[0] for spec in strong_specs]
    weak_names = [_parse_mod_reference(str(spec))[0] for spec in weak_specs]
    reference_names = strong_names + weak_names

    if len(reference_names) != len(set(reference_names)):
        raise ValueError("Duplicate mod/weak reference")
    if set(dll_references).intersection(strong_names):
        raise ValueError("dllReferences contains duplicate of modReferences")


def _same_value(key: str, current: str, normalized: object) -> bool:
    if key in LIST_KEYS:
        return _read_list(current) == normalized
    if key in BOOLEAN_KEYS:
        return current.casefold() == normalized
    return current == normalized


def update_build_text(text: str, updates: dict[str, object]) -> str:
    """Apply modeled edits without rewriting unrelated build.txt content."""
    if "\x00" in text:
        raise ValueError("build.txt contains NUL bytes")
    if not updates:
        return text

    parsed = parse_build_text(text)
    if parsed.duplicates:
        raise ValueError("Ambiguous duplicate build.txt keys: " + ", ".join(parsed.duplicates))

    normalized = {key: _normalize(key, value) for key, value in updates.items()}
    candidate = dict(parsed.values)
    candidate.update(normalized)
    _validate_reference_constraints(candidate)

    lines = text.splitlines(keepends=True)
    occurrences: dict[str, list[int]] = {key: [] for key in normalized}
    for index, line in enumerate(lines):
        property_value = _property(line)
        if property_value is not None and property_value[0] in occurrences:
            occurrences[property_value[0]].append(index)

    changed = False
    for key, value in normalized.items():
        indexes = occurrences[key]
        if key in LIST_KEYS and not value:
            if indexes:
                lines[indexes[0]] = ""
                changed = True
            continue

        serialized = ", ".join(value) if key in LIST_KEYS else str(value)
        if indexes:
            index = indexes[0]
            property_value = _property(lines[index])
            assert property_value is not None
            if _same_value(key, property_value[1], value):
                continue
            body, ending = _line_ending(lines[index])
            split = body.find("=")
            right = body[split + 1 :]
            leading = right[: len(right) - len(right.lstrip())]
            trailing = right[len(right.rstrip()) :]
            lines[index] = body[: split + 1] + leading + serialized + trailing + ending
            changed = True
            continue

        newline = "\r\n" if "\r\n" in text else "\n"
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += newline
        lines.append(f"{key} = {serialized}{newline}")
        changed = True

    result = "".join(lines)
    return result if changed else text
