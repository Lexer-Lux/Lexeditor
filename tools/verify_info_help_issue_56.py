"""Shared filled-circle help-marker contract for Lexeditor issue 56."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
rdr2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const infoHelp =" in framework and "infoHelp," in framework,
        "the framework must export one shared help-marker primitive")
require(".lex-info-help {" in css and "border-radius: 50%" in css,
        "shared CSS must own the filled circular marker")
require("lex-help-popover" in framework and ".lex-help-popover {" in css,
        "the shared marker must own an immediate themed popup")
require("background: var(--lex-highlight)" in css,
        "the standard help marker must be filled, not an outlined or bare question mark")
require("LexeditorUI.infoHelp" in rdr2,
        "RDR2 help markers must call the shared primitive")
require("infoHelp(" in ff8,
        "FF8 help markers must call the shared primitive")
require(".field-help {" not in rdr2 and ".shop-help" not in ff8,
        "plugins must not own help-marker appearance")
require('class:"help",title:' not in ff8 and 'class:"field-help",title:' not in rdr2,
        "plugins must not hand-build bare question-mark help DOM")

print("Shared filled-circle help issue 56 source contract passed")
