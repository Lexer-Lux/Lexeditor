"""Three-way, priority-ordered merge for FF8 kernel.bin.

The kernel is not an opaque file. Fixed data records and linked text entries
are independent change units. This lets two mods edit different spells or
fields even though both distribute a complete kernel.bin.
"""

from __future__ import annotations

from . import kernel_text


def _sections(data: bytes, definitions: dict[int, dict]) -> list[bytes]:
    return kernel_text._split_sections(data, len(definitions))[0]


def _record_count(payload: bytes, definition: dict) -> int:
    size = int(definition["sub_section_size"])
    if len(payload) % size:
        raise ValueError(f"Kernel section {definition['id']} has a partial record")
    count = len(payload) // size
    expected = int(definition["number_sub_section"])
    if count != expected and (not definition.get("growable") or count < expected):
        raise ValueError(f"Kernel section {definition['id']} has an unsupported record count")
    return count


def _offset_positions(definition: dict) -> set[int]:
    positions: set[int] = set()
    for slot in range(int(definition.get("sub_section_nb_text_offset", 0))):
        positions.update((slot * 2, slot * 2 + 1))
    return positions


def _text_map(data: bytes, definitions: dict[int, dict]) -> dict[tuple[int, int, int], str]:
    return {
        (int(row["sectionId"]), int(row["recordId"]), int(row["slot"])): str(row["value"])
        for row in kernel_text.rows(data, definitions)["rows"]
    }


def _rebuild(payloads: list[bytes]) -> bytes:
    header_size = (len(payloads) + 1) * 4
    starts = []
    cursor = header_size
    for payload in payloads:
        starts.append(cursor)
        cursor += len(payload)
    return (len(payloads).to_bytes(4, "little")
            + b"".join(start.to_bytes(4, "little") for start in starts)
            + b"".join(payloads))


def merge(vanilla: bytes, mods: list[tuple[str, bytes]],
          definitions: dict[int, dict]) -> tuple[bytes, list[dict]]:
    """Apply complete mod kernels from low to high priority."""
    if not mods:
        return vanilla, []
    vanilla_sections = _sections(vanilla, definitions)
    parsed = [(mod_id, data, _sections(data, definitions), _text_map(data, definitions))
              for mod_id, data in mods]
    vanilla_text = _text_map(vanilla, definitions)

    # A growable section needs a real record and linked-text donor. Use the
    # highest-priority kernel with the largest supported shape, then restore
    # every unchanged vanilla unit below.
    donor_id, donor_data, donor_sections, donor_text = parsed[0]
    for candidate in parsed[1:]:
        if len(candidate[2][1]) >= len(donor_sections[1]):
            donor_id, donor_data, donor_sections, donor_text = candidate
    output = [bytearray(payload) for payload in donor_sections]
    conflicts: list[dict] = []
    claims: dict[str, list[tuple[str, object]]] = {}

    for section_id in range(1, len(definitions) + 1):
        definition = definitions[section_id]
        if definition.get("type") != "data":
            continue
        size = int(definition["sub_section_size"])
        vanilla_payload = vanilla_sections[section_id - 1]
        vanilla_count = _record_count(vanilla_payload, definition)
        counts = [_record_count(item[2][section_id - 1], definition) for item in parsed]
        target_count = max([vanilla_count, *counts])
        if not definition.get("growable") and target_count != vanilla_count:
            raise ValueError(f"Kernel section {section_id} cannot change record count")
        donor_payload = donor_sections[section_id - 1]
        if len(donor_payload) < target_count * size:
            donor_payload = next(item[2][section_id - 1] for item in reversed(parsed)
                                 if len(item[2][section_id - 1]) >= target_count * size)
        result = bytearray(donor_payload[:target_count * size])
        offsets = _offset_positions(definition)
        for record_id in range(target_count):
            for relative in range(size):
                if relative in offsets:
                    continue
                key = f"kernel:section:{section_id}:record:{record_id}:byte:{relative}"
                baseline = (vanilla_payload[record_id * size + relative]
                            if record_id < vanilla_count else None)
                winner = baseline
                for (mod_id, _data, sections, _texts), count in zip(parsed, counts):
                    if record_id >= count:
                        continue
                    value = sections[section_id - 1][record_id * size + relative]
                    if baseline is None or value != baseline:
                        claims.setdefault(key, []).append((mod_id, value))
                        winner = value
                if winner is None:
                    raise ValueError(f"No kernel donor for section {section_id} record {record_id}")
                result[record_id * size + relative] = int(winner)
        output[section_id - 1] = result

    chosen_text: dict[tuple[int, int, int], str] = {}
    all_text_keys = set(vanilla_text)
    for _mod_id, _data, _sections_value, texts in parsed:
        all_text_keys.update(texts)
    for key in sorted(all_text_keys):
        baseline = vanilla_text.get(key)
        winner = baseline
        claim_key = f"kernel:text:{key[0]}:{key[1]}:{key[2]}"
        for mod_id, _data, _sections_value, texts in parsed:
            if key not in texts:
                continue
            value = texts[key]
            if baseline is None or value != baseline:
                claims.setdefault(claim_key, []).append((mod_id, value))
                winner = value
        if winner is not None:
            chosen_text[key] = winner

    # The donor owns valid linked offsets for every expanded record. Rebuild
    # once with the merged values so all offsets and top-level starts are fresh.
    provisional = _rebuild([bytes(payload) for payload in output])
    current_text = _text_map(provisional, definitions)
    edits = [
        {"sectionId": key[0], "recordId": key[1], "slot": key[2], "value": value}
        for key, value in chosen_text.items() if current_text.get(key) != value
    ]
    merged, _ = kernel_text.apply_edits(provisional, definitions, edits)

    for key, values in sorted(claims.items()):
        unique = []
        for mod_id, value in values:
            if not any(existing[0] == mod_id for existing in unique):
                unique.append((mod_id, value))
        if len(unique) > 1 and len({repr(value) for _, value in unique}) > 1:
            conflicts.append({
                "unit": key,
                "winner": unique[-1][0],
                "claimants": [mod_id for mod_id, _ in unique],
            })
    return merged, conflicts
