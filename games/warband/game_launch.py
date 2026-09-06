"""Selected-module stock/WSE2 launch with owned-process and visible-window checks.

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


def installed_module(game_root: Path, project: Path) -> str:
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
    return candidates[0].name


def launch_command(game_root: Path, project: Path) -> list[str]:
    module = installed_module(game_root, project)
    executable = game_root.resolve() / "mb_warband_wse2.exe"
    if executable.is_file():
        return [str(executable), "--module", module, "--no-intro"]
    executable = game_root.resolve() / "mb_warband.exe"
    if not executable.is_file():
        raise RuntimeError("Neither mb_warband.exe nor mb_warband_wse2.exe exists in the selected game folder.")
    # Stock uses its real launcher, not unverified command-line flags.
    return [str(executable)]


class _OwnedProcess:
    """Small handle wrapper; the primary thread stays suspended until job assignment."""
    def __init__(self, handle, pid, api):
        self._handle, self.pid, self._api = handle, pid, api
        self.returncode = None

    def poll(self):
        if self.returncode is None:
            result = self._api.WaitForSingleObject(self._handle, 0)
            if result == 0:
                self.returncode = self._api.GetExitCodeProcess(self._handle)
            elif result != 258:
                raise OSError("Could not query the owned Warband process exit state.")
        return self.returncode

    def wait(self, timeout=None):
        milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
        result = self._api.WaitForSingleObject(self._handle, milliseconds)
        if result == 258:
            raise subprocess.TimeoutExpired("Warband", timeout)
        if result != 0:
            raise OSError("Could not wait for the owned Warband process to exit.")
        return self.poll()

    def terminate(self):
        if self.poll() is None:
            self._api.TerminateProcess(self._handle, 1)

    def close(self):
        if self._handle:
            self._api.CloseHandle(self._handle)
            self._handle = None


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
        k.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)];k.IsProcessInJob.restype=wintypes.BOOL
        self.callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        u.EnumWindows.argtypes=[self.callback_type,wintypes.LPARAM];u.EnumWindows.restype=wintypes.BOOL
        u.IsWindowVisible.argtypes=[wintypes.HWND];u.IsWindowVisible.restype=wintypes.BOOL
        u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];u.GetWindowThreadProcessId.restype=wintypes.DWORD
        u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];u.GetClientRect.restype=wintypes.BOOL
        u.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];u.GetClassNameW.restype=ctypes.c_int
        u.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT];u.GetWindow.restype=wintypes.HWND
        u.GetDlgItem.argtypes=[wintypes.HWND,ctypes.c_int];u.GetDlgItem.restype=wintypes.HWND
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.process=None
        self._tracked_processes: dict[int, _OwnedProcess] = {}
        self.executable = os.path.normcase(str(Path(command[0]).resolve()))
        k.ResumeThread.argtypes=[wintypes.HANDLE]; k.ResumeThread.restype=wintypes.DWORD
        k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
        k.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];k.QueryFullProcessImageNameW.restype=wintypes.BOOL
        thread = None
        try:
            # This is a user-facing game, not a hidden helper process.
            import _winapi
            process, thread, pid, _tid = _winapi.CreateProcess(
                command[0], subprocess.list2cmdline(command), None, None, False,
                4, None, str(cwd), subprocess.STARTUPINFO())  # CREATE_SUSPENDED
            self.process = _OwnedProcess(process, pid, _winapi)
            self._tracked_processes[pid] = self.process
            if not k.AssignProcessToJobObject(self.handle, wintypes.HANDLE(process)):
                raise ctypes.WinError(ctypes.get_last_error())
            if k.ResumeThread(wintypes.HANDLE(thread)) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate();self.process.wait(timeout=5)
            self.close()
            raise
        finally:
            if thread:
                k.CloseHandle(wintypes.HANDLE(thread))

    def _same_executable(self, pid: int) -> bool:
        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            size = wintypes.DWORD(32768)
            name = ctypes.create_unicode_buffer(size.value)
            return bool(self.kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size))) and os.path.normcase(str(Path(name.value).resolve())) == self.executable
        finally:
            self.kernel.CloseHandle(handle)

    def _job_pids(self) -> list[int]:
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

    def pids(self) -> list[int]:
        """Retain ownership until each observed process signals full termination.

        A job's active PID list can empty before the terminating process releases
        its working directory and file handles. Pin process handles while they
        are members, then use their wait state rather than membership as exit
        evidence. This also prevents a recycled PID from becoming our process.
        """
        if not self.handle:
            return []
        for pid in self._job_pids():
            if pid in self._tracked_processes:
                continue
            # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION.
            handle = self.kernel.OpenProcess(0x101000, False, pid)
            if not handle:
                error = ctypes.get_last_error()
                if error == 87:  # The process already exited (ERROR_INVALID_PARAMETER).
                    continue
                raise ctypes.WinError(error)
            try:
                member = wintypes.BOOL()
                if not self.kernel.IsProcessInJob(handle, self.handle, ctypes.byref(member)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if member.value:
                    self._tracked_processes[pid] = _OwnedProcess(handle, pid, self.process._api)
                    handle = None  # Ownership transferred to the tracked wrapper.
            finally:
                if handle:
                    self.kernel.CloseHandle(handle)
        active = []
        for pid, process in list(self._tracked_processes.items()):
            if process.poll() is None:
                active.append(pid)
            else:
                if process is not self.process:
                    process.close()
                del self._tracked_processes[pid]
        return active

    def window_pid(self) -> int | None:
        members={pid for pid in self.pids() if self._same_executable(pid)};found=[]
        @self.callback_type
        def callback(hwnd,_parameter):
            pid=wintypes.DWORD();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value not in members or not self.user.IsWindowVisible(hwnd) or self.user.GetWindow(hwnd,4):
                return True
            name=ctypes.create_unicode_buffer(256);self.user.GetClassNameW(hwnd,name,len(name))
            if name.value=="#32770" or self.user.GetDlgItem(hwnd,1029):  # error/configuration dialog is not a game window
                return True
            rect=wintypes.RECT()
            if self.user.GetClientRect(hwnd,ctypes.byref(rect)) and rect.right>=320 and rect.bottom>=240:
                found.append(pid.value)
            return True
        self.user.EnumWindows(callback,0)
        return found[0] if found else None

    def terminate(self) -> None:
        if self.handle:
            self.pids()  # Pin current children before asynchronous termination begins.
            if not self.kernel.TerminateJobObject(self.handle,1):
                raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle);self.handle=None
        for process in getattr(self, "_tracked_processes", {}).values():
            process.close()
        self._tracked_processes = {}
        if getattr(self, "process", None):
            self.process.close()

    def __del__(self):
        # Closing the editor does not itself kill an already-running game.
        if getattr(self,"handle",None):
            self.close()


class WarbandGameController:
    def __init__(self, job_factory=WindowsGameJob, *, timeout=120.0, clock=time.monotonic, sleep=time.sleep, native_factory=None):
        self._factory,self._timeout,self._clock,self._sleep=job_factory,timeout,clock,sleep
        from .native_launcher import NativeLauncher
        self._native_factory = native_factory or NativeLauncher
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
            module = installed_module(game_root, project)
            job=self._factory(command,game_root)
            deadline=self._clock()+self._timeout
            stable_pid=None;stable_since=0.0
            try:
                native = self._native_factory(job, module) if len(command) == 1 else None
                while self._clock()<deadline:
                    pids=job.pids()
                    if not pids:
                        raise RuntimeError("Warband exited before a game window appeared. Check the selected module, Steam session and rgl_log.txt.")
                    launched = native.advance() if native else True
                    pid=job.window_pid() if launched else None
                    if pid != stable_pid:
                        stable_pid,stable_since=pid,self._clock()
                    if pid and self._clock()-stable_since>=.5:
                        self._job,self._pid,self._module=job,pid,module
                        return {**self.status(),"windowObserved":True,"alreadyRunning":False}
                    self._sleep(.1)
                raise RuntimeError("Warband started but no game-sized window appeared. The owned launch was stopped; check its launcher, Steam session and rgl_log.txt.")
            except Exception:
                # Keep ownership if cleanup itself fails so Stop remains usable.
                self._job, self._module = job, module
                self.stop()
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
