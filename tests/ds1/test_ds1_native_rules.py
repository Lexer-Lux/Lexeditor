"""Compatibility checks for restoring previously installed draft native patches."""
import hashlib
import json
from pathlib import Path
import struct

import pytest

from ds1_native_fixture import fake_executable
from plugins.ds1 import stamina_patch as native


@pytest.fixture
def setup(tmp_path, monkeypatch):
    original = fake_executable(monkeypatch)
    monkeypatch.setattr(native, "ensure_game_closed", lambda: None)
    game = tmp_path / "legacy-game"
    game.mkdir()
    (game / native.EXECUTABLE).write_bytes(original)
    return game, None, None, None, original


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
    (game / native.EXECUTABLE).write_bytes(native.transform(original, {**native.DEFAULT_RULES, "baseRecovery": 80}))
    with pytest.raises(ValueError, match="outside"):
        native.install(game, native.DEFAULT_RULES)
