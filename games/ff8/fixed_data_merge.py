"""Three-way merge for FF8's fixed-record data files."""

from __future__ import annotations


SPECS = {
    "direct/menu/price.bin": {"baseline": "menu/price.bin", "record": 4,
        "fields": (("buy_price", 0, 2), ("sell_multiplier", 2, 1), ("unknown_3", 3, 1))},
    "direct/menu/mitem.bin": {"baseline": "menu/mitem.bin", "record": 4,
        "fields": (("type", 0, 1), ("flags", 1, 1), ("param_1", 2, 1), ("param_2", 3, 1)),
        "bits": {1}},
    "direct/menu/shop.bin": {"baseline": "menu/shop.bin", "record": 2,
        "fields": (("item", 0, 1), ("rare", 1, 1))},
    "direct/menu/mwepon.bin": {"baseline": "menu/mwepon.bin", "record": 12,
        "fields": (("unknown_0", 0, 1), ("unknown_1", 1, 1), ("unknown_2", 2, 1),
                   ("price", 3, 1), ("item_1", 4, 1), ("quantity_1", 5, 1),
                   ("item_2", 6, 1), ("quantity_2", 7, 1), ("item_3", 8, 1),
                   ("quantity_3", 9, 1), ("item_4", 10, 1), ("quantity_4", 11, 1))},
    "direct/battle/scene.out": {"baseline": "battle/scene.out", "record": 128,
        "fields": tuple(
            [(name, offset, 1) for offset, name in enumerate(
                ("stage", "flags", "camera_main", "camera_secondary"))]
            + [(name, offset, 1) for offset, name in enumerate(
                ("not_visible", "not_loaded", "not_targetable", "enabled"), 4)]
            + [(f"slot_{slot}_{axis}", 8 + slot * 6 + axis_index * 2, 2)
               for slot in range(8) for axis_index, axis in enumerate(("x", "y", "z"))]
            + [(f"slot_{slot}_enemy", 0x38 + slot, 1) for slot in range(8)]
            + [(f"unknown_{offset:02x}", offset, 1) for offset in range(0x40, 0x78)]
            + [(f"slot_{slot}_level", 0x78 + slot, 1) for slot in range(8)]),
        "bits": {4, 5, 6, 7}},
}


def merge(vanilla: bytes, mods: list[tuple[str, bytes]], spec: dict,
          path: str) -> tuple[bytes, list[dict]]:
    record_size = int(spec["record"])
    if len(vanilla) % record_size:
        raise ValueError(f"Vanilla {path} has a partial record")
    for mod_id, data in mods:
        if len(data) != len(vanilla):
            raise ValueError(f"{mod_id} changes the fixed size of {path}")
    output = bytearray(vanilla)
    conflicts = []
    bit_offsets = set(spec.get("bits", set()))
    record_count = len(vanilla) // record_size
    for record_id in range(record_count):
        base = record_id * record_size
        for name, relative, size in spec["fields"]:
            if relative in bit_offsets and size == 1:
                for bit in range(8):
                    baseline = bool(vanilla[base + relative] & (1 << bit))
                    claims = [(mod_id, bool(data[base + relative] & (1 << bit)))
                              for mod_id, data in mods
                              if bool(data[base + relative] & (1 << bit)) != baseline]
                    if not claims:
                        continue
                    if claims[-1][1]:
                        output[base + relative] |= 1 << bit
                    else:
                        output[base + relative] &= ~(1 << bit)
                    if len(claims) > 1 and len({value for _, value in claims}) > 1:
                        conflicts.append({"unit": f"{path}:record:{record_id}:{name}:bit:{bit}",
                                          "winner": claims[-1][0],
                                          "claimants": [mod_id for mod_id, _ in claims]})
                continue
            baseline = vanilla[base + relative:base + relative + size]
            claims = [(mod_id, data[base + relative:base + relative + size])
                      for mod_id, data in mods
                      if data[base + relative:base + relative + size] != baseline]
            if not claims:
                continue
            output[base + relative:base + relative + size] = claims[-1][1]
            if len(claims) > 1 and len({value for _, value in claims}) > 1:
                conflicts.append({"unit": f"{path}:record:{record_id}:{name}",
                                  "winner": claims[-1][0],
                                  "claimants": [mod_id for mod_id, _ in claims]})
    return bytes(output), conflicts
