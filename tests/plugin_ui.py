"""A plugin's UI is its page and the modules that page loads.

Tests that ask what a plugin's interface says have to read both, or a page that
splits its script into modules looks to them like a page that lost the code.
The modules come back in the order the page loads them, so code that was
adjacent before the split is still adjacent here.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plugin_ui(name: str) -> str:
    """The page and its modules, as one string, in load order."""
    plugin = ROOT / "games" / name
    page = (plugin / "editor.html").read_text(encoding="utf-8")
    loaded = [plugin / module for module in re.findall(r'<script src="/([A-Za-z0-9_.-]+\.js)">', page)]
    rest = [path for path in sorted(plugin.glob("*.js")) + sorted(plugin.glob("*.css"))
            if path not in loaded]
    return "\n".join([page] + [path.read_text(encoding="utf-8") for path in loaded + rest])


def plugins_with_ui() -> list[str]:
    return sorted(path.parent.name for path in (ROOT / "games").glob("*/editor.html"))
