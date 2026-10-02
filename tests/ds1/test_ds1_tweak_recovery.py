"""Generic executable-mod recovery; fixtures contain no retail code or tweak."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pytest

from plugins.ds1 import exe_patches, tweak_mods
from test_ds1_exe_patches import VANILLA, HOOK_A


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setattr(exe_patches, "VANILLA_SIZE", len(VANILLA))
    monkeypatch.setattr(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest())
    monkeypatch.setattr(tweak_mods, "ensure_game_closed", lambda: None)
    root = tmp_path / "game"
    root.mkdir()
    (root / exe_patches.EXECUTABLE).write_bytes(VANILLA)
    library = tmp_path / "library"
    library.mkdir()
    spec = exe_patches.validate({"version": 1, "hooks": [
        {"rva": HOOK_A, "original": "e800000000", "bytes": "9090909090"},
    ]}, "Synthetic fixture")
    monkeypatch.setattr(tweak_mods, "build_specs", lambda _root=None: [spec])
    return root, library, exe_patches.compose(VANILLA, [spec])


def image(game):
    return (game[0] / exe_patches.EXECUTABLE).read_bytes()


def test_apply_restore_retains_one_original(game):
    root, library, projected = game
    assert tweak_mods.apply(root, library)["state"] == "tweaked"
    assert image(game) == projected
    assert (root / tweak_mods.BACKUP_FILE).read_bytes() == VANILLA
    assert tweak_mods.restore(root, library)["state"] == "vanilla"
    assert image(game) == VANILLA
    assert not (root / tweak_mods.MANIFEST_FILE).exists()
    assert (root / tweak_mods.LOCK_FILE).stat().st_size == 1


@pytest.mark.parametrize("after_write", [False, True])
def test_interrupted_apply_is_recognized_and_retryable(game, monkeypatch, after_write):
    root, library, projected = game
    real = tweak_mods.atomic_write

    def interrupt(path, data):
        if Path(path).name == exe_patches.EXECUTABLE:
            if after_write:
                real(path, data)
            raise OSError("simulated interruption")
        real(path, data)

    monkeypatch.setattr(tweak_mods, "atomic_write", interrupt)
    with pytest.raises(OSError, match="interruption"):
        tweak_mods.apply(root, library)
    assert image(game) == (projected if after_write else VANILLA)
    state = tweak_mods.status(root, library)
    assert state["pendingRecovery"] is True
    assert state["problem"] == ""
    assert state["state"] == ("tweaked" if after_write else "vanilla")
    monkeypatch.setattr(tweak_mods, "atomic_write", real)
    state = tweak_mods.apply(root, library)
    assert state["pendingRecovery"] is False
    assert state["applied"] == ["Synthetic fixture"]
    assert image(game) == projected


@pytest.mark.parametrize("after_write", [False, True])
def test_interrupted_restore_is_recognized_and_retryable(game, monkeypatch, after_write):
    root, library, projected = game
    tweak_mods.apply(root, library)
    real = tweak_mods.atomic_write

    def interrupt(path, data):
        if Path(path).name == exe_patches.EXECUTABLE:
            if after_write:
                real(path, data)
            raise OSError("simulated interruption")
        real(path, data)

    monkeypatch.setattr(tweak_mods, "atomic_write", interrupt)
    with pytest.raises(OSError):
        tweak_mods.restore(root, library)
    assert image(game) == (VANILLA if after_write else projected)
    assert tweak_mods.status(root, library)["pendingRecovery"]
    monkeypatch.setattr(tweak_mods, "atomic_write", real)
    assert tweak_mods.restore(root, library)["state"] == "vanilla"
    assert image(game) == VANILLA
    assert not (root / tweak_mods.MANIFEST_FILE).exists()


def test_failed_journal_cannot_change_live_image(game, monkeypatch):
    root, library, _ = game
    monkeypatch.setattr(tweak_mods, "_save_manifest",
                        lambda *_: (_ for _ in ()).throw(OSError("journal failed")))
    with pytest.raises(OSError, match="journal"):
        tweak_mods.apply(root, library)
    assert image(game) == VANILLA


def test_finalization_failure_is_recoverable_without_rewriting_executable(game, monkeypatch):
    root, library, projected = game
    real = tweak_mods._finish_manifest
    monkeypatch.setattr(tweak_mods, "_finish_manifest",
                        lambda *_: (_ for _ in ()).throw(OSError("finalize failed")))
    with pytest.raises(OSError, match="finalize"):
        tweak_mods.apply(root, library)
    assert image(game) == projected
    monkeypatch.setattr(tweak_mods, "_finish_manifest", real)
    writes = []
    atomic = tweak_mods.atomic_write

    def record(path, data):
        writes.append(Path(path).name)
        return atomic(path, data)

    monkeypatch.setattr(tweak_mods, "atomic_write", record)
    state = tweak_mods.apply(root, library)
    assert not state["pendingRecovery"]
    assert exe_patches.EXECUTABLE not in writes


def test_unknown_bytes_are_refused_even_with_a_pending_record(game, monkeypatch):
    root, library, _ = game
    real = tweak_mods._finish_manifest
    monkeypatch.setattr(tweak_mods, "_finish_manifest",
                        lambda *_: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(OSError):
        tweak_mods.apply(root, library)
    monkeypatch.setattr(tweak_mods, "_finish_manifest", real)
    outsider = bytearray(image(game))
    outsider[-1] ^= 1
    (root / exe_patches.EXECUTABLE).write_bytes(outsider)
    for action in (tweak_mods.apply, tweak_mods.restore):
        with pytest.raises(tweak_mods.TweakError, match="outside"):
            action(root, library)
        assert image(game) == outsider


@pytest.mark.parametrize("entry", [
    {"version": True, "sha256": "a" * 64, "mods": []},
    {"version": 1, "sha256": "not-a-digest", "mods": []},
    {"version": 1, "sha256": "a" * 64, "mods": [None]},
    {"version": 1, "sha256": "a" * 64, "mods": [], "pending": {"sha256": 1, "mods": []}},
])
def test_invalid_journal_is_refused(game, entry):
    root, library, _ = game
    (root / tweak_mods.MANIFEST_FILE).write_text(json.dumps(entry))
    with pytest.raises(tweak_mods.TweakError, match="damaged"):
        tweak_mods.apply(root, library)
    assert image(game) == VANILLA


def test_oversized_journal_is_refused(game):
    root, library, _ = game
    (root / tweak_mods.MANIFEST_FILE).write_bytes(b"x" * (tweak_mods.MAX_MANIFEST + 1))
    with pytest.raises(tweak_mods.TweakError, match="large"):
        tweak_mods.apply(root, library)
    assert image(game) == VANILLA


def test_cooperating_writers_do_not_enter_together(game):
    with tweak_mods._exclusive(game[0]):
        with pytest.raises(OSError):
            with tweak_mods._exclusive(game[0]):
                pytest.fail("The second writer acquired the same lock")
    with tweak_mods._exclusive(game[0]):
        pass


def test_corrupt_backup_is_not_used_for_restore(game):
    root, library, projected = game
    tweak_mods.apply(root, library)
    (root / tweak_mods.BACKUP_FILE).write_bytes(b"bad")
    with pytest.raises(tweak_mods.TweakError, match="original"):
        tweak_mods.restore(root, library)
    assert image(game) == projected


def test_game_start_before_replacement_leaves_recoverable_intent(game, monkeypatch):
    root, library, _ = game
    calls = 0

    def game_closed():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise tweak_mods.TweakError("game started")

    monkeypatch.setattr(tweak_mods, "ensure_game_closed", game_closed)
    with pytest.raises(tweak_mods.TweakError, match="started"):
        tweak_mods.apply(root, library)
    assert image(game) == VANILLA
    assert tweak_mods.status(root, library)["pendingRecovery"]
