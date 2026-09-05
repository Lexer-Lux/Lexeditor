"""Shared table-column pinning and reset contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    styles = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    assert "const columnPreferences =" in framework
    assert "lexeditor:columns:" in framework
    assert "pinButton:" in framework and 'class: `lex-column-pin${pinned ? " pinned" : ""}`' in framework
    assert ".lex-column-pin.pinned:active .lex-column-pin-off { display:block; }" in styles
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
