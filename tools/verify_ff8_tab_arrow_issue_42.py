"""Contract for the FF8 menu-font and overlaid native active pointer."""

from pathlib import Path
import sys

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8.game_font import ensure_font  # noqa: E402

EDITOR = ROOT / "games" / "ff8" / "editor.html"
ICONS = ROOT / "games" / "ff8" / "game_icons.py"


def main() -> int:
    editor = EDITOR.read_text(encoding="utf-8")
    icons = ICONS.read_text(encoding="utf-8")
    required = [
        ".lex-shell-header nav button{position:relative;display:inline-flex;align-items:center;justify-content:center",
        '.lex-shell-header nav button.active::before{content:none!important}',
        '.lex-shell-header nav button.active .lex-tab-label::before{position:absolute',
        'right:calc(100% + 3px);width:32px;height:22px',
        'background:url("/assets/icons/0.png") center/contain no-repeat',
        '.lex-shell-header nav .lex-tab-label{position:relative;display:inline-block}',
        '0: "Menu pointer"',
    ]
    for contract in required:
        if contract not in editor + icons:
            raise AssertionError(f"Missing native pointer/font contract: {contract}")
    forbidden = [
        '.lex-shell-header nav button.active::before{content:"►"',
        '.lex-shell-header nav button.active::before{content:"►";margin-right:7px;font-family:"Arial",sans-serif;font-size:11px;vertical-align:2px}',
        '.lex-shell-header nav button.active .lex-tab-label::before{position:relative',
    ]
    for contract in forbidden:
        if contract in editor:
            raise AssertionError(f"Font-baseline arrow alignment remains: {contract}")
    if 'ascent-override:88%;descent-override:12%;line-gap-override:0%' not in editor:
        raise AssertionError("FF8 text must use one shared font-face metric correction")
    if '.lex-shell-header nav button{vertical-align:' in editor:
        raise AssertionError("Tab alignment must not use a one-off baseline nudge")
    font = TTFont(ensure_font())
    cmap = font.getBestCmap()
    one_advance = font["hmtx"].metrics[cmap[ord("1")]][0]
    zero_advance = font["hmtx"].metrics[cmap[ord("0")]][0]
    if not 0 < one_advance < zero_advance:
        raise AssertionError("The private font must keep FF8's narrow-glyph correction for 1")
    print("FF8 menu ink and the native active pointer use corrected optical centers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
