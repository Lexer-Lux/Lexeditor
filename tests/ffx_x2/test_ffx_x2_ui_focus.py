from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_numeric_input_handlers_preserve_focus_during_typing():
    """Record-detail inputs update local state without rebuilding the page per keystroke."""
    source = (ROOT / "plugins/ffx_x2/editor.js").read_text(encoding="utf-8")
    handlers = re.findall(r"oninput:event=>\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", source)
    assert len(handlers) >= 7
    assert any("row[f.key]" in handler for handler in handlers)
    assert any("row.price" in handler for handler in handlers)
    assert any("values[index]" in handler for handler in handlers)
    assert any("pair.abilityId" in handler for handler in handlers)
    assert any("resultCommandIds" in handler for handler in handlers)
    for handler in handlers:
        assert "render(" not in handler, "oninput must not replace the focused control while typing"
        assert "markChanged()" in handler, "typing must still update the shared dirty state"
