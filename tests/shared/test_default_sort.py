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
    assert 'if (!keptSort && options.order !== "given" && hasNames) {' in source
    assert 'keptSort = {key: "name", dir: 1,' in source
    assert 'compareRecords(left, right, {key: "name"})' in source
    assert 'const hasNames = records.some' in source


def test_own_sort_plugins_keep_their_order():
    exempt = {
        'plugins/chrono_trigger/editor.js': ('order:"given"', 1),
        'plugins/ds3/editor.js': ('order:"given"', 1),
        'plugins/factorio/editor.js': ('order:"given"', 1),
        'plugins/terraria/editor.js': ('order:"given"', 4),
        'plugins/stardew_valley/editor.js': ('order: "given"', 2),
        'plugins/project_zomboid/editor.js': ('order:"given"', 2),
        'plugins/blank/editor.js': ('order:"given"', 1),
        'plugins/ff8/core.js': ('order:"given"', 1),
        'plugins/ff8/cards_ui.js': ('order:"given"', 1),
        'plugins/ff7/workspace.js': ('order:"given"', 1),
        'plugins/ff7r/editor.js': ('order:"given"', 2),
        'plugins/ff7r2/editor.js': ('order:"given"', 3),
        'plugins/ff9/editor.js': ('order:"given"', 3),
        'plugins/ffx_x2/editor.js': ('order:"given"', 2),
        'plugins/bannerlord/editor_shared.js': ('order:"given"', 1),
        'plugins/warband/editor.js': ('order:"given"', 2),
        'plugins/rdr2/ai.js': ('order:"given"', 1),
        'plugins/rdr2/effects.js': ('order:"given"', 2),
        'plugins/rdr2/loot.js': ('order:"given"', 1),
        'plugins/rdr2/mobs.js': ('order:"given"', 1),
        'plugins/rdr2/crafting.js': ('order:"given"', 1),
        'plugins/rdr2/challenges.js': ('order:"given"', 1),
    }
    for rel, (marker, minimum) in exempt.items():
        source = (ROOT / rel).read_text(encoding='utf-8', errors='replace')
        found = source.replace('order: "given"', 'order:"given"').count('order:"given"')
        assert found >= minimum, rel
    stardew = (ROOT / 'plugins/stardew_valley/editor.js').read_text(encoding='utf-8', errors='replace')
    assert 'sort: {key: "name", dir: 1}' in stardew
    assert 'datasetSort: {key: "name", dir: 1}' in stardew
    assert 'datasetSort = {key: "name", dir: 1}' in stardew
    assert '{key: "id", dir: 1}' not in stardew


def test_mods_tab_keeps_load_order():
    source = ui()
    mods = source[source.index('className: "lex-mods-page"'):source.index('className: "lex-mods-page"') + 400]
    assert 'order: "given"' in mods


def test_mods_tab_shows_priority_numbers():
    source = ui()
    assert '{key: "priority", label: "Priority"' in source
    assert 'the higher number wins' in source
    assert 'localPaths().indexOf(row.path) + 1' in source


def test_ds1_sorts_by_name_and_exempts_time_order():
    source = ds1()
    assert 'sort:{key:"name",dir:1}' in source
    assert 'sort:{key:"id",dir:1}' not in source
    assert 'state.animScope.level==="events"))return filtered;' in source
    records = source[source.index('className:"ds1-records"'):source.index('className:"ds1-records"') + 300]
    assert 'order:"given"' in records
