"""Exercise the real FF9 HTTP handler; platform-config implementation is isolated."""
from contextlib import contextmanager
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
    platform = types.ModuleType("platform_config")
    platform.load_config = lambda *args: {"available": False, "sections": []}
    platform.save_config = lambda *args: {"saved": True}
    monkeypatch.setitem(sys.modules, "platform_config", platform)
    file = Path(__file__).parents[1] / "games/ff9/server.py"
    spec = importlib.util.spec_from_file_location("games.ff9._http_test", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.paths, "GAME_ROOT", tmp_path / "game")
    called = []
    for action in ("install", "recover", "open_settings"):
        def invoke(root, action=action):
            called.append(action)
            return {"action": action}
        monkeypatch.setattr(module.memoria_manager, action, invoke)
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
        # A second HTTP response concatenated into the first used to be possible.
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


def test_config_save_uses_installation_guard(service, monkeypatch):
    events = []
    @contextmanager
    def guard(root):
        events.append("lock")
        yield
        events.append("unlock")
    monkeypatch.setattr(service[0].memoria_manager, "configuration_write", guard)
    monkeypatch.setattr(service[0], "save_config", lambda *args: events.append("save") or {"saved": True})
    assert request(service, "/api/platform-config/save")[0] == 200
    assert events == ["lock", "save", "unlock"]
