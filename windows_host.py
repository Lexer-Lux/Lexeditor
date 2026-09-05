"""Windows-specific identity, icon, and frameless maximize helpers."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import queue
import threading
import time


APP_USER_MODEL_ID = "Lexer.Lexeditor"
WM_GETICON = 0x007F
ICON_SMALL = 0
ICON_BIG = 1
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D
WM_APPCOMMAND = 0x0319
XBUTTON1 = 1
XBUTTON2 = 2
APPCOMMAND_BROWSER_BACKWARD = 1
APPCOMMAND_BROWSER_FORWARD = 2


def xbutton_navigation_direction(message: int, wparam: int) -> int:
    """Map one Windows X-button-down message to browser-style direction."""
    if int(message) != WM_XBUTTONDOWN:
        return 0
    button = (int(wparam) >> 16) & 0xFFFF
    if button == XBUTTON1:
        return -1
    if button == XBUTTON2:
        return 1
    return 0


def xbutton_navigation_event(message: int, wparam: int) -> tuple[bool, int]:
    """Return whether to consume an X-button message and its one-shot direction."""
    if int(message) not in {WM_XBUTTONDOWN, WM_XBUTTONUP, WM_XBUTTONDBLCLK}:
        return False, 0
    button = (int(wparam) >> 16) & 0xFFFF
    if button not in {XBUTTON1, XBUTTON2}:
        return False, 0
    return True, xbutton_navigation_direction(message, wparam)


def appcommand_navigation_event(message: int, lparam: int) -> tuple[bool, int]:
    """Consume browser Back/Forward commands emitted by some X-button drivers."""
    if int(message) != WM_APPCOMMAND:
        return False, 0
    command = (int(lparam) >> 16) & 0x7FF
    if command == APPCOMMAND_BROWSER_BACKWARD:
        return True, -1
    if command == APPCOMMAND_BROWSER_FORWARD:
        return True, 1
    return False, 0


class MouseNavigationController:
    """Keep the WinForms message filter and ordered JavaScript worker alive."""

    def __init__(self, application, message_filter, commands: queue.Queue):
        self._application = application
        self._message_filter = message_filter
        self._commands = commands
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._application.RemoveMessageFilter(self._message_filter)
        self._commands.put(None)


# Windows 11 rounds the corners of every top-level window and draws a thin
# border around it, frameless or not. On a frameless app that border is a
# hairline of whatever sits behind the window, and the rounded corners cut
# into the shell chrome. Both are DWM attributes and both can be switched off.
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_DONOTROUND = 1
DWMWA_COLOR_NONE = 0xFFFFFFFE


def square_window_edges(window) -> bool:
    """Remove the rounded corners and the 1px border from a frameless window."""
    if os.name != "nt":
        return False
    try:
        handle = wintypes.HWND(int(_native_form(window).Handle.ToInt64()))
    except Exception:
        return False
    dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
    dwm.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.restype = ctypes.c_long
    applied = True
    for attribute, value in (
        (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND),
        (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE),
    ):
        payload = ctypes.c_uint32(value)
        result = dwm(handle, attribute, ctypes.byref(payload),
                     ctypes.sizeof(payload))
        # Older Windows builds do not know these attributes and return a
        # failure code; the window simply keeps its default edges.
        applied = applied and result == 0
    return applied

def install_mouse_navigation(window) -> MouseNavigationController:
    """Consume mouse X buttons and send ordered Back/Forward commands to the shell."""
    if os.name != "nt":
        raise RuntimeError("Native mouse navigation is available only on Windows")
    from System.Windows.Forms import Application, IMessageFilter

    native = _native_form(window)
    installed: dict[str, MouseNavigationController] = {}

    def apply() -> None:
        root_handle = int(native.Handle.ToInt64())
        commands: queue.Queue[int | None] = queue.Queue()

        def deliver() -> None:
            while True:
                direction = commands.get()
                if direction is None:
                    return
                try:
                    window.run_js(f"window.__lexeditorNavigateHistory?.({direction});")
                except Exception:
                    pass

        worker = threading.Thread(target=deliver, daemon=True)
        worker.start()

        class LexeditorMouseNavigationFilter(IMessageFilter):
            __namespace__ = "Lexer.Lexeditor.Native"

            def PreFilterMessage(self, message):  # noqa: N802 - .NET interface
                consume, direction = xbutton_navigation_event(
                    int(message.Msg), int(message.WParam.ToInt64()),
                )
                if not consume:
                    consume, direction = appcommand_navigation_event(
                        int(message.Msg), int(message.LParam.ToInt64()),
                    )
                if not consume:
                    return False, message
                target = int(message.HWnd.ToInt64())
                if (target != root_handle and
                        not ctypes.windll.user32.IsChild(root_handle, target) and
                        not bool(native.ContainsFocus)):
                    return False, message
                if direction:
                    commands.put(direction)
                return True, message

        message_filter = LexeditorMouseNavigationFilter()
        Application.AddMessageFilter(message_filter)
        installed["controller"] = MouseNavigationController(
            Application, message_filter, commands,
        )

    _invoke(native, apply)
    return installed["controller"]


def configure_process_identity() -> str:
    """Give the Python-hosted window a stable Lexeditor taskbar identity."""
    if os.name != "nt":
        return ""
    setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = [ctypes.c_wchar_p]
    setter.restype = ctypes.c_long
    result = int(setter(APP_USER_MODEL_ID))
    if result != 0:
        raise OSError(f"SetCurrentProcessExplicitAppUserModelID failed: 0x{result & 0xffffffff:08X}")
    return APP_USER_MODEL_ID


def current_process_identity() -> str:
    """Read back the explicit identity for acceptance checks."""
    if os.name != "nt":
        return ""
    getter = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
    getter.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    getter.restype = ctypes.c_long
    pointer = ctypes.c_void_p()
    result = int(getter(ctypes.byref(pointer)))
    if result != 0 or not pointer.value:
        return ""
    try:
        return ctypes.wstring_at(pointer.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)


def _native_form(window):
    native = getattr(window, "native", None)
    if native is None:
        raise RuntimeError("Lexeditor's native window is not ready")
    return native


def _invoke(native, callback) -> None:
    from System import Action

    if native.InvokeRequired:
        native.Invoke(Action(callback))
    else:
        callback()


def configure_window_icon(window, icon_path: Path) -> dict:
    """Set the real WinForms icon used by Alt+Tab and the taskbar."""
    if os.name != "nt":
        return {"largeIcon": 0, "smallIcon": 0}
    native = _native_form(window)
    if not icon_path.is_file():
        raise FileNotFoundError(icon_path)

    def apply() -> None:
        from System.Drawing import Icon

        native.Icon = Icon(str(icon_path))

    _invoke(native, apply)
    handle = int(native.Handle.ToInt64())
    user32 = ctypes.windll.user32
    return {
        "largeIcon": int(user32.SendMessageW(handle, WM_GETICON, ICON_BIG, 0)),
        "smallIcon": int(user32.SendMessageW(handle, WM_GETICON, ICON_SMALL, 0)),
    }


def maximize_to_work_area(window) -> dict:
    """Fill the monitor work area and preserve the prior window rectangle."""
    if os.name != "nt":
        window.maximize()
        return {}
    native = _native_form(window)
    result: dict[str, list[int]] = {}

    def apply() -> None:
        from System.Windows.Forms import FormWindowState, Screen

        work = Screen.FromHandle(native.Handle).WorkingArea
        restored = native.RestoreBounds if native.WindowState != FormWindowState.Normal else native.Bounds
        native.WindowState = FormWindowState.Normal
        native.Bounds = work
        result.update({
            "restoreBounds": [
                int(restored.Left), int(restored.Top),
                int(restored.Width), int(restored.Height),
            ],
            "workArea": [
                int(work.Left), int(work.Top), int(work.Width), int(work.Height),
            ],
        })

    _invoke(native, apply)
    return result


def restore_from_work_area(window, restore_bounds: list[int] | None) -> None:
    """Restore a saved rectangle and keep it inside the nearest work area."""
    if os.name != "nt":
        window.restore()
        return
    if not restore_bounds or len(restore_bounds) != 4:
        raise RuntimeError("Lexeditor has no saved restore rectangle")
    native = _native_form(window)

    def apply() -> None:
        from System.Drawing import Rectangle
        from System.Windows.Forms import FormWindowState, Screen

        requested = Rectangle(*[int(value) for value in restore_bounds])
        work = Screen.FromRectangle(requested).WorkingArea
        width = min(max(900, int(requested.Width)), int(work.Width))
        height = min(max(620, int(requested.Height)), int(work.Height))
        left = max(int(work.Left), min(int(requested.Left), int(work.Right) - width))
        top = max(int(work.Top), min(int(requested.Top), int(work.Bottom) - height))
        native.WindowState = FormWindowState.Normal
        native.Bounds = Rectangle(left, top, width, height)

    _invoke(native, apply)


def _resized_rectangle(bounds: list[int], edge: str, dx: int, dy: int,
                       minimum: list[int]) -> list[int]:
    """Return one clamped rectangle for a frameless edge drag."""
    left, top, width, height = [int(value) for value in bounds]
    min_width, min_height = [max(1, int(value)) for value in minimum]
    right = left + width
    bottom = top + height
    if "left" in edge:
        left = min(left + int(dx), right - min_width)
    if "right" in edge:
        right = max(right + int(dx), left + min_width)
    if "top" in edge:
        top = min(top + int(dy), bottom - min_height)
    if "bottom" in edge:
        bottom = max(bottom + int(dy), top + min_height)
    return [left, top, right - left, bottom - top]


def resize_window_by(window, edge: str, dx: int, dy: int) -> list[int]:
    """Resize a frameless native window by one deterministic cursor delta."""
    allowed = {
        "top", "right", "bottom", "left",
        "top-left", "top-right", "bottom-right", "bottom-left",
    }
    if edge not in allowed:
        raise ValueError(f"Unknown window resize edge: {edge}")
    native = _native_form(window)
    result: dict[str, list[int]] = {}

    def apply() -> None:
        from System.Drawing import Rectangle
        from System.Windows.Forms import FormWindowState

        native.WindowState = FormWindowState.Normal
        bounds = [native.Left, native.Top, native.Width, native.Height]
        minimum = [native.MinimumSize.Width, native.MinimumSize.Height]
        resized = _resized_rectangle(bounds, edge, dx, dy, minimum)
        native.Bounds = Rectangle(*resized)
        result["bounds"] = resized

    _invoke(native, apply)
    return result["bounds"]


def begin_window_resize(window, edge: str) -> dict:
    """Track the real Windows cursor and resize a frameless window until release."""
    allowed = {
        "top", "right", "bottom", "left",
        "top-left", "top-right", "bottom-right", "bottom-left",
    }
    if edge not in allowed:
        raise ValueError(f"Unknown window resize edge: {edge}")
    native = _native_form(window)
    initial: dict[str, list[int]] = {}

    def capture() -> None:
        from System.Windows.Forms import FormWindowState

        native.WindowState = FormWindowState.Normal
        initial["bounds"] = [native.Left, native.Top, native.Width, native.Height]
        initial["minimum"] = [native.MinimumSize.Width, native.MinimumSize.Height]

    _invoke(native, capture)
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    start = [int(point.x), int(point.y)]

    def track() -> None:
        from System.Drawing import Rectangle

        while ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
            current = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(current))
            resized = _resized_rectangle(
                initial["bounds"], edge,
                int(current.x) - start[0], int(current.y) - start[1],
                initial["minimum"],
            )
            _invoke(native, lambda values=resized: setattr(native, "Bounds", Rectangle(*values)))
            time.sleep(0.016)

    threading.Thread(target=track, daemon=True).start()
    return {"started": True, "edge": edge}


def native_window_metrics(window) -> dict:
    """Read the native bounds, work area, and attached icon handles."""
    if os.name != "nt":
        return {}
    native = _native_form(window)
    result: dict = {}

    def read() -> None:
        from System.Windows.Forms import Screen

        bounds = native.Bounds
        work = Screen.FromHandle(native.Handle).WorkingArea
        handle = int(native.Handle.ToInt64())
        user32 = ctypes.windll.user32
        result.update({
            "bounds": [int(bounds.Left), int(bounds.Top), int(bounds.Width), int(bounds.Height)],
            "workArea": [int(work.Left), int(work.Top), int(work.Width), int(work.Height)],
            "largeIcon": int(user32.SendMessageW(handle, WM_GETICON, ICON_BIG, 0)),
            "smallIcon": int(user32.SendMessageW(handle, WM_GETICON, ICON_SMALL, 0)),
            "windowState": str(native.WindowState),
        })

    _invoke(native, read)
    result["appUserModelId"] = current_process_identity()
    return result
