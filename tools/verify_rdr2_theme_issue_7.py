import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('id: "global-save", class: "save lex-save-icon' in FRAMEWORK_JS,
        "Save must use its own color-emoji class")
require('class: "save lex-ui-symbol"' not in FRAMEWORK_JS,
        "Save must not use the monochrome utility-symbol class")
require(".lex-save-icon" in FRAMEWORK_CSS and '"Segoe UI Emoji"' in FRAMEWORK_CSS,
        "the shared save class must prefer the Windows color-emoji font")
require("nav button" in RDR2 and "font-family:var(--rdr-font-display)" in RDR2,
        "every RDR2 main tab must use the Chinese Rocks display face")
require('class:"item-list-name"' in RDR2,
        "the visible item name must have a display-font class")
require('class:"item-list-id"' in RDR2,
        "the internal item ID must have a technical monospace class")
require(".item-list-name" in RDR2 and "var(--rdr-font-display)" in RDR2,
        "item list names must use the display face")
require(".item-list-id" in RDR2 and "Consolas" in RDR2,
        "item IDs must remain clearly monospace")
require("#global-save:disabled { color:#77736c; background:#34312c; border-color:#49453e; opacity:.48; filter:grayscale(1)" not in RDR2,
        "the RDR2 disabled state must not strip the save icon color")
def css_number(property_name: str) -> float:
    match = re.search(rf"{re.escape(property_name)}\s*:\s*([0-9.]+)%?", RDR2)
    require(match is not None, f"RDR Lino needs {property_name}")
    return float(match.group(1))


size_adjust = css_number("size-adjust")
ascent = css_number("ascent-override")
descent = css_number("descent-override")
line_gap = css_number("line-gap-override")
control_line_height = css_number("line-height")
require(92 <= size_adjust < 100,
        "RDR Lino must be optically reduced without shrinking every CSS box")
require(ascent > 80 and descent < 20 and abs(ascent + descent - 100) < 0.01,
        "RDR Lino must move its baseline down through balanced font metrics")
require(line_gap >= 15,
        "RDR Lino must retain a stable corrected line box")
require('input:not([type="checkbox"]):not([type="radio"]), select, textarea' in RDR2
        and control_line_height >= 1.3,
        "RDR2 text controls must leave visible vertical breathing room")

print("RDR2 theme issue 7 source contract passed")
