"""Static contracts for Lexeditor issue 25 shared list presentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
rdr2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
rdr = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")

# Tweaks was deliberately returned to the ordinary tab run. Settings is the
# only shared special tab; Tweaks may keep its subtle lex-tweaks-tab marker but
# must not be grouped with Settings again.
assert 'const isSpecialTab = tab =>' in framework and 'tab.id === "settings"' in framework
assert '["settings", "tweaks"].includes(tab.id)' not in framework
assert 'tab.id === "tweaks" ? "lex-tweaks-tab"' in framework
assert 'localeCompare' in framework
assert 'lex-settings-tab' in framework and '.lex-settings-tab' in css
for source in (ff8, rdr, rdr2):
    assert 'Tweaks' in source
    assert '["settings","Settings"]' not in source and 'id:"settings",label:"Settings"' not in source
assert 'lex-page-summary' in framework and '${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}' in framework
assert 'of ${formatNumber(total)} ${noun}' not in framework
assert 'main{flex:1;min-height:0;height:auto' in ff8
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
_body = _resize[1][:400]
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
