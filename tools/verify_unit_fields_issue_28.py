"""Static unit-display contracts for Lexeditor issue 28."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")

assert "const unitField" in framework and "unitField," in framework
assert "const readonlyField" in framework and "readonlyField," in framework
assert '"lex-unit-field-boxed"' in framework
assert ".lex-unit-field-boxed" in css and "position: absolute" in css
assert ".lex-readonly-field:disabled" in css and "user-select: none" in css
assert 'unitField(numberControl(row.buyPrice' in ff8
assert 'sell=readonlyField(row.sellPrice)' in ff8
assert 'unitField(sell,"G"' in ff8
assert 'unitField(numberControl(row.sellMultiplier' in ff8 and '),"%"' in ff8
assert 'unitField(numberControl(row.upgradePrice' in ff8
assert 'unitField(flying,"% EVA")' in ff8
assert 'render:row=>gilValue(row.buyPrice)' in ff8
assert 'render:row=>gilValue(row.sellPrice)' in ff8

print("Shared unit fields and FF8 Gil display contracts passed")
