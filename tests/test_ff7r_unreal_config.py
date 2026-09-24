"""Remake Engine Config endpoints reuse the shared Unreal editor (issue 478)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from plugins.ff7r.plugin import FF7RSession
from service_session import request_json


def _session_env(root: Path, ini: Path) -> dict[str, str]:
    game = root / "game"
    (game / "End" / "Content" / "Paks").mkdir(parents=True, exist_ok=True)
    fixture = root / "fixture" / "End" / "Content" / "GameContents" / "DataObject"
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / "Equipment.uasset").write_bytes(b"fixture")
    (fixture / "Equipment.uexp").write_bytes(b"fixture")
    return {
        "LEXEDITOR_FF7R_ROOT": str(game),
        "LEXEDITOR_FF7R_DATA_ROOT": str(root / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(root / "project"),
        "LEXEDITOR_FF7R_ENGINE_INI": str(ini),
        "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(root / "fixture"),
    }


def test_status_reports_discovery_catalogue_unlocker_and_wiring(tmp_path):
    ini = tmp_path / "Engine.ini"
    ini.write_text("[Core.System]\n", encoding="utf-8")
    with FF7RSession(_session_env(tmp_path, ini)) as session:
        report = request_json(session.url + "api/unreal-config")
        assert report["game"] == "ff7r"
        assert report["engine"] == "UE4"
        assert report["configDiscovered"] is True
        assert report["configExists"] is True
        assert report["overrides"] == {}
        assert report["advanced"], "catalogue must reach the page even unverified"
        for item in report["advanced"]:
            assert item["name"] and item["description"]
            assert item["type"] in ("int", "float", "choice")
        assert report["iniUnlocker"] == {
            "verified": False, "candidatePresent": False}
        assert "unreal-config" in request_json(
            session.url + "api/plugin")["capabilities"]
        rows = request_json(session.url + "api/datamap")["rows"]
        assert any(row.get("target") == "tweaks"
                   and "WindowsNoEditor/Engine.ini" in row.get("filename", "")
                   and "REMAKE" in row.get("filename", "")
                   for row in rows)


def test_apply_default_reset_round_trip_through_service(tmp_path):
    ini = tmp_path / "Engine.ini"
    ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
    with FF7RSession(_session_env(tmp_path, ini)) as session:
        applied = request_json(
            session.url + "api/unreal-config/apply",
            {"values": {"r.BloomQuality": 3, "r.MotionBlurQuality": 0}})
        assert applied["result"]["overrides"] == {
            "r.BloomQuality": "3", "r.MotionBlurQuality": "0"}
        assert applied["result"]["observed"] == {"r.BloomQuality": "5"}
        assert applied["result"]["iniUnlocker"]["verified"] is False
        text = ini.read_text(encoding="utf-8")
        assert text.count("BEGIN LEXEDITOR FF7R EYE ADAPTATION") == 1
        assert "r.BloomQuality=5" in text
        backups = list(tmp_path.glob("Engine.ini.lexeditor-*.bak"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == (
            "[SystemSettings]\nr.BloomQuality=5\n")

        defaulted = request_json(
            session.url + "api/unreal-config/default",
            {"key": "r.BloomQuality"})
        assert defaulted["result"]["overrides"] == {"r.MotionBlurQuality": "0"}

        reset = request_json(session.url + "api/unreal-config/reset", {})
        assert reset["result"]["managedPresent"] is False
        text = ini.read_text(encoding="utf-8")
        assert "LEXEDITOR FF7R EYE ADAPTATION" not in text
        assert "r.BloomQuality=5" in text


def test_eye_adaptation_and_bad_values_rejected(tmp_path):
    ini = tmp_path / "Engine.ini"
    ini.write_text("[SystemSettings]\n", encoding="utf-8")
    with FF7RSession(_session_env(tmp_path, ini)) as session:
        with pytest.raises(HTTPError) as legacy:
            request_json(session.url + "api/unreal-config/apply",
                         {"values": {"r.EyeAdaptationQuality": 0}})
        assert legacy.value.code == 400
        payload = json.loads(legacy.value.read().decode("utf-8"))
        assert "existing game tweaks group" in payload["error"]
        with pytest.raises(HTTPError) as default:
            request_json(session.url + "api/unreal-config/default",
                         {"key": "r.EyeAdaptationQuality"})
        assert default.value.code == 400
        with pytest.raises(HTTPError) as bad:
            request_json(session.url + "api/unreal-config/apply",
                         {"values": {"r.MotionBlurQuality": 99}})
        assert bad.value.code == 400
        payload = json.loads(bad.value.read().decode("utf-8"))
        assert "0 to 4" in payload["error"]


def test_read_only_project_refuses_engine_config_writes(tmp_path):
    ini = tmp_path / "Engine.ini"
    ini.write_text("[SystemSettings]\n", encoding="utf-8")
    environment = _session_env(tmp_path, ini)
    environment["LEXEDITOR_MOD_READ_ONLY"] = "1"
    with FF7RSession(environment) as session:
        report = request_json(session.url + "api/unreal-config")
        assert report["game"] == "ff7r"
        with pytest.raises(HTTPError) as blocked:
            request_json(session.url + "api/unreal-config/apply",
                         {"values": {"r.BloomQuality": 3}})
        assert blocked.value.code == 403
        assert ini.read_text(encoding="utf-8") == "[SystemSettings]\n"


def test_legacy_ini_path_follows_redirected_documents(monkeypatch, tmp_path):
    from plugins.ff7r import graphics_tweaks

    docs = tmp_path / "Docs"
    monkeypatch.delenv("LEXEDITOR_FF7R_ENGINE_INI", raising=False)
    monkeypatch.setattr("unreal_config._shell_personal", lambda: docs)
    assert graphics_tweaks.engine_ini_path() == (
        docs / "My Games" / "FINAL FANTASY VII REMAKE" / "Saved"
        / "Config" / "WindowsNoEditor" / "Engine.ini")


def test_engine_config_wiring_reuses_shared_editor_without_duplicates():
    root = Path(__file__).resolve().parents[1]
    page = (root / "plugins/ff7r/editor.html").read_text(encoding="utf-8")
    assert page.count("/shared/unreal-config.js") == 1
    assert (page.index("/shared/unreal-config.js")
            > page.index("/shared/framework.js"))
    assert (page.index("/shared/unreal-config.js")
            < page.index('<script src="editor.js"'))
    editor = (root / "plugins/ff7r/editor.js").read_text(encoding="utf-8")
    assert "LexeditorUnrealConfig.createPanel" in editor
    assert 'route:"/api/unreal-config"' in editor
    assert "enginePanel.element()" in editor
    assert "ENGINE CONFIG" not in editor
    server = (root / "plugins/ff7r/server.py").read_text(encoding="utf-8")
    assert "import unreal_config" in server
    for route in ("/api/unreal-config", "/api/unreal-config/apply",
                  "/api/unreal-config/default", "/api/unreal-config/reset",
                  "/api/unreal-config/refresh"):
        assert route in server, route
    assert "unreal_config.apply_settings" in server
    assert "unreal_config.use_game_default" in server
    assert "unreal_config.reset_all" in server
    assert "unreal_config.refresh_snapshot" in server
    assert (root / "plugins/ff7r/unreal_config.py").exists() is False, \
        "the shared editor must not be copied per game"
