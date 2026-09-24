"""Contracts for the movable and resizable shared frameless window."""

from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop_host import HostApi, load_window_geometry, save_window_geometry  # noqa: E402
from windows_host import _resized_rectangle  # noqa: E402


framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
desktop = (ROOT / "desktop_host.py").read_text(encoding="utf-8")

assert 'region.classList.toggle("pywebview-drag-region", !maximized)' in framework
assert 'region.classList.add("lex-window-drag-region", "pywebview-drag-region")' not in framework
assert 'region.addEventListener("mousedown", armWindowMove)' not in framework
assert 'callWindow("window_begin_resize", edge)' in framework
assert "return begin_window_resize(self._bound_window(), edge)" in desktop
assert "nativeResizeEdges" in desktop
assert "api.apply_window_geometry(geometry)" in desktop
assert "self.remember_window_geometry()" in desktop

with tempfile.TemporaryDirectory(prefix="lexeditor-window-state-", ignore_cleanup_errors=True) as directory:
    state_path = Path(directory) / "window-state.json"
    expected_state = {"bounds": [135, 246, 1280, 760], "maximized": True}
    save_window_geometry(expected_state, state_path)
    assert load_window_geometry(state_path) == expected_state
    state_path.write_text('{"bounds":[0,0,10,10],"maximized":true}', encoding="utf-8")
    assert load_window_geometry(state_path)["maximized"] is False

api = HostApi.__new__(HostApi)
api._lock = threading.RLock()
api._maximized = True
api._begin_nonclient_drag = lambda _hit_test: (_ for _ in ()).throw(
    AssertionError("A maximized window attempted to move")
)
api._bound_window = lambda: (_ for _ in ()).throw(
    AssertionError("A maximized window attempted to resize")
)
assert api.window_begin_move() == {"started": False, "reason": "maximized"}
assert api.window_begin_resize("right") == {"started": False, "reason": "maximized"}
assert api.window_resize_by("right", 12, 0) == {"started": False, "reason": "maximized"}

api._maximized = False
api._begin_nonclient_drag = lambda hit_test: {"started": True, "hitTest": hit_test}
assert api.window_begin_move() == {"started": True, "hitTest": 2}
with patch("desktop_host.begin_window_resize", return_value={"started": True, "edge": "right"}):
    api._bound_window = lambda: object()
    assert api.window_begin_resize("right") == {"started": True, "edge": "right"}

bounds = [100, 100, 900, 620]
minimum = [900, 620]
expected = {
    "top": [100, 88, 900, 632],
    "right": [100, 100, 912, 620],
    "bottom": [100, 100, 900, 632],
    "left": [88, 100, 912, 620],
    "top-left": [88, 88, 912, 632],
    "top-right": [100, 88, 912, 632],
    "bottom-right": [100, 100, 912, 632],
    "bottom-left": [88, 100, 912, 632],
}
for edge, rectangle in expected.items():
    dx = -12 if "left" in edge else 12
    dy = -12 if "top" in edge else 12
    assert _resized_rectangle(bounds, edge, dx, dy, minimum) == rectangle, edge

print("Frameless move and resize issue 49 contracts passed")
