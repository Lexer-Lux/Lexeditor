"""One Engine Config panel serves both Unreal games (issue 478)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "ui" / "unreal-config.js"
PAGES = {
    "ff7r": (ROOT / "plugins/ff7r/editor.html",
             ROOT / "plugins/ff7r/editor.js",
             ROOT / "plugins/ff7r/server.py",
             ROOT / "plugins/ff7r/unreal_config.py"),
    "ff7r2": (ROOT / "plugins/ff7r2/editor.html",
              ROOT / "plugins/ff7r2/editor.js",
              ROOT / "plugins/ff7r2/server.py",
              ROOT / "plugins/ff7r2/unreal_config.py"),
}
ROUTES = ("/api/unreal-config", "/api/unreal-config/apply",
          "/api/unreal-config/default", "/api/unreal-config/reset",
          "/api/unreal-config/refresh")


def test_shared_panel_defines_one_mountable_editor():
    text = SHARED.read_text(encoding="utf-8")
    assert "window.LexeditorUnrealConfig={createPanel}" in text
    assert "createPanel(options)" in text
    assert "ENGINE CONFIG" in text
    assert "Use game default" in text
    assert "Reset all" in text
    assert "INI UNLOCKER" in text
    assert "Managed by another Lexeditor group; change it there." in text


def test_shared_panel_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for JavaScript syntax checks.")
    result = subprocess.run([node, "--check", str(SHARED)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("game", sorted(PAGES))
def test_each_page_loads_and_mounts_the_shared_panel(game):
    page, editor, server, copy = PAGES[game]
    html = page.read_text(encoding="utf-8")
    assert html.count("/shared/unreal-config.js") == 1
    assert (html.index("/shared/unreal-config.js")
            > html.index("/shared/framework.js"))
    script = editor.read_text(encoding="utf-8")
    assert "LexeditorUnrealConfig.createPanel" in script
    assert 'route:"/api/unreal-config"' in script
    assert "ENGINE CONFIG" not in script, \
        "the panel title must live in the shared module, not a page copy"
    body = server.read_text(encoding="utf-8")
    assert "import unreal_config" in body
    for route in ROUTES:
        assert route in body, route
    assert copy.exists() is False, \
        "the shared editor must not be copied per game"


def test_rebirth_keeps_its_engine_subtab():
    script = (ROOT / "plugins/ff7r2/editor.js").read_text(encoding="utf-8")
    assert '{id:"engine",label:"Engine Config"' in script


def test_remake_lists_engine_config_on_the_tweaks_page():
    script = (ROOT / "plugins/ff7r/editor.js").read_text(encoding="utf-8")
    assert "enginePanel.element()" in script
    assert "enginePanel.ensure()" in script
    server = (ROOT / "plugins/ff7r/server.py").read_text(encoding="utf-8")
    assert '"unreal-config"' in server
    assert '"target": "tweaks"' in server
