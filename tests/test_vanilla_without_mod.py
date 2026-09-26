"""Issue 567: a game with no mod yet opens on vanilla, locked read-only.

No mod is the normal first state of every game, not a warning. Home shows
such a game as ready; opening it tells the plugin service there is no mod
(LEXEDITOR_VANILLA) so it reads vanilla data and refuses every write; and
creating or choosing a mod reopens it unlocked. A mod the player chose that
has since vanished is a real problem and keeps its warning.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from desktop_host import HostApi
from plugin_api import GamePlugin, ModProjectSpec
from plugin_http import PluginRequestHandler
from project_manager import ProjectManager


class _Session:
    """A plugin service stand-in that records what it was told."""

    started: list[dict] = []

    def __init__(self, environment: dict | None = None):
        self.environment = dict(environment or {})
        self.url = "http://127.0.0.1:1/"

    def start(self) -> dict:
        _Session.started.append(self.environment)
        return {"pluginId": "probe-game", "hosted": True}

    def stop(self) -> None:
        pass


def _plugin(default_root: Path, template: Path) -> GamePlugin:
    return GamePlugin(
        plugin_id="probe-game", name="Probe Game", accent="#000000",
        check=lambda: [], launch=lambda: 0, session_factory=_Session,
        projects=ModProjectSpec(
            root_env="LEXEDITOR_PROBE_PROJECT", default_root=default_root,
            required_paths=("marker.json",), template_root=template,
        ),
    )


@pytest.fixture
def template(tmp_path):
    root = tmp_path / "template"
    root.mkdir()
    (root / "marker.json").write_text("{}", encoding="utf-8")
    return root


def _host(tmp_path, plugin) -> HostApi:
    return HostApi({"probe-game": plugin}, enforce_installations=False, auto_scan=False,
                   projects=ProjectManager({"probe-game": plugin}, tmp_path / "projects.json"))


def test_no_mod_is_vanilla_not_a_problem(tmp_path, template):
    missing = tmp_path / "mods" / "probe" / "My Mod"
    manager = ProjectManager({"probe-game": _plugin(missing, template)}, tmp_path / "projects.json")
    snapshot = manager.snapshot("probe-game")
    assert snapshot["vanilla"] is True
    assert not any(row["current"] for row in snapshot["projects"]), snapshot["projects"]
    assert not any(row["problems"] for row in snapshot["projects"]), snapshot["projects"]
    assert not missing.exists(), "vanilla must not create a placeholder mod"


def test_chosen_mod_that_vanished_keeps_its_warning(tmp_path, template):
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    (chosen / "marker.json").write_text("{}", encoding="utf-8")
    manager = ProjectManager({"probe-game": _plugin(tmp_path / "absent", template)}, tmp_path / "projects.json")
    manager.select("probe-game", str(chosen))
    (chosen / "marker.json").unlink()
    chosen.rmdir()
    snapshot = manager.snapshot("probe-game")
    assert snapshot["vanilla"] is False
    current = next(row for row in snapshot["projects"] if row["current"])
    assert not current["valid"]
    assert "Project folder not found" in current["problems"][0], current["problems"]


def test_removing_the_open_mod_returns_to_vanilla(tmp_path, template):
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    (chosen / "marker.json").write_text("{}", encoding="utf-8")
    manager = ProjectManager({"probe-game": _plugin(tmp_path / "absent", template)}, tmp_path / "projects.json")
    manager.select("probe-game", str(chosen))
    snapshot = manager.forget("probe-game", str(chosen))
    assert snapshot["vanilla"] is True
    assert chosen.is_dir(), "removing a mod from the list never deletes it"


def test_home_shows_no_mod_ready_and_broken_mod_warning(tmp_path, template):
    api = _host(tmp_path, _plugin(tmp_path / "absent", template))
    try:
        row = api.plugins()[0]
        assert row["status"] != "warning", row
        assert row["ready"] is True, row
        assert row["noMod"] is True, row
        broken = tmp_path / "broken"
        broken.mkdir()
        (broken / "marker.json").write_text("{}", encoding="utf-8")
        api._projects.select("probe-game", str(broken))
        (broken / "marker.json").unlink()
        row = api.plugins()[0]
        assert row["status"] == "warning", row
        assert "marker.json" in row["problem"], row
    finally:
        api.dispose()


def test_opening_without_a_mod_is_locked_and_creating_one_unlocks(tmp_path, template, monkeypatch):
    _Session.started.clear()
    default = tmp_path / "absent"
    api = _host(tmp_path, _plugin(default, template))
    try:
        api.open_plugin("probe-game")
        environment = _Session.started[-1]
        assert environment["LEXEDITOR_VANILLA"] == "1"
        assert environment["LEXEDITOR_MOD_READ_ONLY"] == "1"
        assert api.vanilla_session() == {"pluginId": "probe-game", "vanilla": True}
        assert not default.exists(), "opening vanilla must not create a mod"

        parent = tmp_path / "library"
        parent.mkdir()
        monkeypatch.setattr(api, "_choose_folder", lambda *_args: str(parent))
        result = api.create_mod_project("probe-game", "First Mod")
        assert not result.get("vanilla"), result
        environment = _Session.started[-1]
        assert environment["LEXEDITOR_VANILLA"] == "0"
        assert environment["LEXEDITOR_MOD_READ_ONLY"] == "0"
        assert Path(environment["LEXEDITOR_PROBE_PROJECT"]) == (parent / "First Mod").resolve()
        assert api.vanilla_session()["vanilla"] is False
    finally:
        api.dispose()


class _Service(PluginRequestHandler):
    READ_ONLY_SAFE_ROUTES = ("/api/preview",)
    writes: list[str] = []

    def do_GET(self):
        self.send_json({"value": 7})

    def do_POST(self):
        _Service.writes.append(self.path)
        self.send_json({"saved": True})


def _request(port: int, path: str, method: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", method=method,
        data=b"{}" if method == "POST" else None, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@pytest.mark.parametrize("vanilla", [True, False])
def test_every_plugin_service_refuses_writes_in_vanilla(monkeypatch, vanilla):
    monkeypatch.setenv("LEXEDITOR_VANILLA", "1" if vanilla else "0")
    _Service.writes.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Service)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        assert _request(port, "/api/rows", "GET") == (200, {"value": 7})
        status, body = _request(port, "/api/save", "POST")
        if vanilla:
            assert status == 403 and body["readOnly"] is True, body
            assert "Find a Mod" in body["error"]
            assert _Service.writes == []
        else:
            assert status == 200 and _Service.writes == ["/api/save"]
        assert _request(port, "/api/preview", "POST")[0] == 200
    finally:
        server.shutdown()
        server.server_close()


def test_every_real_plugin_handler_is_guarded():
    """No plugin service may accept writes without the shared lock."""
    root = Path(__file__).resolve().parents[1] / "plugins"
    sources = sorted(root.glob("*/server.py"))
    assert sources
    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert "(BaseHTTPRequestHandler):" not in text.replace(
            "class PluginRequestHandler(BaseHTTPRequestHandler):", ""), (
            f"{source} serves writes without the shared read-only guard")
