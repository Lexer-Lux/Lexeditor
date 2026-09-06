"""Real FF9 HTTP handler with isolated runtime/data fixtures, not game acceptance."""
import ast
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import pytest


@pytest.fixture
def service(tmp_path, monkeypatch):
    # A private fixture package isolates these dependencies from other FF9 tests.
    # The production server file is executed unchanged; only its backends are fake.
    package_name = "_ff9_http_fixture"
    package = types.ModuleType(package_name)
    package.__path__ = []
    monkeypatch.setitem(sys.modules, package_name, package)
    def dependency(name, **values):
        module = types.ModuleType(f"{package_name}.{name}")
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        setattr(package, name, module)
        return module
    paths = dependency("paths", GAME_ROOT=tmp_path / "game", PROJECT_ROOT=tmp_path / "project",
                       game_problems=lambda: [])
    paths.GAME_ROOT.mkdir()
    dependency("memoria_csv", DATASETS=(), MemoriaDataStore=lambda: None, catalog=lambda: [])
    class FakeBattleSceneStore:
        def status_rows(self):
            return []
    dependency("battle_scene", BattleSceneStore=FakeBattleSceneStore)
    dependency("memoria_baseline", ensure=lambda: {"release": "fixture", "source": "fixture", "problems": []})
    runtime = dependency("memoria_manager", status=lambda root: {"installed": False},
                         available=lambda: {"available": False})
    called = []
    for action in ("install", "recover", "open_settings"):
        def invoke(root, action=action):
            called.append(action)
            return {"action": action}
        setattr(runtime, action, invoke)
    file = Path(__file__).parents[1] / "games/ff9/server.py"
    spec = importlib.util.spec_from_file_location(f"{package_name}.server", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield module, server.server_address[1], called
    server.shutdown()
    server.server_close()
    thread.join(5)


def request(service, path, body=b"{}", headers=None, method="POST"):
    _, port, _ = service
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        content = response.read()
        return response.status, json.loads(content)
    finally:
        connection.close()


@pytest.mark.parametrize("route,action", [("install", "install"), ("recover", "recover"), ("settings", "open_settings")])
def test_runtime_routes_reachable_exactly_once(service, route, action):
    status, payload = request(service, "/api/runtime/" + route)
    assert status == 200 and payload == {"action": action}
    assert service[2] == [action]


@pytest.mark.parametrize("headers,status", [
    ({"Origin": "https://example.invalid"}, 403),
    ({"Origin": "null"}, 403),
    ({"Host": "example.invalid"}, 403),
    ({"Content-Type": "text/plain"}, 415),
    ({"Content-Type": "application/x-www-form-urlencoded"}, 415),
    ({"Content-Length": "99999999"}, 413),
    ({"Transfer-Encoding": "chunked"}, 400),
])
def test_untrusted_or_invalid_requests_cannot_start_patcher(service, headers, status):
    assert request(service, "/api/runtime/install", headers=headers)[0] == status
    assert not service[2]


def test_same_origin_post(service):
    assert request(service, "/api/runtime/install", headers={"Origin": f"http://127.0.0.1:{service[1]}"})[0] == 200


@pytest.mark.parametrize("body", [b"null", b"[]", b"true", b"broken"])
def test_json_object_required(service, body):
    assert request(service, "/api/runtime/install", body=body)[0] == 400
    assert not service[2]


def test_get_does_not_install(service):
    assert request(service, "/api/runtime/install", method="GET")[0] == 404
    assert not service[2]


def test_unknown_route_is_not_a_save_request(service):
    assert request(service, "/api/runtime/delete")[0] == 404
    assert not service[2]


def test_runtime_failure_returns_conflict(service, monkeypatch):
    def fail(root):
        raise RuntimeError("Close FF9 first")
    monkeypatch.setattr(service[0].memoria_manager, "install", fail)
    assert request(service, "/api/runtime/install") == (409, {"error": "Close FF9 first"})


@pytest.mark.parametrize("method,path", [("GET", "/api/platform-config"),
                                         ("POST", "/api/platform-config/save")])
def test_embedded_memoria_configuration_routes_are_removed(service, method, path):
    config = service[0].paths.GAME_ROOT / "Memoria.ini"
    original = b"[Unknown]\r\nCustom = 7 ; leave this alone\r\n"
    config.write_bytes(original)
    assert request(service, path, method=method)[0] == 404
    assert config.read_bytes() == original
    assert not service[2]


def test_dashboard_and_plugin_choose_launcher_for_play(service):
    _, dashboard = request(service, "/api/dashboard", method="GET")
    expected = service[0].paths.GAME_ROOT / "FF9_Launcher.exe"
    assert Path(dashboard["game"]["executable"]) == expected
    source = (Path(__file__).parents[1] / "games/ff9/plugin.py").read_text(encoding="utf-8")
    specs = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "GameInstallSpec"]
    assert len(specs) == 1
    values = {entry.arg: entry.value for entry in specs[0].keywords}
    assert ast.literal_eval(values["launch_path"]) == "FF9_Launcher.exe"


def test_data_map_reports_external_launcher_not_an_embedded_ini_editor(service):
    launcher = service[0].paths.GAME_ROOT / "FF9_Launcher.exe"
    launcher.write_bytes(b"fixture, never executed")
    _, data = request(service, "/api/datamap", method="GET")
    row = next(row for row in data["rows"] if row["filename"] == "FF9_Launcher.exe")
    assert row["status"] == "integrated" and row["target"] == "tweaks"
    assert "does not edit Memoria.ini" in row["notes"]
    assert not any(row["filename"] == "Memoria.ini" for row in data["rows"])
