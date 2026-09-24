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
    dependency("memoria_csv", MemoriaDataStore=lambda: None, catalog=lambda: [])
    class FakeBattleSceneStore:
        KEYS = frozenset({"enemies", "encounters", "enemy-attacks", "scene-flags"})
        def status_rows(self): return []
    dependency("battle_scene", BattleSceneStore=FakeBattleSceneStore)
    class FakeFieldWalkmeshStore:
        KEY = "field-walkmesh"
        KEYS = frozenset({"field-walkmesh", "field-walkmesh-triangles"})
        def status_rows(self): return []
    dependency("field_walkmesh", FieldWalkmeshStore=FakeFieldWalkmeshStore)
    dependency("memoria_baseline", ensure=lambda: {"release": "fixture", "source": "fixture", "problems": []})
    dependency("mod_compat", audit=lambda: {
        "pinnedMemoria": "v2025.07.04", "mods": [], "declaredConflicts": [],
        "overlaps": [], "unsupportedByPinnedMemoria": [], "folderNames": [],
        "priorities": [], "mergeScripts": False, "projectScanTruncated": False,
    })
    runtime = dependency("memoria_manager", status=lambda root: {"installed": False},
                         available=lambda: {"available": False})
    called = []
    for action in ("install", "recover", "open_settings"):
        def invoke(root, action=action):
            called.append(action)
            return {"action": action}
        setattr(runtime, action, invoke)
    feature_values = {"ImprovedInterface": False, "BetterEat": False}
    def feature_load():
        return {"features": dict(feature_values), "sha256": "feature-fixture", "path": str(tmp_path / "project/lexeditor-ff9.ini")}
    def feature_save(values, sha):
        if sha != "feature-fixture": raise RuntimeError("stale feature fixture")
        feature_values.update(values)
        return feature_load()
    deployed = {"value": False}
    def deployment_status():
        return {"deployed": deployed["value"], "runtimeReady": True, "runtimeCurrent": deployed["value"],
                "features": dict(feature_values), "gameModPath": str(tmp_path / "game/Lexeditor")}
    def deploy(): deployed["value"] = True; return deployment_status()
    def revert(): deployed["value"] = False; return deployment_status()
    dependency("features", load=feature_load, save=feature_save, status=deployment_status,
               deploy=deploy, revert=revert)
    font_file = tmp_path / "generated" / "ff9-menu.ttf"
    def ensure_font(name="ff9-menu.ttf"):
        if name != "ff9-menu.ttf" or not font_file.is_file():
            raise FileNotFoundError("The installed FF9 font bundle (Memoria p_fa.mpc) was not found")
        return font_file
    dependency("game_font", FACES={"ff9-menu.ttf": "Alexandria", "ff9-heading.ttf": "Garnet"},
               ensure_font=ensure_font, FONT_FILE=font_file)
    file = Path(__file__).parents[1] / "plugins/ff9/server.py"
    spec = importlib.util.spec_from_file_location(f"{package_name}.server", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield module, server.server_address[1], called
    server.shutdown(); server.server_close(); thread.join(5)


def request(service, path, body=b"{}", headers=None, method="POST"):
    _, port, _ = service
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse(); content = response.read()
        return response.status, json.loads(content)
    finally:
        connection.close()


@pytest.mark.parametrize("route,action", [("install", "install"), ("recover", "recover"), ("settings", "open_settings")])
def test_runtime_routes_reachable_exactly_once(service, route, action):
    status, payload = request(service, "/api/runtime/" + route)
    assert status == 200 and payload == {"action": action}
    assert service[2] == [action]


@pytest.mark.parametrize("headers,status", [
    ({"Origin": "https://example.invalid"}, 403), ({"Origin": "null"}, 403),
    ({"Host": "example.invalid"}, 403), ({"Content-Type": "text/plain"}, 415),
    ({"Content-Type": "application/x-www-form-urlencoded"}, 415),
    ({"Content-Length": "99999999"}, 413), ({"Transfer-Encoding": "chunked"}, 400),
])
def test_untrusted_or_invalid_requests_cannot_start_patcher(service, headers, status):
    # These headers must be rejected before reading a body. Sending body bytes
    # races the early close on Windows and can hide the response behind a reset.
    assert request(service, "/api/runtime/install", body=None, headers=headers)[0] == status
    assert not service[2]


def test_theme_font_is_served_privately_or_answers_404(service):
    module, port, _ = service
    status, payload = request(service, "/assets/ff9-menu.ttf", body=None, method="GET")
    assert status == 404 and "p_fa.mpc" in payload["error"]
    target = module.game_font.FONT_FILE
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x00\x01\x00\x00fixture")
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", "/assets/ff9-menu.ttf")
        response = connection.getresponse()
        assert response.status == 200 and response.read() == b"\x00\x01\x00\x00fixture"
    finally:
        connection.close()
    assert request(service, "/assets/other.ttf", body=None, method="GET")[0] == 404


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
    def fail(root): raise RuntimeError("Close FF9 first")
    monkeypatch.setattr(service[0].memoria_manager, "install", fail)
    assert request(service, "/api/runtime/install") == (409, {"error": "Close FF9 first"})


@pytest.mark.parametrize("method,path", [("GET", "/api/platform-config"), ("POST", "/api/platform-config/save")])
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
    source = (Path(__file__).parents[1] / "plugins/ff9/plugin.py").read_text(encoding="utf-8")
    specs = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "GameInstallSpec"]
    assert len(specs) == 1
    values = {entry.arg: entry.value for entry in specs[0].keywords}
    assert ast.literal_eval(values["launch_path"]) == "FF9_Launcher.exe"


def test_data_map_reports_external_launcher_not_an_embedded_ini_editor(service):
    launcher = service[0].paths.GAME_ROOT / "FF9_Launcher.exe"; launcher.write_bytes(b"fixture")
    _, data = request(service, "/api/datamap", method="GET")
    row = next(row for row in data["rows"] if row["filename"] == "FF9_Launcher.exe")
    assert row["status"] == "integrated" and row["target"] == "tweaks"
    assert "does not edit Memoria.ini" in row["notes"]
    assert not any(row["filename"] == "Memoria.ini" for row in data["rows"])


def test_feature_and_deployment_routes_are_guarded_and_stateful(service):
    status, before = request(service, "/api/features", method="GET")
    assert status == 200 and not before["features"]["BetterEat"]
    status, saved = request(service, "/api/features/save",
                            body=json.dumps({"sha256":"feature-fixture","features":{"BetterEat":True}}).encode())
    assert status == 200 and saved["features"]["BetterEat"]
    assert request(service, "/api/deployment/deploy")[1]["deployed"]
    assert not request(service, "/api/deployment/revert")[1]["deployed"]
    assert request(service, "/api/features/save", headers={"Origin":"https://example.invalid"})[0] == 403



def test_data_map_reports_editor_integration_even_before_baseline_arrives(service, monkeypatch):
    monkeypatch.setattr(service[0], "catalog", lambda: [{
        "available": False, "relativePath": "StreamingAssets/Data/Items/Items.csv",
        "controls": "Items", "label": "Items", "tab": "items", "key": "items",
    }])
    row = service[0].data_map()["rows"][0]
    assert row["status"] == "integrated" and row["coverage"] == "structured"
    assert row["openable"] is True and row["sourceAvailable"] is False


def test_data_map_keeps_battle_editor_integration_when_game_source_is_missing(service, monkeypatch):
    monkeypatch.setattr(service[0].BattleSceneStore, "status_rows", lambda self: [{
        "available": False, "relativePath": "StreamingAssets/p0data2.bin → BattleMap/BattleScene/*/dbfile0000.raw16",
        "controls": "Enemy fields", "notes": "Reads p0data2 and saves raw16 overlays.",
        "tab": "enemies", "key": "enemies",
    }])
    row = next(row for row in service[0].data_map()["rows"] if row.get("datasetKey") == "enemies")
    assert row["status"] == "integrated" and row["coverage"] == "structured"
    assert row["openable"] is True and row["sourceAvailable"] is False


def test_data_map_marks_walkmesh_floor_activity_partial_when_available(service, monkeypatch):
    monkeypatch.setattr(service[0].FIELD_WALKMESH, "status_rows", lambda: [{
        "available": True,
        "relativePath": "StreamingAssets/p0data1*.bin → StreamingAssets/Assets/Resources/FieldMaps/*/*.bgi.bytes",
        "controls": "Field walkmesh floor active/inactive state (BGI_FLOOR_ACTIVE)",
        "notes": "Edits only the documented active bit.",
        "tab": "world", "key": "field-walkmesh",
    }])
    row = next(row for row in service[0].data_map()["rows"] if row.get("datasetKey") == "field-walkmesh")
    assert row["status"] == "partial" and row["coverage"] == "structured"
    assert row["openable"] is True and row["sourceAvailable"] is True


def test_data_map_marks_walkmesh_triangle_activity_partial_when_available(service, monkeypatch):
    monkeypatch.setattr(service[0].FIELD_WALKMESH, "status_rows", lambda: [{
        "available": True,
        "relativePath": "StreamingAssets/p0data1*.bin → StreamingAssets/Assets/Resources/FieldMaps/*/*.bgi.bytes",
        "controls": "Per-field triangle active/inactive state (BGI_TRI_ACTIVE)",
        "notes": "Edits only the documented triangle-active bit.",
        "tab": "world", "key": "field-walkmesh-triangles",
    }])
    row = next(row for row in service[0].data_map()["rows"] if row.get("datasetKey") == "field-walkmesh-triangles")
    assert row["status"] == "partial" and row["coverage"] == "structured"
    assert row["openable"] is True and row["sourceAvailable"] is True


def test_data_map_keeps_each_known_p0data_gap_visible(service):
    rows = service[0].data_map()["rows"]
    gaps = {row["filename"]: row for row in rows if row["status"] == "not-integrated"}
    expected = {
        "StreamingAssets/p0data1*.bin (outside integrated BGI pathing flags)",
        "StreamingAssets/p0data2.bin (outside BattleScene raw16)",
        "StreamingAssets/p0data3.bin",
        "StreamingAssets/p0data4.bin",
        "StreamingAssets/p0data5.bin",
        "StreamingAssets/p0data7.bin",
        "StreamingAssets/p0data6*.bin and other unmatched p0data*.bin",
    }
    # Exact set, not a subset: a catch-all row previously concealed known format families (#74),
    # so any added, removed, or re-merged not-integrated row must fail here and be justified.
    assert set(gaps) == expected
    assert all(gaps[name]["coverage"] == "unavailable" and not gaps[name]["openable"]
               for name in expected)
    assert "mesh/rig" in gaps["StreamingAssets/p0data4.bin"]["notes"]
    assert "event-script" in gaps["StreamingAssets/p0data7.bin"]["notes"]


def test_dashboard_exposes_read_only_mod_compatibility_snapshot(service):
    status, dashboard = request(service, "/api/dashboard", method="GET")
    assert status == 200
    report = dashboard["modCompatibility"]
    assert report["pinnedMemoria"] == "v2025.07.04"
    assert report["mods"] == [] and report["overlaps"] == []


def test_mod_compat_endpoint_is_read_only(service):
    status, report = request(service, "/api/mod-compat", method="GET")
    assert status == 200
    assert report["pinnedMemoria"] == "v2025.07.04"
    before = list(service[2])
    assert request(service, "/api/mod-compat", method="POST")[0] == 404
    assert service[2] == before
