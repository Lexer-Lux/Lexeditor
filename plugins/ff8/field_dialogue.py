"""Strict reader and writer for one FF8 PC field-map MSD file.

Deling's ``MsdFile`` and OpenVIII's ``Msd.Reader`` independently describe the
same layout: the first little-endian u32 is both the first string offset and
four times the string count.  The remaining u32 values are string offsets.
Each range may end in a null byte; duplicate offsets represent empty strings.

Unchanged payloads remain byte-identical.  A changed string uses Lexeditor's
strict FF8 code page and retains that entry's original terminator policy.
"""

from __future__ import annotations

import struct

from . import kernel_text, japanese_text


def _codec(map_name: str):
    # This unused map retains Japanese developer dialogue in the English archive.
    return japanese_text if map_name.casefold() == "bccent12" else kernel_text


def _layout(raw: bytes, map_name: str = "") -> dict:
    if not raw:
        return {"lines": [], "headerSize": 0}
    if len(raw) < 4:
        raise ValueError("Field dialogue MSD is shorter than its first offset")
    first = struct.unpack_from("<I", raw, 0)[0]
    if first < 4 or first % 4 or first > len(raw):
        raise ValueError("Field dialogue MSD has an invalid first offset")
    count = first // 4
    if count * 4 > len(raw):
        raise ValueError("Field dialogue MSD offset table exceeds the file")
    offsets = list(struct.unpack_from(f"<{count}I", raw, 0))
    if offsets[0] != first or offsets != sorted(offsets):
        raise ValueError("Field dialogue MSD offsets are not monotonic")
    if any(offset < first or offset > len(raw) for offset in offsets):
        raise ValueError("Field dialogue MSD has an out-of-range text offset")
    lines = []
    for line_id, start in enumerate(offsets):
        end = offsets[line_id + 1] if line_id + 1 < count else len(raw)
        if end < start:
            raise ValueError("Field dialogue MSD text ranges overlap")
        payload = raw[start:end]
        terminated = bool(payload) and payload[-1] == 0
        text_raw = payload[:-1] if terminated else payload
        if b"\0" in text_raw:
            raise ValueError("Field dialogue MSD has data after a string terminator")
        lines.append({
            "id": line_id,
            "text": _codec(map_name).decode(text_raw),
            "rawText": text_raw.hex(),
            "terminated": terminated,
            "offset": start,
            "storedSize": len(payload),
        })
    return {"lines": lines, "headerSize": first}


def read(raw: bytes, *, map_name: str = "") -> dict:
    return _layout(raw, map_name)


def apply_edits(raw: bytes, edits: list[dict], *, map_name: str = "") -> tuple[bytes, int]:
    document = _layout(raw, map_name)
    lines = document["lines"]
    if not edits:
        return raw, 0
    seen: set[int] = set()
    replacements: dict[int, str] = {}
    for edit in edits:
        line_id = int(edit.get("id", -1))
        if line_id in seen or not 0 <= line_id < len(lines):
            raise ValueError("Invalid or duplicate field dialogue line edit")
        if set(edit) - {"id", "text"}:
            raise ValueError("Field dialogue edit contains an unsupported field")
        seen.add(line_id)
        replacements[line_id] = str(edit.get("text", ""))

    payloads: list[bytes] = []
    changed = 0
    for line in lines:
        replacement = replacements.get(line["id"])
        if replacement is not None and replacement != line["text"]:
            encoded = _codec(map_name).encode(replacement)
            changed += 1
        else:
            encoded = bytes.fromhex(line["rawText"])
        payloads.append(encoded + (b"\0" if line["terminated"] else b""))
    if not changed:
        return raw, 0
    header_size = len(lines) * 4
    cursor = header_size
    offsets = []
    for payload in payloads:
        offsets.append(cursor)
        cursor += len(payload)
        if cursor > 0xFFFFFFFF:
            raise ValueError("Field dialogue MSD exceeds its 32-bit offset range")
    rebuilt = struct.pack(f"<{len(offsets)}I", *offsets) + b"".join(payloads)
    reparsed = _layout(rebuilt, map_name)
    if len(reparsed["lines"]) != len(lines):
        raise ValueError("Field dialogue line count changed during save")
    return rebuilt, changed


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], path: str, *,
          map_name: str = "") -> tuple[bytes | None, list[dict], str]:
    """Merge dialogue lines, or return a visible whole-file fallback."""
    try:
        baseline = read(vanilla, map_name=map_name)["lines"]
    except ValueError as error:
        return None, [], f"vanilla {path} is unsupported: {error}"
    claims: dict[int, list[tuple[str, str]]] = {}
    for mod_id, source in mods:
        try:
            lines = read(source, map_name=map_name)["lines"]
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if len(lines) != len(baseline):
            return None, [], f"{mod_id} changes the dialogue line count of {path}"
        changed = [{"id": line["id"], "text": line["text"]}
                   for line, base in zip(lines, baseline)
                   if line["text"] != base["text"]]
        for edit in changed:
            claims.setdefault(edit["id"], []).append((mod_id, edit["text"]))
        try:
            reconstructed, _ = apply_edits(vanilla, changed, map_name=map_name)
        except ValueError as error:
            return None, [], f"{mod_id} is not a supported {path}: {error}"
        if reconstructed != source:
            return None, [], f"{mod_id} contains changes outside proved dialogue lines"
    winners = {line_id: values[-1][1] for line_id, values in claims.items()}
    output, _ = apply_edits(
        vanilla, [{"id": line_id, "text": text} for line_id, text in winners.items()],
        map_name=map_name)
    conflicts = [
        {"unit": f"{path}:line:{line_id}", "winner": values[-1][0],
         "claimants": [mod_id for mod_id, _ in values]}
        for line_id, values in claims.items()
        if len(values) > 1 and len({value for _, value in values}) > 1
    ]
    read(output, map_name=map_name)
    return output, conflicts, ""
