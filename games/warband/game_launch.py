"""Selected-module WSE2 launch with owned-process and visible-window checks.

Do not invoke the auto-updating WSE2 launcher, guess stock Warband command-line
switches, or report a Popen handle as evidence of a game window.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import threading
import time


def launch_command(game_root: Path, project: Path) -> list[str]:
    game_root, project = game_root.resolve(), project.resolve()
    module = project if (project / "module.ini").is_file() else project / "Module"
    if not (module / "module.ini").is_file():
        raise RuntimeError("The selected project has no built module.ini. Build/install this module before Play.")
    modules = game_root / "Modules"
    candidates = sorted((p for p in modules.iterdir()
                         if p.is_dir() and (p / "module.ini").is_file()
                         and p.resolve() == module.resolve()), key=lambda p: p.name.casefold()) if modules.is_dir() else []
    if not candidates:
        raise RuntimeError("The selected module is not installed under this game's Modules folder. Play will not start a different mod.")
    if len(candidates) != 1:
        raise RuntimeError("Several installed module names point to this project. Keep one unambiguous installed module before Play.")
    executable = game_root / "mb_warband_wse2.exe"
    if not executable.is_file():
        raise RuntimeError("Direct selected-mod launching currently requires an installed mb_warband_wse2.exe. Stock Warband launching is not yet verified; no game was started.")
    # WSE2 author-documented syntax. argv keeps module names with spaces intact.
    return [str(executable), "--module", candidates[0].name, "--no-intro"]


class WindowsGameJob:
    """Own only the processes created by this launch, including child handoff."""
    def __init__(self, command: list[str], cwd: Path):
        if os.name != "nt":
            raise RuntimeError("Warband game launching requires the Windows desktop host.")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        k,u = self.kernel,self.user
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
        k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];k.AssignProcessToJobObject.restype=wintypes.BOOL
        k.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p];k.QueryInformationJobObject.restype=wintypes.BOOL
        k.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT];k.TerminateJobObject.restype=wintypes.BOOL
        k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
        self.callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        u.EnumWindows.argtypes=[self.callback_type,wintypes.LPARAM];u.EnumWindows.restype=wintypes.BOOL
        u.IsWindowVisible.argtypes=[wintypes.HWND];u.IsWindowVisible.restype=wintypes.BOOL
        u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];u.GetWindowThreadProcessId.restype=wintypes.DWORD
        u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];u.GetClientRect.restype=wintypes.BOOL
        u.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];u.GetClassNameW.restype=ctypes.c_int
        u.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT];u.GetWindow.restype=wintypes.HWND
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.process=None
        try:
            # This is a user-facing game, not a hidden helper process.
            self.process=subprocess.Popen(command,cwd=str(cwd))
            if not k.AssignProcessToJobObject(self.handle,wintypes.HANDLE(int(self.process._handle))):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate();self.process.wait(timeout=5)
            self.close()
            raise

    def pids(self) -> list[int]:
        if not self.handle:
            return []
        # JobObjectBasicProcessIdList is two DWORDs followed by ULONG_PTRs.
        for capacity in (64,1024,16384):
            buffer=ctypes.create_string_buffer(8+capacity*ctypes.sizeof(ctypes.c_size_t))
            success=self.kernel.QueryInformationJobObject(self.handle,3,buffer,len(buffer),None)
            if not success:
                if ctypes.get_last_error()==234:  # ERROR_MORE_DATA
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            assigned,count=(ctypes.c_uint32*2).from_buffer(buffer)
            if assigned>count:
                continue
            return list((ctypes.c_size_t*count).from_buffer(buffer,8))
        raise RuntimeError("The launched game exceeded the process tracking limit.")

    def window_pid(self) -> int | None:
        members=set(self.pids());found=[]
        @self.callback_type
        def callback(hwnd,_parameter):
            pid=wintypes.DWORD();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value not in members or not self.user.IsWindowVisible(hwnd) or self.user.GetWindow(hwnd,4):
                return True
            name=ctypes.create_unicode_buffer(256);self.user.GetClassNameW(hwnd,name,len(name))
            if name.value=="#32770":  # error/configuration dialog is not a game window
                return True
            rect=wintypes.RECT()
            if self.user.GetClientRect(hwnd,ctypes.byref(rect)) and rect.right>=320 and rect.bottom>=240:
                found.append(pid.value)
            return True
        self.user.EnumWindows(callback,0)
        return found[0] if found else None

    def terminate(self) -> None:
        if self.handle and not self.kernel.TerminateJobObject(self.handle,1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle);self.handle=None

    def __del__(self):
        # Closing the editor does not itself kill an already-running game.
        if getattr(self,"handle",None):
            self.close()


class WarbandGameController:
    def __init__(self, job_factory=WindowsGameJob, *, timeout=30.0, clock=time.monotonic, sleep=time.sleep):
        self._factory,self._timeout,self._clock,self._sleep=job_factory,timeout,clock,sleep
        self._job=None
        self._pid=None
        self._module=""
        self._lock=threading.RLock()

    def status(self) -> dict:
        with self._lock:
            pids=self._job.pids() if self._job else []
            if not pids and self._job:
                self._job.close();self._job=None;self._pid=None
            return {"running":bool(pids),"pid":self._pid if self._pid in pids else (pids[0] if pids else None),
                    "owned":bool(pids),"module":self._module,"processes":[{"pid":pid} for pid in pids]}

    def launch(self, game_root: Path, project: Path) -> dict:
        with self._lock:
            if self.status()["running"]:
                return {**self.status(),"alreadyRunning":True}
            command=launch_command(game_root,project)
            job=self._factory(command,game_root)
            deadline=self._clock()+self._timeout
            stable_pid=None;stable_since=0.0
            try:
                while self._clock()<deadline:
                    pids=job.pids()
                    if not pids:
                        raise RuntimeError("Warband exited before a game window appeared. Check the module and WSE2 crash log.")
                    pid=job.window_pid()
                    if pid != stable_pid:
                        stable_pid,stable_since=pid,self._clock()
                    if pid and self._clock()-stable_since>=.5:
                        self._job,self._pid,self._module=job,pid,command[2]
                        return {**self.status(),"windowObserved":True,"alreadyRunning":False}
                    self._sleep(.1)
                raise RuntimeError("Warband started but no game-sized window appeared. The owned launch was stopped; check its WSE2 log.")
            except Exception:
                try:
                    job.terminate()
                finally:
                    job.close()
                raise

    def stop(self) -> dict:
        with self._lock:
            if self._job is None:
                return {"running":False,"stopped":False}
            self._job.terminate()
            deadline=self._clock()+5
            while self._job.pids() and self._clock()<deadline:
                self._sleep(.1)
            if self._job.pids():
                raise RuntimeError("The owned Warband process has not stopped yet. Stop remains available.")
            self._job.close();self._job=None;self._pid=None
            return {"running":False,"stopped":True}
