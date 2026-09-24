"""Stop a hosted service when its host closes the private input pipe or exits."""
from __future__ import annotations
import ctypes
import os
import signal
import sys
import threading

_JOB = None


def _own_windows_tree():
    # Assign this service before it imports plugin code or creates children.
    # A kill-on-close job also covers forced termination of the service itself.
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('processTime', ctypes.c_int64), ('jobTime', ctypes.c_int64),
                    ('flags', w.DWORD), ('minWorkingSet', ctypes.c_size_t),
                    ('maxWorkingSet', ctypes.c_size_t), ('activeLimit', w.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', ctypes.c_ulonglong * 6),
                    ('processMemory', ctypes.c_size_t), ('jobMemory', ctypes.c_size_t),
                    ('peakProcessMemory', ctypes.c_size_t), ('peakJobMemory', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    for name, args, result in (
        ('CreateJobObjectW', [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
        ('SetInformationJobObject', [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
        ('AssignProcessToJobObject', [w.HANDLE, w.HANDLE], w.BOOL),
        ('GetCurrentProcess', [], w.HANDLE), ('CloseHandle', [w.HANDLE], w.BOOL),
    ):
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error(); kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error(); kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    return job


def watch_host():
    global _JOB
    if os.name == 'nt':
        _JOB = _own_windows_tree()
    # pythonw has no sys.stdin object. Descriptor 0 still holds the explicit
    # inherited pipe supplied by LocalPluginSession.
    descriptor = 0 if sys.stdin is None else sys.stdin.fileno()

    def wait_for_close():
        try:
            while os.read(descriptor, 1):
                pass
        finally:
            if os.name != 'nt':
                os.killpg(os.getpgrp(), signal.SIGKILL)
            os._exit(0)

    threading.Thread(target=wait_for_close, name='plugin-host-lifetime', daemon=True).start()
