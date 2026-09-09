"""Narrow structural helpers for FF7R localized text resources.

Top-level text IDs are serialized as FStrings in the .uexp, so a new entry does
not require adding a package FName.  This helper appends only a plain top-level
entry with zero subentries, rebuilds the known FF7R text-resource payload, and
fully reparses it before accepting the mutation.
"""

from __future__ import annotations

from .textresource import MAX_ENTRIES, TextEntry, TextResourcePackage


TOP_LEVEL_TEXT_ENTRY_APPEND_SUPPORTED = True


def append_text_entry(package: TextResourcePackage, entry_id: str, text: str) -> int:
    """Append a unique top-level localized text entry and verify full readback."""
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("FF7R text entry ID must be a non-empty string")
    if "\0" in entry_id:
        raise ValueError("FF7R text entry ID cannot contain NUL characters")
    if not isinstance(text, str):
        raise TypeError("FF7R text entry value must be a string")
    if "\0" in text:
        raise ValueError("FF7R text entry value cannot contain NUL characters")
    if len(package.entries) >= MAX_ENTRIES:
        raise ValueError("FF7R text resource is already at the maximum supported entry count")
    if any(entry.id == entry_id for entry in package.entries):
        raise ValueError(f"FF7R text entry ID already exists: {entry_id}")

    old_uasset_bytes = bytearray(package.uasset_bytes)
    old_uexp_bytes = bytearray(package.uexp_bytes)
    old_entries = package.entries
    old_head = package.head
    old_language = package.language
    index = len(package.entries)
    try:
        package.entries = [*package.entries, TextEntry(entry_id, text, [])]
        package._rebuild()
        head, language, entries = package._parse_uexp(bytes(package.uexp_bytes))
        if head != package.head or language != package.language:
            raise RuntimeError("FF7R text entry append changed resource header/language")
        if len(entries) != index + 1:
            raise RuntimeError("FF7R text entry append failed entry-count readback")
        if entries[index].id != entry_id or entries[index].text != text or entries[index].subentries:
            raise RuntimeError("FF7R text entry append failed value readback")
        package.entries = entries
    except Exception:
        package.uasset_bytes = old_uasset_bytes
        package.uexp_bytes = old_uexp_bytes
        package.entries = old_entries
        package.head = old_head
        package.language = old_language
        raise
    return index
