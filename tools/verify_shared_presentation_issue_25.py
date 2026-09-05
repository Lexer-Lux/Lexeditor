"""Static contracts for Lexeditor issue 25 shared list presentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
rdr2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
rdr = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")

assert 'const isSpecialTab = tab =>' in framework and '"settings", "tweaks"' in framework
assert 'localeCompare' in framework
assert 'lex-settings-tab' in framework and '.lex-settings-tab' in css
for source in (ff8, rdr, rdr2):
    assert '["settings","Tweaks"]' in source or 'id:"settings",label:"Tweaks"' in source
    assert '["settings","Settings"]' not in source and 'id:"settings",label:"Settings"' not in source
assert 'lex-page-summary' in framework and '${formatNumber(first)}-${formatNumber(last)}/${formatNumber(total)}' in framework
assert 'of ${formatNumber(total)} ${noun}' not in framework
assert 'main{flex:1;min-height:0;height:auto' in ff8
assert '--lex-fitted-row-height:36px' not in ff8
assert 'function sharedDetail' in ff8 and 'identity:el("span",{class:"lex-pinnable-property"}' in ff8
assert 'Character ID' not in ff8 and 'Item ID' not in ff8
assert 'root.classList.add("lex-paged-list-detail", "has-pager")' in framework
assert 'root.style.setProperty("--lex-pager-height"' in framework
assert 'masterNode.style.height = `${height}px`' in framework
assert 'detailNode.style.height = measurement?.full ? `${height}px` : ""' in framework
assert 'available: root' in framework
assert '.lex-paged-list-detail.has-pager' in css
assert '.lex-paged-list-detail {' in css and 'height:100%' in css
assert '.lex-paged-list-detail > .lex-detail' in css and 'height:auto' in css
assert '.lex-paged-list-detail{height:calc(100% - 52px)}' not in ff8
for obsolete in ('itemcount', 'behaviorcount', 'effcount', 'lootcount'):
    assert obsolete not in rdr2, f"RDR2 still duplicates the pager total through {obsolete}"

print("Shared tab order, title identity, fitted rows, and pager totals passed")
