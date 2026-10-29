"""Executable recovery; fixtures contain no retail code or tweak.

Apply no longer writes the executable (the loader patches it in memory), so
the only executable write left is putting back one an earlier Lexeditor
patched. That write keeps its journal: an interruption at any point is
recognised and retried, and unknown bytes are never overwritten.
"""
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
    library = tmp_path / "library"
    library.mkdir()
    spec = exe_patches.validate({"version": 1, "hooks": [
        {"rva": HOOK_A, "original": "e800000000", "bytes": "9090909090"},
    ]}, "Synthetic fixture")
    monkeypatch.setattr(tweak_mods, "build_specs", lambda _root=None, _game_root=None: [spec])
    # What an earlier Lexeditor left: the tweak built into the executable.
    built = exe_patches.compose(VANILLA, [spec])
    (root / exe_patches.EXECUTABLE).write_bytes(built)
    (root / tweak_mods.BACKUP_FILE).write_bytes(VANILLA)
    (root / tweak_mods.MANIFEST_FILE).write_text(json.dumps({
        "version": 2, "sha256": hashlib.sha256(built).hexdigest(), "mods": ["Synthetic fixture"],
        "project": None, "pending": None}), encoding="utf-8")
    return root, library, built


def image(game):
    return (game[0] / exe_patches.EXECUTABLE).read_bytes()


def loader_installed(game):
    return (game[0] / tweak_mods.RUNTIME_PATCH).is_file() and (game[0] / tweak_mods.RUNTIME_DLL).is_file()


def interrupt_executable(monkeypatch, after_write):
    real = tweak_mods.atomic_write

    def interrupt(path, data):
        if Path(path).name == exe_patches.EXECUTABLE:
            if after_write:
                real(path, data)
            raise OSError("simulated interruption")
        real(path, data)
    monkeypatch.setattr(tweak_mods, "atomic_write", interrupt)
    return real


@pytest.mark.parametrize("action", ["apply", "restore"])
def test_the_first_apply_or_restore_puts_the_original_back(game, action):
    root, library, _built = game
    result = getattr(tweak_mods, action)(root, library)
    assert image(game) == VANILLA
    assert not (root / tweak_mods.MANIFEST_FILE).exists()
    assert result["builtIntoExecutable"] is False
    assert loader_installed(game) is (action == "apply")
    assert (root / tweak_mods.LOCK_FILE).stat().st_size == 1


@pytest.mark.parametrize("action", ["apply", "restore"])
@pytest.mark.parametrize("after_write", [False, True])
def test_an_interrupted_put_back_is_recognized_and_retryable(game, monkeypatch, action, after_write):
    root, library, built = game
    real = interrupt_executable(monkeypatch, after_write)
    with pytest.raises(OSError, match="interruption"):
        getattr(tweak_mods, action)(root, library)
    assert image(game) == (VANILLA if after_write else built)
    state = tweak_mods.status(root, library)
    assert state["pendingRecovery"] is True and state["problem"] == ""
    monkeypatch.setattr(tweak_mods, "atomic_write", real)
    state = getattr(tweak_mods, action)(root, library)
    assert state["pendingRecovery"] is False
    assert image(game) == VANILLA
    assert not (root / tweak_mods.MANIFEST_FILE).exists()


def test_failed_journal_cannot_change_live_image(game, monkeypatch):
    root, library, built = game
    monkeypatch.setattr(tweak_mods, "_save_manifest",
                        lambda *_: (_ for _ in ()).throw(OSError("journal failed")))
    with pytest.raises(OSError, match="journal"):
        tweak_mods.apply(root, library)
    assert image(game) == built
    assert not loader_installed(game)


def test_finalization_failure_is_recoverable_without_rewriting_executable(game, monkeypatch):
    root, library, _built = game
    real = tweak_mods._finish_manifest
    monkeypatch.setattr(tweak_mods, "_finish_manifest",
                        lambda *_: (_ for _ in ()).throw(OSError("finalize failed")))
    with pytest.raises(OSError, match="finalize"):
        tweak_mods.restore(root, library)
    assert image(game) == VANILLA
    monkeypatch.setattr(tweak_mods, "_finish_manifest", real)
    writes = []
    atomic = tweak_mods.atomic_write

    def record(path, data):
        writes.append(Path(path).name)
        return atomic(path, data)

    monkeypatch.setattr(tweak_mods, "atomic_write", record)
    state = tweak_mods.restore(root, library)
    assert not state["pendingRecovery"]
    assert exe_patches.EXECUTABLE not in writes


def test_unknown_bytes_are_refused_even_with_a_pending_record(game, monkeypatch):
    root, library, _built = game
    real = interrupt_executable(monkeypatch, False)
    with pytest.raises(OSError):
        tweak_mods.restore(root, library)
    monkeypatch.setattr(tweak_mods, "atomic_write", real)
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
    root, library, built = game
    (root / tweak_mods.MANIFEST_FILE).write_text(json.dumps(entry))
    with pytest.raises(tweak_mods.TweakError, match="damaged"):
        tweak_mods.apply(root, library)
    assert image(game) == built


def test_oversized_journal_is_refused(game):
    root, library, built = game
    (root / tweak_mods.MANIFEST_FILE).write_bytes(b"x" * (tweak_mods.MAX_MANIFEST + 1))
    with pytest.raises(tweak_mods.TweakError, match="large"):
        tweak_mods.apply(root, library)
    assert image(game) == built


def test_cooperating_writers_do_not_enter_together(game):
    with tweak_mods._exclusive(game[0]):
        with pytest.raises(OSError):
            with tweak_mods._exclusive(game[0]):
                pytest.fail("The second writer acquired the same lock")
    with tweak_mods._exclusive(game[0]):
        pass


def test_corrupt_backup_is_not_used_for_restore(game):
    root, library, built = game
    (root / tweak_mods.BACKUP_FILE).write_bytes(b"bad")
    with pytest.raises(tweak_mods.TweakError, match="original"):
        tweak_mods.restore(root, library)
    assert image(game) == built


def test_a_pinned_executable_is_moved_aside_and_cleared_later(game, monkeypatch):
    """A crashed game Windows keeps listed pins the executable: Windows refuses
    to replace it but lets it be renamed. Lexeditor moves it aside, writes the
    original in its place, and deletes the moved file once it is free."""
    root, library, built = game
    real = tweak_mods.atomic_write
    refused = []

    def pinned(path, data):
        if Path(path).name == exe_patches.EXECUTABLE and not refused:
            refused.append(path)
            raise PermissionError(13, "Access is denied")
        real(path, data)
    monkeypatch.setattr(tweak_mods, "atomic_write", pinned)
    tweak_mods.restore(root, library)
    aside = root / (exe_patches.EXECUTABLE + tweak_mods.LOCKED_SUFFIX)
    assert image(game) == VANILLA and aside.read_bytes() == built
    assert not (root / tweak_mods.MANIFEST_FILE).exists()
    tweak_mods.apply(root, library)
    assert not aside.exists() and loader_installed(game)


def test_a_pinned_loader_is_moved_aside_when_switching_mods(game, monkeypatch):
    """The crashed game pins dinput8.dll as well as the executable (Lexer hit
    this switching Better Details off): it is moved aside too."""
    root, library, _built = game
    tweak_mods.apply(root, library)
    dll = root / tweak_mods.RUNTIME_DLL
    real_unlink = Path.unlink

    def pinned(self, *args, **kwargs):
        if self.name == tweak_mods.RUNTIME_DLL:
            raise PermissionError(13, "Access is denied")
        return real_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", pinned)
    result = tweak_mods.restore(root, library)
    assert result["state"] == "vanilla" and not dll.exists()
    assert (root / (tweak_mods.RUNTIME_DLL + tweak_mods.LOCKED_SUFFIX)).is_file()
    monkeypatch.setattr(Path, "unlink", real_unlink)
    tweak_mods.apply(root, library)
    assert dll.read_bytes() == tweak_mods.loader_bytes(online=True)
    assert not (root / (tweak_mods.RUNTIME_DLL + tweak_mods.LOCKED_SUFFIX)).exists()


def test_an_executable_that_cannot_be_moved_either_says_why(game, monkeypatch):
    root, library, built = game
    real = tweak_mods.atomic_write

    def pinned(path, data):
        if Path(path).name == exe_patches.EXECUTABLE:
            raise PermissionError(13, "Access is denied")
        real(path, data)
    monkeypatch.setattr(tweak_mods, "atomic_write", pinned)
    real_replace = tweak_mods.os.replace

    def unmovable(source, target):
        if Path(source).name == exe_patches.EXECUTABLE:
            raise PermissionError(13, "denied")
        real_replace(source, target)
    monkeypatch.setattr(tweak_mods.os, "replace", unmovable)
    with pytest.raises(tweak_mods.TweakError, match="restart Windows"):
        tweak_mods.restore(root, library)
    assert image(game) == built
    assert tweak_mods.status(root, library)["pendingRecovery"]


def test_game_start_before_replacement_leaves_recoverable_intent(game, monkeypatch):
    root, library, built = game
    calls = 0

    def game_closed():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise tweak_mods.TweakError("game started")

    monkeypatch.setattr(tweak_mods, "ensure_game_closed", game_closed)
    with pytest.raises(tweak_mods.TweakError, match="started"):
        tweak_mods.apply(root, library)
    assert image(game) == built
    assert tweak_mods.status(root, library)["pendingRecovery"]
