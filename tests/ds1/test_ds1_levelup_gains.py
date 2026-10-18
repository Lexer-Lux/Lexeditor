"""DS1 level-up gains: the 36 defense weights are editable and patchable.

Runs against a small synthetic PE32+ that maps the real factor addresses,
so it needs no game files: the build fingerprint is swapped for the
synthetic one for each test.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ds1_fixture import make_archive
from plugins.ds1 import data_map, exe_patches, levelup_gains, load_bands_patch, stamina_patch
from plugins.ds1.native_rules import DEFAULTS, NativeRules, settings
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE, ItemStore

NT = 0x80
OPTIONAL = NT + 24
SECTIONS = OPTIONAL + 0xF0
LAYOUT = [  # name, rva, vsize, raw, raw size, flags
    (b".text", 0x1000, 0x1000, 0x400, 0x1000, 0x60000020),
    (b".data", 0x1A2B680, 0x100, 0x1400, 0x200, 0xC0000040),
    (b".pdata", 0x3000, 0x18, 0x1600, 0x200, 0x40000040),
    (b".text", 0x4000, 0x1000, 0x1800, 0x1000, 0x60000020),
]
CERT = (0x2800, 0x40)
UNWIND = 0x1100
FACTOR_RAW = 0x1400 + (levelup_gains.FACTOR_RVA_BASE - 0x1A2B680)

# The disassembly's factor table, pinned: output, block address, vanilla weights.
EXPECTED = [
    ("physical", 0x1A2B6A0, (0.9,) * 8 + (1.8,)),
    ("magic", 0x1A2B6C8, (0.85,) * 6 + (2.2, 0.85, 0.85)),
    ("flame", 0x1A2B6F0, (0.85,) * 8 + (2.2,)),
    ("lightning", 0x1A2B718, (1.0,) * 9),
]
EXPECTED_HEX = {"6666663f": 0.9, "6666e63f": 1.8, "9a99593f": 0.85,
                "cdcc0c40": 2.2, "0000803f": 1.0}
PADDING = (0x1A2B6C0, 0x1A2B6E8, 0x1A2B710, 0x1A2B738)


def synthetic() -> bytes:
    data = bytearray(CERT[0] + CERT[1])
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, NT)
    data[NT:NT + 4] = b"PE\0\0"
    struct.pack_into("<HH", data, NT + 4, 0x8664, len(LAYOUT))
    struct.pack_into("<H", data, NT + 20, 0xF0)
    struct.pack_into("<H", data, OPTIONAL, 0x20B)
    struct.pack_into("<II", data, OPTIONAL + 32, 0x1000, 0x200)
    struct.pack_into("<I", data, OPTIONAL + 108, 16)
    struct.pack_into("<I", data, OPTIONAL + 4, 0x2000)
    struct.pack_into("<I", data, OPTIONAL + 56, 0x5000)
    struct.pack_into("<I", data, OPTIONAL + 64, 0x12345)
    struct.pack_into("<II", data, OPTIONAL + 112 + 3 * 8, 0x3000, 0x18)
    struct.pack_into("<II", data, OPTIONAL + 112 + 4 * 8, *CERT)
    for index, (name, rva, vsize, raw, raw_size, flags) in enumerate(LAYOUT):
        at = SECTIONS + index * 40
        data[at:at + 8] = name.ljust(8, b"\0")
        struct.pack_into("<IIII", data, at + 8, vsize, rva, raw_size, raw)
        struct.pack_into("<I", data, at + 36, flags)
    struct.pack_into("<IIIIII", data, 0x1600, 0x1000, 0x1010, UNWIND, 0x1020, 0x1030, UNWIND)
    data[0x400 + UNWIND - 0x1000] = 0x01
    for output in range(len(levelup_gains.OUTPUTS)):
        for index in range(len(levelup_gains.INPUTS)):
            at = FACTOR_RAW + (levelup_gains.rva_of(output, index)
                               - levelup_gains.FACTOR_RVA_BASE)
            struct.pack_into("<f", data, at, levelup_gains.vanilla_of(output, index))
    return bytes(data)


@pytest.fixture
def original(monkeypatch):
    monkeypatch.setattr(levelup_gains, "FACTOR_OFFSET_BASE", FACTOR_RAW)
    raw = synthetic()
    for module, size_key, hash_key in (
            (stamina_patch, "ORIGINAL_SIZE", "ORIGINAL_SHA256"),
            (exe_patches, "VANILLA_SIZE", "VANILLA_SHA256")):
        monkeypatch.setattr(module, size_key, len(raw))
        monkeypatch.setattr(module, hash_key, hashlib.sha256(raw).hexdigest())
    return raw


@pytest.fixture
def rules(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    game.mkdir(parents=True)
    mod.mkdir()
    (mod / MARKER).touch()
    return NativeRules(game, mod, False)


def test_factor_addresses_match_the_disassembly():
    assert levelup_gains.WITHIN == (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x24)
    assert levelup_gains.BLOCK_STRIDE == 0x28
    assert [key for key, _ in levelup_gains.OUTPUTS] == [row[0] for row in EXPECTED]
    assert [offset for _, _, offset in levelup_gains.INPUTS] == [
        0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x84, 0x88]
    seen = set()
    for output, (key, base, values) in enumerate(EXPECTED):
        assert levelup_gains.rva_of(output, 0) == base
        for index, value in enumerate(values):
            assert levelup_gains.vanilla_of(output, index) == value
            assert levelup_gains.vanilla_bytes(output, index).hex() == next(
                text for text, number in EXPECTED_HEX.items() if number == value)
            seen.add(levelup_gains.rva_of(output, index))
    assert len(seen) == 36
    assert not set(seen) & set(PADDING)
    assert max(seen) + 4 - min(seen) == 0xA0
    others = {stamina_patch.BASELINE_RVA, load_bands_patch.CLASS_RVA,
              load_bands_patch.FACTOR_RVA, load_bands_patch.FRACTION_RVA}
    assert not set(seen) & others


def test_project_defaults_are_vanilla_and_detached():
    first, second = levelup_gains.project_defaults(), levelup_gains.project_defaults()
    assert first == {key: dict(zip([name for name, _, _ in levelup_gains.INPUTS], values))
                     for key, _, values in EXPECTED}
    first["physical"]["vit"] = 0
    assert second["physical"]["vit"] == 0.9


def test_validate_round_trips_and_rejects_bad_rules():
    assert levelup_gains.validate(deepcopy(DEFAULTS["levelupGains"])) == DEFAULTS["levelupGains"]
    bad = deepcopy(DEFAULTS["levelupGains"])
    with pytest.raises(ValueError):
        levelup_gains.validate({"physical": bad["physical"]})
    for broken in ("extra", None, [], 0.9, True):
        with pytest.raises(ValueError):
            levelup_gains.validate({**bad, "physical": broken} if broken != "extra"
                                   else {**bad, "extra": {}})
    for value in (float("nan"), float("inf"), -0.1, 10.1, True, "0.9", None):
        attempt = deepcopy(bad)
        attempt["magic"]["fai"] = value
        with pytest.raises(ValueError):
            levelup_gains.validate(attempt)
    assert bad == DEFAULTS["levelupGains"]


def test_edit_replaces_one_factor():
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "flame", "res", 0)
    assert rules["flame"]["res"] == 0
    assert rules["flame"]["vit"] == 0.85
    assert rules["physical"]["res"] == 1.8
    assert DEFAULTS["levelupGains"]["flame"]["res"] == 2.2
    with pytest.raises(ValueError):
        levelup_gains.edit(rules, "flame", "unknown", 1)
    with pytest.raises(ValueError):
        levelup_gains.edit(rules, "unknown", "vit", 1)
    with pytest.raises(ValueError):
        levelup_gains.edit(rules, "flame", "res", 11)


def test_rows_use_bounded_number_controls():
    config = {"levelupGains": deepcopy(DEFAULTS["levelupGains"])}
    seen = set()
    for key, label in levelup_gains.OUTPUTS:
        row = levelup_gains.row(key, config)
        assert row["name"] == label and row["table"] == "NativeRules"
        assert row["id"] == levelup_gains.ROW_IDS[key]
        assert "99" in row["help"]
        assert len(row["fields"]) == 9
        for field in row["fields"]:
            seen.add(field["key"])
            assert field["type"] == "number" and field["dtype"] == "f32"
            assert (field["minimum"], field["maximum"]) == (0.0, 10.0)
            assert field["editable"] and not field["disabled"]
            assert field["description"] and field["description"] != field["label"]
        locked = levelup_gains.row(key, config, read_only=True)
        assert all(field["disabled"] for field in locked["fields"])
    assert seen == {name for name, _, _ in levelup_gains.INPUTS}
    identities = set(levelup_gains.ROW_IDS.values())
    assert len(identities) == 4 and not identities & {0, 200}
    assert min(identities) < 1001


def test_vanilla_values_build_no_hooks():
    spec = levelup_gains.spec_for_values(deepcopy(DEFAULTS["levelupGains"]))
    assert spec == {"version": 1, "islands": [], "hooks": []}
    assert exe_patches.validate(spec, "Level-up gains")


def test_one_change_builds_one_hook():
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "magic", "fai", 0)
    spec = levelup_gains.spec_for_values(rules)
    assert spec["islands"] == [] and len(spec["hooks"]) == 1
    assert spec["hooks"][0] == {"rva": 0x1A2B6E0, "original": "cdcc0c40",
                                "bytes": struct.pack("<f", 0).hex()}
    assert exe_patches.validate(spec, "Level-up gains")
    assert json.loads(json.dumps(spec)) == spec


def test_removed_defense_gain_hooks_every_weight():
    rules = {key: {name: 0 for name, _, _ in levelup_gains.INPUTS}
             for key, _ in levelup_gains.OUTPUTS}
    spec = levelup_gains.spec_for_values(rules)
    assert len(spec["hooks"]) == 36
    assert {hook["rva"] for hook in spec["hooks"]} == {
        levelup_gains.rva_of(output, index)
        for output in range(4) for index in range(9)}
    assert all(hook["bytes"] == struct.pack("<f", 0).hex() for hook in spec["hooks"])
    assert exe_patches.validate(spec, "Level-up gains")


def test_patch_spec_checks_the_build(original):
    assert levelup_gains.patch_spec(original, deepcopy(DEFAULTS["levelupGains"])) == {
        "version": 1, "islands": [], "hooks": []}
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "lightning", "hum", 0.5)
    assert (levelup_gains.patch_spec(original, rules)
            == levelup_gains.spec_for_values(rules))
    with pytest.raises(ValueError, match="Unsupported"):
        levelup_gains.patch_spec(original[:-1] + b"x", rules)


def test_patch_spec_refuses_rewritten_weights(original, monkeypatch):
    tampered = bytearray(original)
    tampered[FACTOR_RAW + 1] ^= 1
    raw = bytes(tampered)
    for module, size_key, hash_key in (
            (stamina_patch, "ORIGINAL_SIZE", "ORIGINAL_SHA256"),
            (exe_patches, "VANILLA_SIZE", "VANILLA_SHA256")):
        monkeypatch.setattr(module, size_key, len(raw))
        monkeypatch.setattr(module, hash_key, hashlib.sha256(raw).hexdigest())
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "physical", "vit", 0)
    with pytest.raises(ValueError, match="does not match"):
        levelup_gains.patch_spec(raw, rules)


def test_compose_changes_only_edited_weights(original):
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "physical", "vit", 0)
    rules = levelup_gains.edit(rules, "magic", "fai", 3)
    spec = exe_patches.validate(levelup_gains.spec_for_values(rules), "Level-up gains")
    output = exe_patches.compose(original, [spec])
    for target, (key, _) in enumerate(levelup_gains.OUTPUTS):
        for index, (name, _, _) in enumerate(levelup_gains.INPUTS):
            at = FACTOR_RAW + (levelup_gains.rva_of(target, index)
                               - levelup_gains.FACTOR_RVA_BASE)
            expected = struct.unpack("<f", struct.pack("<f", rules[key][name]))[0]
            assert struct.unpack_from("<f", output, at)[0] == expected
    for padding in PADDING:
        at = FACTOR_RAW + (padding - levelup_gains.FACTOR_RVA_BASE)
        assert output[at:at + 4] == b"\0\0\0\0"
    assert output[CERT[0]:CERT[0] + CERT[1]] == original[CERT[0]:CERT[0] + CERT[1]]


def test_loader_patch_carries_the_changed_weights(original):
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "flame", "res", 0)
    spec = exe_patches.validate(levelup_gains.spec_for_values(rules), "Level-up gains")
    parsed = exe_patches.read_runtime_patch(exe_patches.runtime_patch(original, [spec]))
    kinds = [record[0] for record in parsed["records"]]
    assert kinds.count(exe_patches.HOOK) == 1
    assert exe_patches.DELAY in kinds
    _kind, rva, length, payload = next(record for record in parsed["records"]
                                       if record[0] == exe_patches.HOOK)
    assert (rva, length) == (0x1A2B714, 4)
    assert payload == bytes.fromhex("cdcc0c40") + struct.pack("<f", 0)


def test_shared_weights_conflict_before_a_result_is_returned(original):
    rules = levelup_gains.edit(DEFAULTS["levelupGains"], "physical", "vit", 0)
    spec = exe_patches.validate(levelup_gains.spec_for_values(rules), "Level-up gains")
    at = FACTOR_RAW + (0x1A2B6A0 - levelup_gains.FACTOR_RVA_BASE)
    other = exe_patches.validate({"version": 1, "hooks": [{
        "rva": 0x1A2B6A0, "original": original[at:at + 4].hex(), "bytes": "0000803f"}]},
        "Other rules")
    with pytest.raises(exe_patches.PatchError, match="both patch"):
        exe_patches.compose(original, [spec, other])


def test_settings_accept_older_files_and_reject_unknown_keys():
    assert settings(deepcopy(DEFAULTS)) == DEFAULTS
    older = deepcopy(DEFAULTS)
    del older["levelupGains"]
    assert settings(older)["levelupGains"] == DEFAULTS["levelupGains"]
    with pytest.raises(ValueError):
        settings({**deepcopy(DEFAULTS), "extra": {}})
    with pytest.raises(ValueError):
        settings({})


def test_native_rules_edit_save_and_reload(rules, tmp_path):
    rows = rules.list_rows("levelup")
    assert [(row["id"], row["name"]) for row in rows] == [
        (identity, label) for (_, label), identity
        in zip(levelup_gains.OUTPUTS, sorted(levelup_gains.ROW_IDS.values()))]
    assert rows[0]["values"] == DEFAULTS["levelupGains"]["physical"]
    row = rules.read_row(101)
    assert [field["key"] for field in row["fields"]] == [
        name for name, _, _ in levelup_gains.INPUTS]
    rules.edit_row(101, "vit", 0)
    assert rules.read_row(101)["fields"][0]["value"] == 0
    assert rules.dirty_count == 1
    with pytest.raises(ValueError):
        rules.edit_row(101, "vit", 11)
    with pytest.raises(ValueError):
        rules.edit_row(101, "unknown", 1)
    rules.save()
    assert rules.dirty_count == 0
    reopened = NativeRules(rules.game_root, rules.project, False)
    assert reopened.value["levelupGains"]["physical"]["vit"] == 0
    with pytest.raises(PermissionError):
        NativeRules(rules.game_root).edit_row(101, "vit", 1)


def test_contribution_combines_bands_and_gains(rules, original):
    assert rules._contribution(original) is None
    rules.edit_row(102, "fai", 0)
    rules.save()
    contribution = rules._contribution(original)
    assert contribution["path"] == str(rules.project.resolve())
    spec = exe_patches.validate(contribution["spec"], "Project native rules")
    assert spec["islands"] == [] and len(spec["hooks"]) == 1
    assert spec["hooks"][0]["rva"] == 0x1A2B6E0


def request_json(session, path, payload=None):
    request = Request(session.url.rstrip("/") + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request) as reply:
        return json.loads(reply.read())


def test_service_lists_edits_and_saves_gains(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})
    try:
        session.start()
        assert "levelup-gains" in request_json(session, "/api/plugin")["capabilities"]
        rows = request_json(session, "/api/table?tab=levelup")["rows"]
        assert [row["name"] for row in rows] == [label for _, label in levelup_gains.OUTPUTS]
        row = request_json(session, "/api/row?table=NativeRules&id=101&sub=levelup")["row"]
        assert [field["key"] for field in row["fields"]] == [
            name for name, _, _ in levelup_gains.INPUTS]
        edited = request_json(session, "/api/edit", {"table": "NativeRules", "id": 101,
                                                     "field": "vit", "value": 0,
                                                     "sub": "levelup"})["row"]
        assert edited["fields"][0]["value"] == 0
        with pytest.raises(HTTPError):
            request_json(session, "/api/edit", {"table": "NativeRules", "id": 101,
                                                "field": "vit", "value": 11, "sub": "levelup"})
        assert request_json(session, "/api/save", {})["dirtyCount"] == 0
        assert request_json(session, "/api/table?tab=levelup")["rows"][0]["values"]["vit"] == 0
    finally:
        session.stop()


def test_data_map_links_the_tab(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    store = ItemStore(game, mod, False)
    row = next(item for item in data_map.payload(
        store, {"native": {"available": True}})["rows"] if item["id"] == "native-levelup")
    assert row["target"] == "stats" and row["sub"] == "levelup" and row["openable"]
    assert row["targets"] == [{"id": "stats", "label": "Stats"}]
    assert row["controls"] == "Stats: level-up defense gains"
    unavailable = next(item for item in data_map.payload(store)["rows"]
                       if item["id"] == "native-levelup")
    assert unavailable["target"] == "" and not unavailable["openable"]


def test_gains_live_in_the_stats_subtabs(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    tabs = ItemStore(game, mod, False).state()["statsTabs"]
    gains = next(entry for entry in tabs if entry["id"] == "levelup")
    assert (gains["label"], gains["table"]) == ("Level-up gains", "NativeRules")


def test_native_list_rows_mark_modified_after_edit(rules):
    assert all(not row.get("modified") for row in rules.list_rows("levelup"))
    assert all(not row.get("modified") for row in rules.list_rows("encumbrance"))
    assert all(not row.get("modified") for row in rules.list_rows("encumbrance-overrides"))
    assert all(not row.get("modified") for row in rules.list_rows("misc"))
    rules.edit_row(101, "vit", 0)
    flags = {row["id"]: row.get("modified") for row in rules.list_rows("levelup")}
    assert flags[101] is True
    assert all(value is not True for key, value in flags.items() if key != 101)
    band = rules.list_rows("encumbrance")[0]
    rules.edit_row(band["id"], "recovery", 50)
    flags = {row["id"]: row.get("modified") for row in rules.list_rows("encumbrance")}
    assert flags[band["id"]] is True
    assert all(value is not True for key, value in flags.items() if key != band["id"])
    rules.edit_row(200, "forcedRecovery", 50)
    assert [row.get("modified") for row in rules.list_rows("encumbrance-overrides")] == [True]
    rules.edit_row(0, "baseRecovery", 60)
    assert [row.get("modified") for row in rules.list_rows("misc")] == [True]
