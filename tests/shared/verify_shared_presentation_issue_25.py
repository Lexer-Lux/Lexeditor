"""Static contracts for Lexeditor issue 25 shared list presentation."""

from pathlib import Path
import re

from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = plugin_ui("ff8")
rdr2 = plugin_ui("rdr2")
rdr = plugin_ui("rdr")

# The live request requires Tweaks last and distinct. The ordinary-fill
# assertion contradicted that request and the later navigation regression.
_special = framework.split('const isSpecialTab = tab =>', 1)[1].split(';', 1)[0]
assert 'tab.id === "settings"' in _special and 'tab.id === "tweaks"' in _special
assert 'const rank = tab => tab.id === "tweaks" ? 2' in framework
assert 'isSpecialTab(tab) ? "lex-settings-tab"' in framework
assert '"lex-tweaks-tab"' in framework
assert 'localeCompare' in framework
assert 'lex-settings-tab' in framework and '.lex-settings-tab' in css
for source in (ff8, rdr, rdr2):
    assert 'Tweaks' in source
    assert '["settings","Settings"]' not in source and 'id:"settings",label:"Settings"' not in source
assert 'lex-page-summary' in framework and '${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}' in framework
assert 'of ${formatNumber(total)} ${noun}' not in framework
_main = re.search(r'^main\s*\{([^}]+)', css, re.M)[1]
assert 'flex:1' in _main and 'min-height:0' in _main
assert re.search(r'(?:^|;)\s*height\s*:', _main) is None, 'main must retain natural flex sizing'
assert '--lex-fitted-row-height:36px' not in ff8
assert 'function sharedDetail' in ff8 and 'identity:el("span",{class:"lex-pinnable-property"}' in ff8
assert 'Character ID' not in ff8 and 'Item ID' not in ff8
assert 'root.classList.add("lex-paged-list-detail", "has-pager")' in framework
assert 'root.style.setProperty("--lex-pager-height"' in framework
# What matters is that a fitted page gives the list and the detail the same
# explicit height, and clears it again when the page is not full. Pinning the
# exact spelling of those two lines meant an ordinary refactor - hoisting the
# shared value into `fittedHeight` - failed a check whose behaviour was intact.
_resize = framework.split("resize: (height, measurement) =>", 1)
assert len(_resize) == 2, "the fitted page no longer has a resize hook"
_body = _resize[1].split('change: nextSize =>', 1)[0]
assert "measurement?.full" in _body and "${height}px" in _body, (
    "the fitted height is no longer derived from a full measurement")
assert "masterNode.style.height" in _body and "detailNode.style.height" in _body, (
    "a fitted page must size both the list and the detail")
assert 'available: root' in framework
assert '.lex-paged-list-detail.has-pager' in css
assert '.lex-paged-list-detail {' in css and 'height:100%' in css
assert '.lex-paged-list-detail > .lex-detail' in css and 'height:auto' in css
assert '.lex-paged-list-detail{height:calc(100% - 52px)}' not in ff8
for obsolete in ('itemcount', 'behaviorcount', 'effcount', 'lootcount'):
    assert obsolete not in rdr2, f"RDR2 still duplicates the pager total through {obsolete}"

print("Shared tab order, title identity, fitted rows, and pager totals passed")
