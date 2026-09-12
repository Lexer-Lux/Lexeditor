"""Safe localization transactions layered over the preservation-first HJSON editor."""

from __future__ import annotations

from .localization import apply_localization_changes as _apply_localization_changes
from .localization import parse_localization_text


def delete_localization_entries(text: str, deletes: object, prefix: str = "") -> str:
    """Delete whole source lines for existing editable scalar leaves only."""
    if not isinstance(deletes, (list, tuple, set)):
        raise ValueError("Localization deletes must be a list")
    keys = list(dict.fromkeys(deletes))
    if any(not isinstance(key, str) or not key for key in keys):
        raise ValueError("Localization delete keys must be non-empty text")
    if not keys:
        return text

    document = parse_localization_text(text, prefix)
    if document.duplicates:
        raise ValueError("Ambiguous duplicate localization keys: " + ", ".join(document.duplicates))
    by_key = {entry.key: entry for entry in document.entries}
    selected = []
    for key in keys:
        entry = by_key.get(key)
        if entry is None:
            raise ValueError(f"Localization key is not present in this file: {key}")
        if not entry.editable:
            raise ValueError(f"Localization key is not safely deletable: {key}")
        selected.append(entry)

    lines = text.splitlines(keepends=True)
    for entry in sorted(selected, key=lambda value: value.line_index, reverse=True):
        del lines[entry.line_index]
    changed = "".join(lines)

    remaining = {entry.key for entry in parse_localization_text(changed, prefix).entries}
    if any(key in remaining for key in keys):
        raise ValueError("Could not safely delete localization key")
    return changed


def apply_localization_transaction(
    text: str,
    updates: dict[str, object],
    creates: dict[str, object],
    deletes: object = (),
    prefix: str = "",
) -> str:
    """Apply edits, deletions and creations without allowing contradictory operations."""
    if not isinstance(updates, dict):
        raise ValueError("Localization updates must be an object")
    if not isinstance(creates, dict):
        raise ValueError("Localization creates must be an object")
    if not isinstance(deletes, (list, tuple, set)):
        raise ValueError("Localization deletes must be a list")
    delete_keys = set(deletes)
    overlap = (
        set(updates).intersection(creates)
        | set(updates).intersection(delete_keys)
        | set(creates).intersection(delete_keys)
    )
    if overlap:
        raise ValueError("Localization keys cannot have multiple operations: " + ", ".join(sorted(overlap)))

    changed = _apply_localization_changes(text, updates, {}, prefix)
    changed = delete_localization_entries(changed, deletes, prefix)
    return _apply_localization_changes(changed, {}, creates, prefix)
