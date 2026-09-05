"""Source contract for the composable shared Detail panel."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
warband = (ROOT / "games" / "warband" / "editor.html").read_text(encoding="utf-8")

for token in (
    "const detailPanel = (options = {}) =>", "lex-detail-panel-heading",
    "lex-detail-panel-icon", "lex-detail-panel-identity", "lex-detail-panel-actions",
    "lex-field-readonly-lock", 'grid-template-rows:10% minmax(0,1fr)',
):
    assert token in framework or token in css, token
assert 'input.readOnly || input.disabled || input.tagName === "OUTPUT"' in framework
assert '? "READ ONLY"' not in framework
assert '.lex-column-list-head-cell {' in css and 'font-weight:750' in css
assert "detailPanel," in framework
assert "detailPanel({className:\"warband-item-detail\",icon:thumbnail" in warband
assert "warband-item-head" not in warband

print("Shared Detail panel issue 46 contract passed")
