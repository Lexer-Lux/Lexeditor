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

from games.ff9 import memoria_manager as manager
from games.ff9.memoria_patcher import MAGIC, inspect_payload, installation_files
from games.ff9.memoria_recovery import Recovery, digest, root_key, install_lock


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


@pytest.mark.parametrize("status", ["enabled", "recovery-required"])
def test_configuration_write_is_serialized(setup, status):
    root, kwargs, _, _ = setup
    with manager.configuration_write(root, kwargs["state_path"]):
        pass
