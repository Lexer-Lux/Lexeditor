"""A plugin page's source as verifiers should read it: the page and its modules.

Pages load their code from modules beside them, so a check that reads only
editor.html no longer sees most of the plugin.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from plugin_ui import plugin_ui  # noqa: E402


def plugin_source(name: str) -> str:
    """plugins/<name>/editor.html followed by every module and stylesheet beside it."""
    return plugin_ui(name)
