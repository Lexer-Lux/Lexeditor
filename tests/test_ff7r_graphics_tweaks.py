from __future__ import annotations

import json
from pathlib import Path

import pytest

from games.ff7r.graphics_dataobject import (
    load_graphics_virtual_package,
    save_graphics_virtual_package,
)
from games.ff7r.graphics_tweaks import (
    EYE_ADAPTATION_CVAR,
    GRAPHICS_SCHEMA_VERSION,
    MANAGED_BEGIN,
    MANAGED_END,
    deploy_graphics_tweaks,
    detect_ini_unlocker,
    graphics_status,
    save_graphics_config,
)


def _binary_root(game: Path) -> Path:
    root = game / "End" / "Binaries" / "Win64"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_verified_hook(game: Path, *, name: str = "xinput1_3.dll") -> Path:
    target = _binary_root(game) / name
    target.write_bytes(
        b"MZ fixture FFVIIHook Engine.ini WindowsNoEditor ff7remake_ ConsoleVariables"
    )
    return target


def test_ini_unlocker_requires_engine_ini_and_ff7_context(tmp_path):
    game = tmp_path / "game"
    binary = _binary_root(game)
    (binary / "xinput1_3.dll").write_bytes(b"MZ unrelated proxy")
    status = detect_ini_unlocker(game)
    assert status["candidatePresent"] is True
    assert status["verified"] is False

    (binary / "xinput1_3.dll").write_bytes(b"MZ Engine.ini ff7remake_")
    status = detect_ini_unlocker(game)
    assert status["verified"] is True
    assert status["verifiedPaths"] == [str(binary / "xinput1_3.dll")]


def test_deploy_enabled_appends_managed_block_and_preserves_user_ini(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _write_verified_hook(game)
    ini = tmp_path / "Documents" / "Engine.ini"
    ini.parent.mkdir(parents=True)
    original_text = "[SystemSettings]\nr.MotionBlurQuality=0\n"
    ini.write_bytes(b"\xef\xbb\xbf" + original_text.encode("utf-8"))
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(ini))
    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": True,
    })

    result = deploy_graphics_tweaks(game, project)
    raw = ini.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.startswith(original_text)
    assert text.count(MANAGED_BEGIN) == 1
    assert text.count(MANAGED_END) == 1
    assert EYE_ADAPTATION_CVAR in text
    assert text.rstrip().endswith(MANAGED_END)
    assert result["managedOverridePresent"] is True
    assert result["iniUnlockerVerified"] is True
    assert result["restartRequired"] is True

    status = graphics_status(game, project)
    assert status["disableEyeAdaptationRequested"] is True
    assert status["managedOverridePresent"] is True
    assert status["managedOverrideEffectiveAtEnd"] is True
    assert status["deployReady"] is True


def test_redeploy_replaces_one_managed_block_without_duplication(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _write_verified_hook(game)
    ini = tmp_path / "Engine.ini"
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(ini))
    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": True,
    })

    deploy_graphics_tweaks(game, project)
    first = ini.read_text(encoding="utf-8")
    deploy_graphics_tweaks(game, project)
    second = ini.read_text(encoding="utf-8")
    assert second == first
    assert second.count(MANAGED_BEGIN) == 1


def test_disabling_removes_only_managed_block(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _write_verified_hook(game)
    ini = tmp_path / "Engine.ini"
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(ini))
    original = "[SystemSettings]\nr.MotionBlurQuality=0\n"
    ini.write_text(original, encoding="utf-8")

    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": True,
    })
    deploy_graphics_tweaks(game, project)
    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": False,
    })
    result = deploy_graphics_tweaks(game, project)

    assert ini.read_text(encoding="utf-8") == original
    assert result["managedOverridePresent"] is False
    assert EYE_ADAPTATION_CVAR not in ini.read_text(encoding="utf-8")


def test_graphics_deploy_refuses_unverified_proxy_without_touching_ini(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    binary = _binary_root(game)
    (binary / "xinput1_3.dll").write_bytes(b"MZ unrelated proxy")
    ini = tmp_path / "Engine.ini"
    ini.write_text("[SystemSettings]\nr.MotionBlurQuality=0\n", encoding="utf-8")
    before = ini.read_bytes()
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(ini))
    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": True,
    })

    with pytest.raises(RuntimeError, match="not verified"):
        deploy_graphics_tweaks(game, project)
    assert ini.read_bytes() == before


def test_graphics_virtual_game_data_save_round_trip(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _write_verified_hook(game)
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(tmp_path / "Engine.ini"))

    package, source_sha, using_project = load_graphics_virtual_package(game, project)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    properties = {row["name"]: row for row in payload["properties"]}
    assert properties["DisableEyeAdaptation"]["editable"] is True
    assert properties["IniUnlockerVerified"]["editable"] is False
    assert payload["records"][0]["values"]["DisableEyeAdaptation"] is False
    assert payload["records"][0]["values"]["IniUnlockerVerified"] is True

    result = save_graphics_virtual_package(
        project,
        source_sha256=payload["sourceSha256"],
        active_sha256=payload["activeSha256"],
        edits=[{"entry": 0, "property": "DisableEyeAdaptation", "value": True}],
    )
    assert result["saved"] == 1
    saved = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert saved["disableEyeAdaptation"] is True

    refreshed, _source_sha, _using_project = load_graphics_virtual_package(game, project)
    assert refreshed.entries[0].values["DisableEyeAdaptation"] is True


def test_graphics_virtual_rejects_read_only_and_stale_edits(monkeypatch, tmp_path):
    game = tmp_path / "game"
    project = tmp_path / "project"
    _write_verified_hook(game)
    monkeypatch.setenv("LEXEDITOR_FF7R_ENGINE_INI", str(tmp_path / "Engine.ini"))
    package, source_sha, _using_project = load_graphics_virtual_package(game, project)
    payload = package.api_payload(source_sha256=source_sha)

    with pytest.raises(ValueError, match="read-only or unknown"):
        save_graphics_virtual_package(
            project,
            source_sha256=source_sha,
            active_sha256=payload["activeSha256"],
            edits=[{"entry": 0, "property": "IniUnlockerVerified", "value": False}],
        )

    save_graphics_config(project, {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": True,
    })
    with pytest.raises(RuntimeError, match="changed on disk"):
        save_graphics_virtual_package(
            project,
            source_sha256=source_sha,
            active_sha256=payload["activeSha256"],
            edits=[{"entry": 0, "property": "DisableEyeAdaptation", "value": False}],
        )
