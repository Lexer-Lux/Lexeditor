"""Shared table-column pinning and reset contract."""

from pathlib import Path
from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    styles = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    ff8 = plugin_ui('ff8')
    assert "const columnPreferences =" in framework
    assert "lexeditor:columns:" in framework
    assert "pinButton:" in framework and 'class: `lex-column-pin${pinned ? " pinned" : ""}`' in framework
    # The pin now moves out of the table instead of showing an alternate
    # pressed glyph. Its state and accessible action still change together.
    assert 'button.classList.toggle(\'pinned\',inserting)' in framework
    assert 'button.setAttribute(\'aria-pressed\',String(inserting))' in framework
    assert '`Unpin ${label} column`' in framework and '`Pin ${label} column`' in framework
    assert ".lex-column-pin.pinned:hover .lex-column-pin-off" not in styles
    assert "options.columnPreferences.move" in framework
    assert 'draggable: false' in framework
    assert 'header.addEventListener("pointerdown"' in framework
    assert 'header.addEventListener("pointermove"' in framework
    assert 'header.addEventListener("pointerup"' in framework
    assert 'oncontextmenu: event =>' in framework and 'options.resetView?.(tab.id)' in framework
    assert "columnPreferences(`ff8-${view}`" in ff8
    assert "pinLabel(prefs" in ff8 and "weaponColumns()" in ff8
    print("Shared column pin, reorder, persistence, and tab-reset contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
