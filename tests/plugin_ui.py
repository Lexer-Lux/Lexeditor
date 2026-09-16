"""A plugin's UI is its page and the modules that page loads.

Tests that ask what a plugin's interface says have to read both, or a page that
splits its script into modules looks to them like a page that lost the code.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plugin_ui(name: str) -> str:
    """The page and its modules, as one string."""
    plugin = ROOT / "games" / name
    parts = [(plugin / "editor.html").read_text(encoding="utf-8")]
    parts += [path.read_text(encoding="utf-8")
              for path in sorted(plugin.glob("*.js")) + sorted(plugin.glob("*.css"))]
    return "\n".join(parts)


def plugins_with_ui() -> list[str]:
    return sorted(path.parent.name for path in (ROOT / "games").glob("*/editor.html"))
