"""Offline tests; fixture bytes are not a game executable or publisher binary."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

from plugins.ff9 import memoria_manager as manager
from plugins.ff9 import memoria_update as update
from plugins.ff9.plugin import PLUGIN
from plugins.ff9.memoria_patcher import MAGIC, inspect_payload, installation_files
from plugins.ff9.memoria_recovery import Recovery, digest, root_key, install_lock


def pack(files, *, signed=False):
    stream, dictionary = bytearray(), {}
    for name, data in files.items():
        parts = name.split("/")
        stream.extend(struct.pack("<IqB", len(data), 0, len(parts)))
        for part in parts:
            if part not in dictionary:
                key = len(dictionary)
                dictionary[part] = key
                encoded = part.encode("utf-8")
                stream.extend(struct.pack("<HB", key | 0x8000, len(encoded)) + encoded)
            else:
                stream.extend(struct.pack("<H", dictionary[part]))
        stream.extend(data)
    prefix = b"MZ-test-fixture-not-an-executable"
    result = prefix + gzip.compress(stream, mtime=0) + MAGIC + struct.pack("<qq", sum(map(len, files.values())), len(prefix))
    return result + (b"certificate-fixture" * 500 if signed else b"")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "game"
    for platform in ("x64", "x86"):
        target = root / platform / "FF9_Data" / "Managed" / "Assembly-CSharp.dll"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"vanilla assembly " + platform.encode())
        (root / platform / "FF9.exe").write_bytes(b"vanilla game")
    (root / "FF9_Launcher.exe").write_bytes(b"vanilla launcher")
    files = {
        "{PLATFORM}/FF9_Data/Managed/Assembly-CSharp.dll": b"patched assembly",
        "{PLATFORM}/FF9_Data/Managed/Memoria.Prime.dll": b"memoria fixture",
        "FF9_Launcher.exe": b"settings launcher",
        "Memoria.ini": b"[Memoria]\r\nEnabled = 1\r\n",
        "Settings.ini": b"[Settings]\nEnabled = 1\n",
    }
    data = pack(files)
    metadata = {"tag_name": manager.PINNED_RELEASE, "assets": [{"name": manager.ASSET_NAME,
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "size": len(data),
        "browser_download_url": manager.REPOSITORY + "/releases/download/" + manager.PINNED_RELEASE + "/" + manager.ASSET_NAME}]}
    def fetch_json(_url):
        return metadata
    def fetch_file(_url, target, _progress):
        target.write_bytes(data)
    def runner(_argv, cwd):
        for name, value in files.items():
            for platform in (("x64", "x86") if "{PLATFORM}" in name else (None,)):
                target = cwd / (name.replace("{PLATFORM}", platform) if platform else name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
        return 0
    monkeypatch.setattr(manager, "_game_running", lambda _root: False)
    kwargs = dict(fetch_json=fetch_json, fetch_file=fetch_file, runner=runner,
                  state_path=tmp_path / "state" / "memoria.json", cache_root=tmp_path / "cache")
    return root, kwargs, files, metadata


def test_unsigned_and_signed_payload(tmp_path):
    for signed in (False, True):
        path = tmp_path / "patcher.exe"
        path.write_bytes(pack({"Data/A.txt": b"first", "Data/B.txt": b"second"}, signed=signed))
        result = inspect_payload(path)
        assert [x.relative_path for x in result] == ["Data/A.txt", "Data/B.txt"]
        assert result[1].sha256 == hashlib.sha256(b"second").hexdigest()


@pytest.mark.parametrize("name", ["../escape", "/escape", "C:/escape", "path/..", "path/CON.txt", "path/link\\escape", "path/trailing."])
def test_reject_unsafe_payload_paths(tmp_path, name):
    path = tmp_path / "bad.exe"
    path.write_bytes(pack({name: b"x"}))
    with pytest.raises(ValueError):
        inspect_payload(path)


def test_reject_bad_footer_and_truncation(tmp_path):
    path = tmp_path / "bad.exe"
    for value in (b"bad", pack({"ok.txt": b"data"})[:-1], pack({"ok.txt": b"data"}).replace(MAGIC, b"BADMAGIC")):
        path.write_bytes(value)
        with pytest.raises(ValueError):
            inspect_payload(path)


def test_refuse_x64_only_before_run(setup):
    root, kwargs, _, _ = setup
    shutil.rmtree(root / "x86")
    kwargs["runner"] = lambda *_: pytest.fail("must not run")
    with pytest.raises(RuntimeError, match="x64 and x86"):
        manager.install(root, **kwargs)
    assert (root / "FF9_Launcher.exe").read_bytes() == b"vanilla launcher"


@pytest.mark.parametrize("mutation", ["wrong-tag", "draft", "prerelease", "wrong-url", "bad-digest", "duplicate", "too-large"])
def test_release_pin_validation(setup, mutation):
    _, kwargs, _, meta = setup
    if mutation == "wrong-tag": meta["tag_name"] = "v2099.1"
    if mutation in {"draft", "prerelease"}: meta[mutation] = True
    if mutation == "wrong-url": meta["assets"][0]["browser_download_url"] = "https://example.com/patcher.exe"
    if mutation == "bad-digest": meta["assets"][0]["digest"] = "sha256:abc"
    if mutation == "duplicate": meta["assets"].append(meta["assets"][0].copy())
    if mutation == "too-large": meta["assets"][0]["size"] = manager.MAX_ASSET_BYTES + 1
    with pytest.raises(RuntimeError): manager.release(kwargs["fetch_json"])


def test_install_verified_and_root_scoped(setup, tmp_path):
    root, kwargs, _, _ = setup
    result = manager.install(root, **kwargs)
    assert result["installed"] and result["version"] == manager.PINNED_RELEASE
    assert not result["recoveryRequired"]
    assert manager.status(tmp_path / "other", kwargs["state_path"])["version"] == ""
    (root / manager.MANAGED_RELATIVE / "Memoria.Prime.dll").write_bytes(b"manual replacement")
    assert manager.status(root, kwargs["state_path"])["version"] == ""


def test_preserve_existing_configuration_byte_for_byte(setup):
    root, kwargs, _, _ = setup
    original = b"\xef\xbb\xbf; custom comment\r\n[Unknown]\r\nVersion = Fake\r\nThing=\"mine\"  ; keep me\r\n"
    (root / "Memoria.ini").write_bytes(original)
    manager.install(root, **kwargs)
    assert (root / "Memoria.ini").read_bytes() == original


@pytest.mark.parametrize("failure", ["exit", "exception", "false-success", "partial", "timeout"])
def test_rollback_restores_previous_files(setup, failure):
    root, kwargs, _, _ = setup
    old_config = b"[Unknown]\nsetting = old\n"
    (root / "Memoria.ini").write_bytes(old_config)
    scripts = root / "StreamingAssets/Assets/Resources/CommonAsset/Field/test.txt"
    scripts.parent.mkdir(parents=True)
    scripts.write_bytes(b"my field script")
    original = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    success = kwargs["runner"]
    def fail(argv, cwd):
        success(argv, cwd)
        shutil.rmtree(root / "StreamingAssets/Assets/Resources/CommonAsset")
        if failure == "exit": return 7
        if failure == "exception": raise OSError("fixture error")
        if failure == "timeout": raise subprocess.TimeoutExpired(argv, 900)
        (root / "x64/FF9_Data/Managed/Assembly-CSharp.dll").write_bytes(b"incomplete")
        return 0
    kwargs["runner"] = fail
    with pytest.raises(RuntimeError, match="previous game files were restored"):
        manager.install(root, **kwargs)
    actual = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert actual == original
    assert not manager.status(root, kwargs["state_path"])["recoveryRequired"]


def test_failed_download_cleans_partial_file(setup):
    root, kwargs, _, _ = setup
    def fail(_url, target, _progress):
        target.write_bytes(b"truncated")
        raise OSError("network lost")
    kwargs["fetch_file"] = fail
    with pytest.raises(OSError): manager.install(root, **kwargs)
    assert not list(kwargs["cache_root"].glob("*.part"))


def test_cached_checksum_is_rechecked(setup):
    root, kwargs, _, _ = setup
    manager.install(root, **kwargs)
    target = kwargs["cache_root"] / f"Memoria-{manager.PINNED_RELEASE}.exe"
    target.write_bytes(b"corrupted cache")
    manager.install(root, **kwargs)
    assert target.read_bytes().startswith(b"MZ-test")


def test_game_started_during_download_is_refused(setup, monkeypatch):
    root, kwargs, _, _ = setup
    states = iter([False, True])
    monkeypatch.setattr(manager, "_game_running", lambda _: next(states))
    kwargs["runner"] = lambda *_: pytest.fail("game running: must not patch")
    with pytest.raises(RuntimeError, match="Close Final Fantasy"):
        manager.install(root, **kwargs)
    assert (root / "FF9_Launcher.exe").read_bytes() == b"vanilla launcher"


def test_same_root_concurrent_operation_is_refused(setup):
    root, kwargs, _, _ = setup
    with install_lock(root, manager._control_root(kwargs["state_path"])):
        with pytest.raises(RuntimeError, match="Another Memoria operation"):
            manager.install(root, **kwargs)


def test_legacy_record_never_leaks_version(setup, tmp_path):
    root, kwargs, _, _ = setup
    manager._save_state({"gameRoot": str(tmp_path / "unrelated"), "version": "v9999"}, kwargs["state_path"])
    result = manager.status(root, kwargs["state_path"])
    assert result["version"] == "" and result["lastInstalled"] == ""


def test_linked_destination_refused_before_patching(setup, tmp_path):
    root, kwargs, _, _ = setup
    outside = tmp_path / "outside.ini"
    outside.write_text("private", encoding="utf-8")
    (root / "Memoria.ini").symlink_to(outside)
    kwargs["runner"] = lambda *_: pytest.fail("must not patch symlink")
    with pytest.raises(RuntimeError, match="linked path"):
        manager.install(root, **kwargs)
    assert outside.read_text() == "private"


def test_no_rollback_while_game_open_and_explicit_recovery(setup, monkeypatch):
    root, kwargs, _, _ = setup
    original = (root / "FF9_Launcher.exe").read_bytes()
    success = kwargs["runner"]
    running = False
    monkeypatch.setattr(manager, "_game_running", lambda _: running)
    def fail(argv, cwd):
        nonlocal running
        success(argv, cwd)
        running = True
        return 9
    kwargs["runner"] = fail
    with pytest.raises(RuntimeError, match="Recovery is required"):
        manager.install(root, **kwargs)
    assert manager.status(root, kwargs["state_path"])["recoveryRequired"]
    running = False
    result = manager.recover(root, kwargs["state_path"])
    assert not result["recoveryRequired"]
    assert (root / "FF9_Launcher.exe").read_bytes() == original


def test_damaged_backup_is_not_restored(setup):
    root, kwargs, _, _ = setup
    patcher, _ = manager.stage(fetch_json=kwargs["fetch_json"], fetch_file=kwargs["fetch_file"], cache_root=kwargs["cache_root"])
    recovery = Recovery.prepare(root, installation_files(inspect_payload(patcher), root), kwargs["cache_root"] / "backups")
    (recovery.folder / "files/FF9_Launcher.exe").write_bytes(b"damaged")
    (root / "FF9_Launcher.exe").write_bytes(b"new")
    with pytest.raises(RuntimeError, match="damaged"):
        recovery.rollback()
    assert (root / "FF9_Launcher.exe").read_bytes() == b"new"


def test_recovery_can_acquire_lock_after_owner_crashes(setup):
    root, kwargs, _, _ = setup
    control = manager._control_root(kwargs["state_path"])
    script = """import os,sys
from pathlib import Path
from plugins.ff9.memoria_recovery import install_lock
with install_lock(Path(sys.argv[1]), Path(sys.argv[2])):
    os._exit(17)
"""
    result = subprocess.run([sys.executable, "-c", script, str(root), str(control)],
                            cwd=Path(__file__).parents[1], timeout=10)
    assert result.returncode == 17
    with install_lock(root, control, recover_stale=True):
        assert (control / (root_key(root) + ".lock")).is_file()


def test_recovery_does_not_clear_live_process_lock(setup):
    root, kwargs, _, _ = setup
    control = manager._control_root(kwargs["state_path"])
    script = """import sys
from pathlib import Path
from plugins.ff9.memoria_recovery import install_lock
with install_lock(Path(sys.argv[1]), Path(sys.argv[2])):
    print('locked', flush=True)
    sys.stdin.readline()
"""
    process = subprocess.Popen([sys.executable, "-c", script, str(root), str(control)],
                               cwd=Path(__file__).parents[1], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(RuntimeError, match="Another Memoria operation"):
            with install_lock(root, control, recover_stale=True):
                pass
    finally:
        process.communicate("done\n", timeout=10)
    assert process.returncode == 0
    with install_lock(root, control):
        pass


def test_install_disables_memoria_launcher_updates_and_preserves_other_settings(setup):
    root, kwargs, _, _ = setup
    original = (b"\xef\xbb\xbf; keep comment\r\n[Memoria]\r\n"
                b"CheckUpdates = True ; keep suffix\r\nOther = Mine\r\n"
                b"[Settings]\r\nWindowMode = 3\r\n")
    (root / "Settings.ini").write_bytes(original)
    result = manager.install(root, **kwargs)
    expected = original.replace(b"CheckUpdates = True", b"CheckUpdates = False")
    assert (root / "Settings.ini").read_bytes() == expected
    assert result["updatesDisabled"] is True


def test_first_install_adds_disabled_update_setting(setup):
    root, kwargs, _, _ = setup
    result = manager.install(root, **kwargs)
    settings = (root / "Settings.ini").read_text(encoding="utf-8")
    assert "[Settings]\nEnabled = 1" in settings
    assert "[Memoria]\nCheckUpdates = False" in settings
    assert result["updatesDisabled"] is True


def test_disable_launcher_updates_preserves_cp1252_and_missing_final_newline(tmp_path):
    path = tmp_path / "Settings.ini"
    raw = "[Memoria]\r\nName = Caf\xe9\r\nCheckUpdates=True;note".encode("cp1252")
    path.write_bytes(manager._disable_launcher_updates(raw))
    assert path.read_bytes() == "[Memoria]\r\nName = Caf\xe9\r\nCheckUpdates=False;note".encode("cp1252")
    assert manager._launcher_updates_disabled(path)


def test_shared_updates_contract_is_metadata_only(tmp_path):
    assert PLUGIN.helper_name == "Memoria"
    assert PLUGIN.helper_pinned == manager.PINNED_RELEASE
    assert callable(PLUGIN.helper_upstream)
    assert callable(PLUGIN.helper_install_for_root)
    # plugin_api rejects declaring both install shapes; the host serves
    # the Updates drawer and readiness from the root-aware hooks.
    assert PLUGIN.helper_install is None and PLUGIN.helper_status is None
    calls = []
    payload = {"tag_name": manager.PINNED_RELEASE, "draft": False, "prerelease": False,
               "published_at": "2025-07-04T20:27:01Z"}
    result = update.upstream_release(fetch_json=lambda url: calls.append(url) or payload,
                                     cache_path=tmp_path / "upstream.json", force=True)
    assert calls == [manager.LATEST_RELEASE_API]
    assert result["pinned"] == manager.PINNED_RELEASE
    assert result["latest"] == manager.PINNED_RELEASE and result["behind"] is False
    assert not (tmp_path / "Memoria.Patcher.exe").exists()


def test_pinned_helper_metadata_is_repository_owned():
    release = manager.pinned_release()
    assert release["version"] == manager.PINNED_RELEASE
    assert release["url"] == manager.PINNED_ASSET_URL
    assert release["sha256"] == manager.PINNED_ASSET_SHA256
    assert release["size"] == manager.PINNED_ASSET_SIZE
    assert release["published"] == manager.PINNED_PUBLISHED_AT


def test_stage_default_uses_repository_pin_without_metadata_lookup(tmp_path, monkeypatch):
    payload = b"synthetic pinned helper"
    metadata = {
        "version": manager.PINNED_RELEASE, "published": "fixture",
        "name": manager.ASSET_NAME, "url": manager.PINNED_ASSET_URL,
        "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload),
        "source": manager.REPOSITORY,
    }
    monkeypatch.setattr(manager, "pinned_release", lambda: metadata)
    calls = []
    def fetch_file(url, target, progress):
        calls.append(url)
        target.write_bytes(payload)
    staged, published = manager.stage(fetch_file=fetch_file, cache_root=tmp_path)
    assert calls == [manager.PINNED_ASSET_URL]
    assert staged.read_bytes() == payload and published == metadata


def test_real_patcher_shape_without_settings_is_recoverable(setup):
    root, kwargs, files, metadata = setup
    files.pop("Settings.ini")
    payload = pack(files)
    metadata["assets"][0]["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    metadata["assets"][0]["size"] = len(payload)
    kwargs["fetch_file"] = lambda _url, target, _progress: target.write_bytes(payload)
    result = manager.install(root, **kwargs)
    assert result["installed"] and result["updatesDisabled"]
    settings = root / manager.SETTINGS_NAME
    assert settings.is_file()
    assert settings.read_bytes() == b"[Memoria]\r\nCheckUpdates = False\r\n"


def test_new_settings_file_is_removed_if_install_rolls_back(setup, monkeypatch):
    root, kwargs, files, metadata = setup
    files.pop("Settings.ini")
    payload = pack(files)
    metadata["assets"][0]["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    metadata["assets"][0]["size"] = len(payload)
    kwargs["fetch_file"] = lambda _url, target, _progress: target.write_bytes(payload)
    real_status = manager.status
    def reject_after_settings(game_root, state_path=manager.STATE_PATH):
        value = real_status(game_root, state_path)
        if (Path(game_root) / manager.SETTINGS_NAME).is_file():
            value = {**value, "installed": False}
        return value
    monkeypatch.setattr(manager, "status", reject_after_settings)
    with pytest.raises(RuntimeError, match="previous game files were restored"):
        manager.install(root, **kwargs)
    assert not (root / manager.SETTINGS_NAME).exists()
