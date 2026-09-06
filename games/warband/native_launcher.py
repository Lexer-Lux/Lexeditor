"""Drive only the stock launcher owned by this Play request.

Stock Warband has no assumed --module switch. Select an exact module from its
real ComboBox, notify the dialog, then invoke control 1029 (1040 is a decoy).
The control ID is corroborated by cuellius/warband-launcher-kit LoaderBase.cs.
No registry setting, game file, unrelated window or global keyboard is changed.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class NativeLauncher:
    def __init__(self, job, module: str):
        self.job, self.module = job, module
        self.started = False
        self.user = job.user
        self.callback_type = job.callback_type
        u = self.user
        signatures = {
            "GetDlgItem": ([wintypes.HWND, ctypes.c_int], wintypes.HWND),
            "GetDlgCtrlID": ([wintypes.HWND], ctypes.c_int),
            "GetParent": ([wintypes.HWND], wintypes.HWND),
            "IsWindowEnabled": ([wintypes.HWND], wintypes.BOOL),
            "EnumChildWindows": ([wintypes.HWND, self.callback_type, wintypes.LPARAM], wintypes.BOOL),
            "SendMessageTimeoutW": ([wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                     wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                     ctypes.POINTER(ctypes.c_size_t)], ctypes.c_ssize_t),
            "PostMessageW": ([wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                              wintypes.LPARAM], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(u, name)
            function.argtypes, function.restype = args, result

    def _send(self, hwnd, message: int, wparam: int = 0, lparam: int = 0) -> int:
        result = ctypes.c_size_t()
        # SMTO_BLOCK | SMTO_ABORTIFHUNG. Never hang the editor on a hung launcher.
        if not self.user.SendMessageTimeoutW(hwnd, message, wparam, lparam, 3, 500,
                                            ctypes.byref(result)):
            raise RuntimeError("Warband's launcher is not responding to module selection.")
        return ctypes.c_ssize_t(result.value).value

    def _class(self, hwnd) -> str:
        name = ctypes.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd, name, len(name))
        return name.value

    def _owned(self, hwnd) -> bool:
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value in self.job.pids()

    def advance(self) -> bool:
        """Return whether Play was sent; remain pending while the dialog loads."""
        if self.started:
            return True
        dialogs = []
        @self.callback_type
        def collect(hwnd, _parameter):
            if self._owned(hwnd) and self.user.IsWindowVisible(hwnd):
                play = self.user.GetDlgItem(hwnd, 1029)
                if play and self._class(play).casefold() == "button":
                    dialogs.append((hwnd, play))
            return True
        self.user.EnumWindows(collect, 0)
        for dialog, play in dialogs:
            if not self.user.IsWindowEnabled(play):
                continue
            matches = []
            @self.callback_type
            def inspect(hwnd, _parameter):
                if self._class(hwnd).casefold() == "combobox":
                    matches.append(hwnd)
                return True
            self.user.EnumChildWindows(dialog, inspect, 0)
            found = []
            for combo in matches:
                count = self._send(combo, 0x146)  # CB_GETCOUNT
                if not 0 <= count <= 10000:
                    continue
                for index in range(count):
                    length = self._send(combo, 0x149, index)  # CB_GETLBTEXTLEN
                    if not 0 <= length <= 32767:
                        continue
                    text = ctypes.create_unicode_buffer(length + 1)
                    self._send(combo, 0x148, index, ctypes.addressof(text))
                    if text.value.casefold() == self.module.casefold():
                        found.append((combo, index))
            if not found:
                continue  # The launcher may not have populated its module list yet.
            if len(found) != 1:
                raise RuntimeError("The stock launcher lists the selected module more than once; no game was started.")
            combo, index = found[0]
            if self._send(combo, 0x14E, index) != index:  # CB_SETCURSEL
                raise RuntimeError("Warband's launcher refused the selected module.")
            control = self.user.GetDlgCtrlID(combo)
            self._send(self.user.GetParent(combo), 0x111, (1 << 16) | (control & 0xFFFF), int(combo))
            if self._send(combo, 0x147) != index:  # CB_GETCURSEL after CBN_SELCHANGE
                raise RuntimeError("Warband's launcher changed the module selection; launch cancelled.")
            if not self._owned(dialog):
                raise RuntimeError("Warband's launcher closed before Play.")
            # Mouse messages also work with Warband's owner-drawn real Play
            # button. Post, rather than Send: its handler may enter game loading.
            for message, key in ((0x201, 1), (0x202, 0)):
                if not self.user.PostMessageW(play, message, key, (1 << 16) | 1):
                    raise RuntimeError("Could not activate Warband's Play button.")
            self.started = True
            return True
        return False
