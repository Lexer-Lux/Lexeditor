"""Native-rule editing, exact ownership, preservation and reversible overlay tests."""
import hashlib
import json
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_native_fixture import make_native_archive, fake_executable
from plugins.ds1 import stamina_patch as native, stamina_rebalance as module, deployment
from plugins.ds1.stamina_rebalance import StaminaRebalance, DEFAULTS, project_overlay, effective_rules
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1.formats import ItemDocument, inflate
from plugins.ds1.effects import TABLE, RECOVERY_KEY


@pytest.fixture
def setup(tmp_path, monkeypatch):
    original = fake_executable(monkeypatch)
    monkeypatch.setattr(native, "ensure_game_closed", lambda: None)
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_native_archive())
    (game / native.EXECUTABLE).write_bytes(original)
    mod.mkdir()
    (mod / MARKER).touch()
    store = ItemStore(game, mod, False)
    return game, mod, store, StaminaRebalance(game, mod, False), original


def test_native_noop_allowed_ranges_and_exact_identification(monkeypatch):
    original = fake_executable(monkeypatch)
    assert native.transform(original, native.DEFAULT_RULES) == original
    rules = {**native.DEFAULT_RULES, "baseRecovery": 60, "lightLimit": 30,
             "mediumLimit": 60, "heavyLimit": 120, "lightRecovery": 125}
    result = native.transform(original, rules)
    assert native.identify(result, original) == rules
    spans = [(native.BASELINE_OFFSET, 4), (native.LIGHT_OFFSET, 4), (native.MEDIUM_OFFSET, 4),
             (native.OVERLOAD_DISP_OFFSET, 4), (native.FACTOR_OFFSET, 41), (native.FRACTION_OFFSET, 151)]
    allowed = {i for start, size in spans for i in range(start, start + size)}
    assert {i for i, (a, b) in enumerate(zip(original, result)) if a != b} <= allowed
    with pytest.raises(ValueError):
        native.identify(result)
    broken = bytearray(result)
    broken[-1] ^= 1
    with pytest.raises(ValueError):
        native.identify(bytes(broken), original)
    with pytest.raises(ValueError):
        native.transform(result, rules)


@pytest.mark.parametrize("key,value", [
    ("baseRecovery", -1), ("baseRecovery", float("nan")), ("baseRecovery", True),
    ("baseRecovery", 201), ("lightLimit", 0), ("lightLimit", 50),
    ("mediumLimit", 100), ("heavyLimit", 49), ("lightRecovery", float("inf")),
    ("lightRecovery", -1), ("heavyRecovery", 1001), ("mediumLimit", 25.00001),
])
def test_bad_rules_rejected(key, value):
    with pytest.raises(ValueError):
        native.validate_rules({**native.DEFAULT_RULES, key: value})


def test_misc_and_each_tier_use_single_canonical_settings(setup):
    game, mod, store, rules, _ = setup
    assert rules.read_row(0)["fields"][0]["key"] == "baseRecovery"
    with pytest.raises(ValueError, match="Enable"):
        rules.edit_row(0, "baseRecovery", 70)
    rules.edit_row(100, "enabled", 1)
    rules.edit_row(0, "baseRecovery", 70)
    rules.edit_row(100, "encumbranceEnabled", True)
    for index, name in enumerate(native.RECOVERY_KEYS):
        rules.edit_row(10 + index, name, 20 + index)
    rules.edit_row(11, "lightLimit", 30)
    assert rules.read_row(10)["fields"][1]["value"] == 30
    assert rules.read_row(12)["fields"][0]["value"] == 30
    rules.save()
    reopened = StaminaRebalance(game, mod, False)
    assert effective_rules(reopened.saved)["baseRecovery"] == 70
    assert [reopened.value[k] for k in native.RECOVERY_KEYS] == list(range(20, 25))
    with pytest.raises(ValueError):
        rules.edit_row(10, "lightLimit", 40)
    with pytest.raises(ValueError):
        rules.edit_row(0, "lightLimit", 20)
    rules.edit("baseRecovery", 80)
    rules.discard()
    assert rules.value["baseRecovery"] == 70


def test_overlay_preserves_authored_values_and_other_cells():
    source = make_native_archive()
    doc = ItemDocument(source)
    doc.edit(TABLE, 6890, RECOVERY_KEY, 13)
    source = doc.export()
    assert project_overlay(source, DEFAULTS) == source
    modified = project_overlay(source, {**DEFAULTS, "enabled": True})
    result = ItemDocument(modified)
    assert result.value(TABLE, 6890, RECOVERY_KEY) == 5
    assert result.value(TABLE, 6200, RECOVERY_KEY) == -2
    start = doc._row(TABLE, 6890)[1] + 184
    allowed = set(range(start, start + 4))
    assert {i for i, (a, b) in enumerate(zip(inflate(source), inflate(modified))) if a != b} <= allowed
    # Follow reassigned passives instead of the reference effect name.
    doc.edit("EquipParamWeapon", 1453000, "residentSpEffectId", 99001)
    reassigned = ItemDocument(project_overlay(doc.export(), {**DEFAULTS, "enabled": True}))
    assert reassigned.value(TABLE, 99001, RECOVERY_KEY) == 5
    assert reassigned.value(TABLE, 6890, RECOVERY_KEY) == 13


def test_apply_disable_restore_are_independent_and_exact(setup):
    game, mod, store, rules, original = setup
    pristine = (game / RELATIVE).read_bytes()
    store.edit(TABLE, 6890, RECOVERY_KEY, 13)
    store.save()
    authored = (mod / RELATIVE).read_bytes()
    rules.edit("enabled", True)
    rules.edit("encumbranceEnabled", True)
    rules.edit("lightLimit", 30)
    rules.save()
    status = rules.apply(store)
    assert not status["stale"]
    installed = (game / native.EXECUTABLE).read_bytes()
    assert native.identify(installed, original)["lightLimit"] == 30
    assert native.identify(installed, original)["baseRecovery"] == 60
    assert ItemDocument((game / RELATIVE).read_bytes()).value(TABLE, 6890, RECOVERY_KEY) == 5
    assert (mod / RELATIVE).read_bytes() == authored
    rules.edit("enabled", False)
    rules.save()
    rules.apply(store)
    current = native.identify((game / native.EXECUTABLE).read_bytes(), original)
    assert current["lightLimit"] == 30 and current["baseRecovery"] == 45
    assert (game / RELATIVE).read_bytes() == authored
    rules.edit("encumbranceEnabled", False)
    rules.save()
    rules.apply(store)
    assert (game / native.EXECUTABLE).read_bytes() == original
    rules.restore()
    assert (game / RELATIVE).read_bytes() == pristine
    assert (game / native.BACKUP).read_bytes() == original
    assert (mod / RELATIVE).read_bytes() == authored


def test_no_write_on_unknown_image_missing_original_running_or_stale_settings(setup, monkeypatch):
    game, mod, store, rules, original = setup
    store.save()
    rules.edit("enabled", True)
    rules.save()
    exe = game / native.EXECUTABLE
    exe.write_bytes(original + b"foreign")
    with pytest.raises(ValueError):
        rules.apply(store)
    assert not (game / native.BACKUP).exists()
    exe.write_bytes(original)
    def running():
        raise RuntimeError("game running")
    monkeypatch.setattr(native, "ensure_game_closed", running)
    with pytest.raises(RuntimeError, match="running"):
        rules.apply(store)
    assert exe.read_bytes() == original and not (game / native.BACKUP).exists()
    monkeypatch.setattr(native, "ensure_game_closed", lambda: None)
    rules.apply(store)
    (game / native.BACKUP).unlink()
    with pytest.raises(ValueError):
        rules.restore()
    assert exe.read_bytes() != original
    (mod / module.SETTINGS_FILE).write_text("{}")
    with pytest.raises(ValueError):
        rules.save()


def test_parameter_failure_rolls_native_back_without_overwriting_others(setup, monkeypatch):
    game, mod, store, rules, original = setup
    store.save()
    rules.edit("enabled", True)
    rules.save()
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic disk error")
    monkeypatch.setattr(deployment, "apply", fail)
    with pytest.raises(RuntimeError, match="previous rate"):
        rules.apply(store)
    assert (game / native.EXECUTABLE).read_bytes() == original


def test_readonly_and_settings_conflicts(setup):
    game, mod, store, rules, original = setup
    with pytest.raises(PermissionError):
        StaminaRebalance(game, mod, True).edit("enabled", True)
    with pytest.raises(PermissionError):
        StaminaRebalance(game).edit("enabled", True)
    rules.edit("enabled", True)
    rules.save()
    other = StaminaRebalance(game, mod, False)
    other.edit("baseRecovery", 65)
    other.save()
    with pytest.raises(ValueError, match="outside"):
        rules.save()


def test_source_native_schema_validation_does_not_touch_game():
    for bad in ({"enabled": True}, {**DEFAULTS, "encumbranceEnabled": 1}):
        with pytest.raises(ValueError):
            module.settings(bad)
    for key, value in [("enabled", True), ("encumbranceEnabled", True)]:
        native.validate_rules(effective_rules({**DEFAULTS, key: value}))


def test_external_project_change_refuses_apply_before_native_write(setup):
    game, mod, store, rules, original = setup
    store.save()
    rules.edit("enabled", True)
    rules.save()
    changed = ItemDocument((mod / RELATIVE).read_bytes())
    changed.edit(TABLE, 6890, RECOVERY_KEY, 9)
    (mod / RELATIVE).write_bytes(changed.export())
    with pytest.raises(ValueError, match="outside"):
        rules.apply(store)
    assert (game / native.EXECUTABLE).read_bytes() == original
    assert not (game / native.BACKUP).exists()


@pytest.mark.parametrize("phase", ["before-image", "after-image"])
def test_interrupted_native_replacement_can_be_retried(setup, monkeypatch, phase):
    game, mod, store, rules, original = setup
    desired = {**native.DEFAULT_RULES, "baseRecovery": 60}
    atomic = native.atomic_write
    calls = []
    def interrupt(path, content):
        path = Path(path)
        calls.append(path.name)
        if phase == "before-image" and path.name == native.EXECUTABLE:
            raise OSError("interrupted before image")
        if phase == "after-image" and path.name == native.OWNER and calls.count(native.OWNER) == 2:
            raise OSError("interrupted before completion marker")
        return atomic(path, content)
    monkeypatch.setattr(native, "atomic_write", interrupt)
    with pytest.raises(OSError):
        native.install(game, desired)
    # The stored pending image is the only additional recognized state.
    _, current, backup_ok = native.inspect(game)
    assert backup_ok and current["baseRecovery"] == (45 if phase == "before-image" else 60)
    monkeypatch.setattr(native, "atomic_write", atomic)
    native.install(game, desired)
    native.install(game, native.DEFAULT_RULES)
    assert (game / native.EXECUTABLE).read_bytes() == original


def test_owner_rejects_schema_and_foreign_projected_image(setup):
    game, mod, store, rules, original = setup
    native.install(game, {**native.DEFAULT_RULES, "baseRecovery": 60})
    owner_path = game / native.OWNER
    owner = json.loads(owner_path.read_text())
    owner_path.write_text(json.dumps({**owner, "schema": True}))
    with pytest.raises(ValueError, match="ownership"):
        native.inspect(game)
    owner_path.write_text(json.dumps(owner))
    # Even another technically valid projection must have recorded ownership.
    (game / native.EXECUTABLE).write_bytes(native.transform(original, {**native.DEFAULT_RULES, "baseRecovery": 80}))
    with pytest.raises(ValueError, match="outside"):
        native.install(game, native.DEFAULT_RULES)


def test_native_http_routes_saved_state_and_protected_writes(setup, monkeypatch):
    from http.server import ThreadingHTTPServer
    import threading
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from plugins.ds1 import server
    game, mod, store, rules, original = setup
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "RULES", rules)
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{http.server_port}"
    def request(path, payload=None, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        req = Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers=headers)
        with urlopen(req) as response:
            return json.load(response)
    def edit(row, key, value):
        return request("/api/edit", {"table": "NativeRules", "id": row, "field": key, "value": value})
    try:
        assert len(request("/api/table?tab=encumbrance")["rows"]) == 5
        assert request("/api/row?table=NativeRules&id=0")["row"]["fields"][0]["disabled"]
        edit(100, "enabled", 1)
        edit(100, "encumbranceEnabled", 1)
        edit(0, "baseRecovery", 72)
        edit(11, "lightLimit", 30)
        assert request("/api/state")["dirtyCount"] == 4
        with pytest.raises(HTTPError) as error:
            request("/api/edit", {"table": "NativeRules", "id": 0, "field": "baseRecovery", "value": 80},
                    origin="http://other.invalid")
        assert error.value.code == 403
        with pytest.raises(HTTPError):
            edit(10, "lightLimit", 35)
        request("/api/save", {})
        assert request("/api/state")["dirtyCount"] == 0
        edit(0, "baseRecovery", 80)
        request("/api/discard", {})
        assert request("/api/row?table=NativeRules&id=0")["row"]["fields"][0]["value"] == 72
        result = request("/api/deployment/apply", {})
        assert not result["stale"]
        assert native.inspect(game)[1]["baseRecovery"] == 72
        request("/api/deployment/disable", {})
        assert (game / native.EXECUTABLE).read_bytes() == original
        monkeypatch.setattr(server, "RULES", StaminaRebalance(game))
        with pytest.raises(HTTPError):
            edit(100, "enabled", 1)
    finally:
        http.shutdown()
        http.server_close()
        thread.join()
