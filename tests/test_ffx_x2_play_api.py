from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

import pytest

from games.ffx_x2 import server


def _installation(tmp_path: Path) -> Path:
    root = tmp_path / "FINAL FANTASY FFX&FFX-2 HD Remaster"
    for relative in (
        "FFX.exe", "FFX-2.exe",
        "fahrenheit/bin/fhstage0.exe", "fahrenheit/bin/fhstage1.dll",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")
    return root


@contextmanager
def _running_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = _installation(tmp_path)
    project = tmp_path / "project"
    monkeypatch.setattr(server.paths, "GAME_ROOT", root)
    monkeypatch.setattr(server.paths, "PROJECT_ROOT", project)
    monkeypatch.setattr(server.paths, "ARCHIVES", {
        "x": root / "data" / "FFX_Data.vbf",
        "x2": root / "data" / "FFX2_Data.vbf",
    })
    monkeypatch.setattr(server.paths, "META_ARCHIVE", root / "data" / "metamenu.vbf")
    httpd = server.create_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield root, f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _request_json(base_url: str, path: str, payload=None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=data,
        method="GET" if data is None else "POST",
        headers={} if data is None else {"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_launch_status_is_exposed_by_dashboard_and_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    with _running_server(monkeypatch, tmp_path) as (_root, base_url):
        status_code, state = _request_json(base_url, "/api/launch")
        assert status_code == 200
        assert state["stage0Ready"] is True
        assert state["stage1Ready"] is True
        assert state["games"]["x"]["ready"] is True
        assert state["games"]["x2"]["ready"] is True
        assert state["platformSupported"] is (server.os.name == "nt")
        assert state["games"]["x"]["launchReady"] is (server.os.name == "nt")

        dashboard = server.dashboard()
        assert dashboard["launch"]["stage0"] == state["stage0"]
        assert dashboard["launch"]["games"]["x2"]["executable"].endswith("FFX-2.exe")


def test_play_route_calls_only_the_fixed_launch_boundary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls: list[tuple[Path, str]] = []

    def fake_launch(root: Path, game: str) -> dict:
        calls.append((Path(root), game))
        return {"launched": True, "game": game, "pid": 12345}

    monkeypatch.setattr(server.fahrenheit_launch, "launch", fake_launch)
    with _running_server(monkeypatch, tmp_path) as (root, base_url):
        for game in ("x", "x2"):
            status_code, result = _request_json(base_url, "/api/play", {"game": game})
            assert status_code == 200
            assert result == {"launched": True, "game": game, "pid": 12345}

    assert calls == [(root, "x"), (root, "x2")]


@pytest.mark.parametrize("payload", [
    {},
    {"game": "X"},
    {"game": "launcher"},
    {"game": "x", "args": ["--anything"]},
    {"game": "x2", "path": "FFX-2.exe"},
    {"path": "FFX.exe"},
    {"game": 1},
    ["x"],
])
def test_play_route_rejects_every_shape_except_exact_collection_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload,
):
    calls: list[str] = []

    def fake_launch(_root: Path, game: str) -> dict:
        calls.append(game)
        return {"launched": True, "game": game}

    monkeypatch.setattr(server.fahrenheit_launch, "launch", fake_launch)
    with _running_server(monkeypatch, tmp_path) as (_root, base_url):
        status_code, result = _request_json(base_url, "/api/play", payload)

    assert status_code == 400
    assert "error" in result
    assert calls == []
