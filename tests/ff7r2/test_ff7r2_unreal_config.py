"""Rebirth Engine Config endpoints reuse the shared Unreal editor (issue 478)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from plugins.ff7r2.plugin import Ff7r2Session


def _json(url: str, body: dict | None = None) -> dict:
    request = Request(url, method="POST" if body is not None else "GET")
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _session_env(root: Path, ini: Path) -> tuple[Path, dict[str, str]]:
    project = root / "RebirthMod"
    project.mkdir()
    (project / "lexeditor-project.json").write_text(
        '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
    return project, {
        "LEXEDITOR_FF7R2_PROJECT": str(project),
        "LEXEDITOR_FF7R2_ENGINE_INI": str(ini),
    }


def test_status_reports_discovery_catalogue_and_wiring():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-unreal-") as temp_name:
        root = Path(temp_name)
        ini = root / "Engine.ini"
        ini.write_text("[Core.System]\n", encoding="utf-8")
        _project, environment = _session_env(root, ini)
        with Ff7r2Session(environment) as session:
            report = _json(session.url + "api/unreal-config")
            assert report["game"] == "ff7r2"
            assert report["engine"] == "UE4"
            assert report["configDiscovered"] is True
            assert report["configExists"] is True
            assert report["overrides"] == {}
            assert report["advanced"], "catalogue must reach the page even unverified"
            for item in report["advanced"]:
                assert item["name"] and item["description"]
                assert item["type"] in ("int", "float", "choice")
            assert "unreal-config" in _json(session.url + "api/plugin")["capabilities"]
            rows = _json(session.url + "api/datamap")["rows"]
            assert any(row.get("target") == "tweaks"
                       and "WindowsNoEditor/Engine.ini" in row.get("filename", "")
                       for row in rows)


def test_apply_default_reset_round_trip_through_service():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-unreal-") as temp_name:
        root = Path(temp_name)
        ini = root / "Engine.ini"
        ini.write_text("[SystemSettings]\nr.BloomQuality=5\n", encoding="utf-8")
        _project, environment = _session_env(root, ini)
        with Ff7r2Session(environment) as session:
            applied = _json(session.url + "api/unreal-config/apply",
                            {"values": {"r.BloomQuality": 3, "r.MotionBlurQuality": 0}})
            assert applied["result"]["overrides"] == {
                "r.BloomQuality": "3", "r.MotionBlurQuality": "0"}
            assert applied["result"]["observed"] == {"r.BloomQuality": "5"}
            text = ini.read_text(encoding="utf-8")
            assert text.count("BEGIN LEXEDITOR UNREAL CONFIG (ff7r2)") == 1
            assert "r.BloomQuality=5" in text
            backups = list(root.glob("Engine.ini.lexeditor-*.bak"))
            assert len(backups) == 1
            assert backups[0].read_text(encoding="utf-8") == (
                "[SystemSettings]\nr.BloomQuality=5\n")

            defaulted = _json(session.url + "api/unreal-config/default",
                              {"key": "r.BloomQuality"})
            assert defaulted["result"]["overrides"] == {"r.MotionBlurQuality": "0"}

            reset = _json(session.url + "api/unreal-config/reset", {})
            assert reset["result"]["managedPresent"] is False
            text = ini.read_text(encoding="utf-8")
            assert "LEXEDITOR UNREAL CONFIG" not in text
            assert "r.BloomQuality=5" in text


def test_invalid_value_rejected_and_missing_file_reported():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-unreal-") as temp_name:
        root = Path(temp_name)
        ini = root / "Engine.ini"
        ini.write_text("[SystemSettings]\n", encoding="utf-8")
        _project, environment = _session_env(root, ini)
        with Ff7r2Session(environment) as session:
            try:
                _json(session.url + "api/unreal-config/apply",
                      {"values": {"r.MotionBlurQuality": 99}})
            except HTTPError as error:
                assert error.code == 400
                payload = json.loads(error.read().decode("utf-8"))
                assert "0 to 4" in payload["error"]
            else:
                raise AssertionError("Out-of-range CVar unexpectedly applied")
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-unreal-") as temp_name:
        root = Path(temp_name)
        missing = root / "Engine.ini"
        _project, environment = _session_env(root, missing)
        with Ff7r2Session(environment) as session:
            report = _json(session.url + "api/unreal-config")
            assert report["configDiscovered"] is False
            assert report["configExists"] is False
            assert report["advanced"], "catalogue stays visible without a file"


def test_engine_config_wiring_reuses_shared_editor_without_duplicates():
    root = Path(__file__).resolve().parents[2]
    editor = (root / "plugins/ff7r2/editor.js").read_text(encoding="utf-8")
    server = (root / "plugins/ff7r2/server.py").read_text(encoding="utf-8")
    assert '{id:"engine",label:"Engine Config"' in editor
    assert "/api/unreal-config" in editor
    assert "import unreal_config" in server
    for route in ("/api/unreal-config", "/api/unreal-config/apply",
                  "/api/unreal-config/default", "/api/unreal-config/reset",
                  "/api/unreal-config/refresh"):
        assert route in server, route
    assert "unreal_config.apply_settings" in server
    assert "unreal_config.use_game_default" in server
    assert "unreal_config.reset_all" in server
    assert "unreal_config.refresh_snapshot" in server
    assert (root / "plugins/ff7r2/unreal_config.py").exists() is False, \
        "the shared editor must not be copied per game"
