"""Per-name merge for namedic.bin: independent names coexist, collisions follow priority."""
import json
import struct

from plugins.ff8 import kernel_text, namedic, runtime_layout

PATH = "direct/namedic.bin"


def _namedic(names, padding=()):
    encoded = [kernel_text.encode(name, compress=False) + b"\x00"
               + b"\x00" * pad for name, pad in
               zip(names, list(padding) + [0] * len(names))]
    header = len(encoded) * 2 + 2
    offsets = []
    position = header
    for payload in encoded:
        offsets.append(position)
        position += len(payload)
    return (struct.pack("<H", len(names)) + struct.pack(f"<{len(names)}H", *offsets)
            + b"".join(encoded))


def _texts(raw):
    return [entry["text"] for entry in namedic.parse(raw)["entries"]]


def test_independent_names_coexist():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    first = namedic.apply_edits(vanilla, [{"index": 0, "text": "Galbadia Region"}])
    second = namedic.apply_edits(vanilla, [{"index": 2, "text": "Balamb Town"}])
    merged, conflicts, fallback = namedic.merge(
        vanilla, [("first", first), ("second", second)], PATH)
    assert not fallback and not conflicts
    assert _texts(merged) == ["Galbadia Region", "Esthar", "Balamb Town"]


def test_collision_follows_priority_with_conflict_unit():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    low = namedic.apply_edits(vanilla, [{"index": 1, "text": "Esthar City"}])
    high = namedic.apply_edits(vanilla, [{"index": 1, "text": "Esthar Plain"}])
    merged, conflicts, fallback = namedic.merge(
        vanilla, [("low", low), ("high", high)], PATH)
    assert not fallback
    assert _texts(merged)[1] == "Esthar Plain"
    assert conflicts == [{"unit": f"{PATH}:name:1", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_same_value_is_not_a_conflict():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    edit = [{"index": 0, "text": "Galbadia Region"}]
    merged, conflicts, fallback = namedic.merge(
        vanilla, [("first", namedic.apply_edits(vanilla, edit)),
                  ("second", namedic.apply_edits(vanilla, edit))], PATH)
    assert not fallback and not conflicts
    assert _texts(merged)[0] == "Galbadia Region"


def test_count_change_falls_back_opaque():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    other = _namedic(["Galbadia", "Esthar"])
    merged, conflicts, fallback = namedic.merge(vanilla, [("other", other)], PATH)
    assert merged is None and not conflicts and "name count" in fallback


def test_unparseable_source_falls_back_opaque():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    merged, conflicts, fallback = namedic.merge(vanilla, [("broken", b"nope")], PATH)
    assert merged is None and not conflicts and "not a supported" in fallback


def test_byte_change_outside_names_falls_back_opaque():
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    padded = _namedic(["Galbadia", "Esthar", "Balamb"], padding=(1, 0, 0))
    assert _texts(padded) == _texts(vanilla)
    merged, conflicts, fallback = namedic.merge(vanilla, [("padded", padded)], PATH)
    assert merged is None and not conflicts and "outside proved names" in fallback


def _write_mod(root, mod_id, payload, order):
    (root / "direct").mkdir(parents=True, exist_ok=True)
    (root / PATH).write_bytes(payload)
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": mod_id, "name": mod_id.title(), "order": order, "enabled": True,
    }), encoding="utf-8")


def test_compose_merges_names_semantically(tmp_path):
    project, mods, active = tmp_path / "project", tmp_path / "mods", tmp_path / "active"
    baseline = tmp_path / "baseline"
    (baseline / "main").mkdir(parents=True)
    vanilla = _namedic(["Galbadia", "Esthar", "Balamb"])
    (baseline / "main" / "namedic.bin").write_bytes(vanilla)
    project.mkdir(parents=True)
    (project / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "project", "name": "Project", "order": -1, "enabled": True,
    }), encoding="utf-8")
    _write_mod(mods / "low", "low",
               namedic.apply_edits(vanilla, [{"index": 0, "text": "Galbadia Region"}]), 0)
    _write_mod(mods / "high", "high",
               namedic.apply_edits(vanilla, [{"index": 0, "text": "Greater Galbadia"},
                                             {"index": 2, "text": "Balamb Town"}]), 1)
    rows = runtime_layout.configure(project, mods, ["project", "low", "high"],
                                    {"project": True, "low": True, "high": True})
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    assert _texts((active / PATH).read_bytes()) == [
        "Greater Galbadia", "Esthar", "Balamb Town"]
    conflict = next(row for row in result["conflicts"] if row["path"] == PATH)
    assert conflict["mode"] == "semantic merge" and conflict["claimants"] == ["low", "high"]
    assert conflict["units"] == [{"unit": f"{PATH}:name:0", "winner": "high",
                                  "claimants": ["low", "high"]}]
