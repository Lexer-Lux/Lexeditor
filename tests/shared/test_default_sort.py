"""Source-level contract for the default A-to-Z record sort."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / 'ui' / 'framework.js'
DS1 = ROOT / 'plugins' / 'ds1' / 'editor.js'


def ui():
    return UI.read_text(encoding='utf-8', errors='replace')


def ds1():
    return DS1.read_text(encoding='utf-8', errors='replace')


def test_paged_list_defaults_to_name_ascending():
    source = ui()
    assert 'let keptSort = pagedSortStates.get(rowPreferenceKey);' in source
    assert 'if (!keptSort && options.order !== "given") {' in source
    assert 'keptSort = {key: "name", dir: 1,' in source
    assert 'compareRecords(left, right, {key: "name"})' in source


def test_mods_tab_keeps_load_order():
    source = ui()
    mods = source[source.index('className: "lex-mods-page"'):source.index('className: "lex-mods-page"') + 400]
    assert 'order: "given"' in mods


def test_ds1_sorts_by_name_and_exempts_time_order():
    source = ds1()
    assert 'sort:{key:"name",dir:1}' in source
    assert 'sort:{key:"id",dir:1}' not in source
    assert 'state.animScope.level==="events"))return filtered;' in source
    records = source[source.index('className:"ds1-records"'):source.index('className:"ds1-records"') + 300]
    assert 'order:"given"' in records
