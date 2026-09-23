"""Compatibility launcher for the shared Lexeditor WebView2 host.

The Warband plugin no longer owns a separate Tkinter application. Existing
imports of this module open the same shared desktop host as Lexeditor.cmd.
"""

from __future__ import annotations


def launch() -> int:
    from .plugin import launch as launch_shared_host
    return launch_shared_host()


if __name__ == "__main__":
    raise SystemExit(launch())
