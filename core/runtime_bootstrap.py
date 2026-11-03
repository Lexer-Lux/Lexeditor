"""Writable application paths and explicit frozen child-service entry points."""
from __future__ import annotations
import os
from pathlib import Path
import runpy
import subprocess
import sys

SERVICE_MODULES = frozenset({
    'plugins.kf1.server',
    'plugins.ds1.server',
    'plugins.ds1.script_worker',

    'plugins.bannerlord.server', 'plugins.blank.server', 'plugins.ff7.server', 'plugins.ff7r.server', 'plugins.ff7r.themed_server',
    'plugins.ds3.server', 'plugins.ff8.server', 'plugins.ff9.server', 'plugins.ffx_x2.server', 'plugins.palworld.full_server', 'plugins.project_zomboid.server',
    'plugins.rdr.server', 'plugins.rdr2.server', 'plugins.terraria.server',
    'plugins.stardew_valley.server', 'plugins.warband.server', 'plugins.ff7r2.server', 'plugins.factorio.server', 'plugins.chrono_trigger.server',





})


def user_data_dir() -> Path:
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        value = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        base = value if value.is_absolute() else Path.home() / '.local/share'
    return base / 'Lexeditor'


def bootstrap_environment() -> None:
    """Set process-local defaults before plugins import their path descriptors.

    Explicit user overrides win. Installed resources never become the writable
    settings/cache/project directory. LOCALAPPDATA is a compatibility shim for
    existing plugins, not a change to the user's global environment.
    """
    root = user_data_dir()
    os.environ.setdefault('LOCALAPPDATA', str(root.parent))
    if os.name != 'nt':
        for key, game in [('LEXEDITOR_FF8_PROJECT', 'ff8'), ('LEXEDITOR_RDR_PROJECT', 'rdr'),
                          ('LEXEDITOR_RDR2_PROJECT', 'rdr2'), ('LEXEDITOR_STARDEW_PROJECT', 'stardew-valley'),
                          ('LEXEDITOR_MOD_PROJECT', 'warband'), ('LEXEDITOR_PROJECT_ZOMBOID_PROJECT', 'project-zomboid')]:
            os.environ.setdefault(key, str(root / 'projects' / game))


def service_command(module: str, *, owned: bool = False) -> list[str]:
    if module not in SERVICE_MODULES:
        raise ValueError(f'Unsupported plugin service: {module}')
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--plugin-service', module]
    if owned:
        return [sys.executable, '-m', 'core.runtime_bootstrap', '--plugin-service', module]
    return [sys.executable, '-m', module]


def dispatch_service(argv: list[str]) -> bool:
    if not argv or argv[0] != '--plugin-service':
        return False
    if len(argv) != 2 or argv[1] not in SERVICE_MODULES:
        raise ValueError('A bundled plugin service must name an allowed module')
    module = argv[1]
    if os.environ.get('LEXEDITOR_SERVICE_PIPE') == '1':
        from core.service_lifetime import watch_host
        watch_host()
    sys.argv = [module]
    runpy.run_module(module, run_name='__main__')
    return True


def open_path(path: Path) -> None:
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    if os.name == 'nt':
        os.startfile(str(target))
    else:
        # Never pass a file path through a shell.
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(target)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_text_file(path: Path) -> None:
    """Use a text-editor association, never the executable .py association."""
    target = Path(path).resolve(strict=True)
    if not target.is_file():
        raise ValueError('Choose a text file')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        query = ctypes.WinDLL('shlwapi').AssocQueryStringW
        query.argtypes = [wintypes.DWORD, ctypes.c_int, wintypes.LPCWSTR,
                          wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        query.restype = ctypes.c_long
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        # ASSOCSTR_EXECUTABLE (2), using the user's plain-text association.
        result = query(0, 2, '.txt', 'open', buffer, ctypes.byref(size))
        editor = buffer.value if result == 0 and buffer.value else 'notepad.exe'
        subprocess.Popen([editor, str(target)])
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-t', str(target)])
    else:
        import shutil
        launcher = shutil.which('sensible-editor')
        if not launcher:
            raise OSError('No default text editor was found. Open disable_networking.py in your text editor.')
        subprocess.Popen([launcher, str(target)])


if __name__ == '__main__':
    if not dispatch_service(sys.argv[1:]):
        raise SystemExit('An allowed plugin service is required.')
