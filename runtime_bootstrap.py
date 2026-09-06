"""Writable application paths and explicit frozen child-service entry points."""
from __future__ import annotations
import os
from pathlib import Path
import runpy
import subprocess
import sys

SERVICE_MODULES = frozenset({
    'games.blank.server', 'games.ff7.server', 'games.ff8.server',
    'games.ff9.server', 'games.rdr.server', 'games.rdr2.server', 'games.warband.server',
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
                          ('LEXEDITOR_RDR2_PROJECT', 'rdr2'), ('LEXEDITOR_MOD_PROJECT', 'warband')]:
            os.environ.setdefault(key, str(root / 'projects' / game))


def service_command(module: str) -> list[str]:
    if module not in SERVICE_MODULES:
        raise ValueError(f'Unsupported plugin service: {module}')
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--plugin-service', module]
    return [sys.executable, '-m', module]


def dispatch_service(argv: list[str]) -> bool:
    if not argv or argv[0] != '--plugin-service':
        return False
    if len(argv) != 2 or argv[1] not in SERVICE_MODULES:
        raise ValueError('A bundled plugin service must name an allowed module')
    module = argv[1]
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
