from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _input_handler(path: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    start_marker = "  function inputChanged(target) {"
    end_marker = "\n  async function save() {"
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_x2_numeric_editors_preserve_active_input_during_typing():
    """Regression: input handlers must not rebuild the field grid per keystroke."""
    for path in ("ui/ffx-x2-accessories.js", "ui/ffx-x2-jobs.js"):
        handler = _input_handler(path)
        assert "renderSummary(row);" in handler, path
        assert "render();" not in handler, f"{path} would replace the focused input on every keystroke"
