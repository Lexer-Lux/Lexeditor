"""Verify semantic low-to-high merge of FF8 menu text and refine recipes."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, mngrp_merge, mngrp_text, paths, refine_tables, runtime_layout  # noqa: E402


def main() -> int:
    vanilla = (paths.BASELINE_ROOT / "menu" / "mngrp.bin").read_bytes()
    text_row = mngrp_text.rows(vanilla)["rows"][0]
    text_value = text_row["value"] + "!"
    text_mod, _ = mngrp_text.apply_edits(vanilla, [{
        "source": "mngrp", "sectionId": text_row["sectionId"],
        "recordId": text_row["recordId"], "value": text_value,
    }])
    recipe = refine_tables.read(vanilla)["tables"][0]["rows"][0]
    quantity = recipe["inputQuantity"] + 1
    refine_mod, _ = refine_tables.apply_edits(vanilla, [{
        "table": "m000", "id": 0, "inputQuantity": quantity,
    }])

    merged, conflicts, fallback = mngrp_merge.merge(
        vanilla, [("text-mod", text_mod), ("refine-mod", refine_mod)],
        "direct/menu/mngrp.bin")
    assert merged is not None and not conflicts and not fallback
    merged_text = mngrp_text.rows(merged)["rows"][0]
    merged_recipe = refine_tables.read(merged)["tables"][0]["rows"][0]
    assert merged_text["value"] == text_value
    assert merged_recipe["inputQuantity"] == quantity

    competing, _ = refine_tables.apply_edits(vanilla, [{
        "table": "m000", "id": 0, "inputQuantity": quantity + 1,
    }])
    collided, conflicts, fallback = mngrp_merge.merge(
        vanilla, [("refine-mod", refine_mod), ("higher", competing)],
        "direct/menu/mngrp.bin")
    assert collided is not None and not fallback
    assert refine_tables.read(collided)["tables"][0]["rows"][0]["inputQuantity"] == quantity + 1
    assert conflicts == [{
        "unit": "direct/menu/mngrp.bin:refine:m000:record:0:inputQuantity",
        "winner": "higher", "claimants": ["refine-mod", "higher"],
    }]

    opaque = bytearray(refine_mod)
    opaque[0] ^= 1
    unsupported, conflicts, fallback = mngrp_merge.merge(
        vanilla, [("refine-mod", refine_mod), ("opaque", bytes(opaque))],
        "direct/menu/mngrp.bin")
    assert unsupported is None and not conflicts and "outside proved" in fallback

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mngrp-merge-") as name:
        root = Path(name)
        first, second, active = root / "first", root / "second", root / "active"
        for mod, mod_id, payload, order in (
                (first, "text-mod", text_mod, 0),
                (second, "refine-mod", refine_mod, 1)):
            target = mod / "direct" / "menu" / "mngrp.bin"
            target.parent.mkdir(parents=True)
            target.write_bytes(payload)
            (mod / runtime_layout.MOD_FILE).write_text(json.dumps({
                "id": mod_id, "name": mod_id, "enabled": True, "order": order,
            }), encoding="utf-8")
        rows = runtime_layout.catalog(first, root)
        runtime = runtime_layout.compose(
            first, active, rows, paths.BASELINE_ROOT, formats.SECTIONS)
        output = (active / "direct" / "menu" / "mngrp.bin").read_bytes()
        assert mngrp_text.rows(output)["rows"][0]["value"] == text_value
        assert refine_tables.read(output)["tables"][0]["rows"][0]["inputQuantity"] == quantity
        conflict = next(row for row in runtime["conflicts"]
                        if row["path"] == "direct/menu/mngrp.bin")
        assert conflict["winner"] == "semantic merge" and "semanticFallback" not in conflict

        (second / "direct" / "menu" / "mngrp.bin").write_bytes(bytes(opaque))
        fallback_runtime = runtime_layout.compose(
            first, active, rows, paths.BASELINE_ROOT, formats.SECTIONS)
        output = (active / "direct" / "menu" / "mngrp.bin").read_bytes()
        assert output == bytes(opaque)
        conflict = next(row for row in fallback_runtime["conflicts"]
                        if row["path"] == "direct/menu/mngrp.bin")
        assert conflict["winner"] == "refine-mod"
        assert "outside proved" in conflict["semanticFallback"]

    print({"independentUnitsCoexist": True, "higherUnitWins": True,
           "opaqueFallbackVisible": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
