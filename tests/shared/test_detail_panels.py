"""Detail panels: labels never grow rows, columns never overflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ui():
    return (ROOT / 'ui' / 'framework.js').read_text(encoding='utf-8', errors='replace')


def css():
    return (ROOT / 'ui' / 'framework.css').read_text(encoding='utf-8', errors='replace')


def test_field_labels_never_grant_row_height():
    source = ui()
    assert 'label.parentElement.style.minHeight' not in source
    sheet = css()
    rule = sheet[sheet.index('.lex-detail-field-label-text {'):sheet.index(
        '.lex-detail-field-label-text {') + 200]
    assert 'overflow:hidden;' in rule.replace(' ', '')


def test_chosen_columns_beat_the_fitted_width():
    source = ui()
    assert 'if(chosen>0)return Math.max(1,Math.min(length,chosen));' in source
    assert 'root.lexFittedColumns=fit;' in source
    assert 'moreColumns.disabled = count >= 6;' in source


def test_detail_scroll_never_runs_sideways():
    assert '.lex-master-detail .lex-tweaks-scroll { overflow-x:clip; }' in css()
