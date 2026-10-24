"""Source-level contract for pinned columns: edit, reorder, in-place refresh."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / 'ui' / 'framework.js'
DS1 = ROOT / 'plugins' / 'ds1' / 'editor.js'


def ui():
    return UI.read_text(encoding='utf-8', errors='replace')


def ds1():
    return DS1.read_text(encoding='utf-8', errors='replace')


def test_pinned_columns_carry_editors():
    source = ui()
    assert 'const described = typeof owner.describe === "function"' in source
    assert 'edit: editable ? ((row, value) => owner.commitCell(row, entry.key, value)) : null' in source
    assert 'editValue: row => row?.values?.[entry.key] ?? ""' in source


def test_cell_editor_accepts_labelled_choices():
    source = ui()
    assert 'const [value, label] = Array.isArray(entry) ? entry : [entry, entry]' in source


def test_pin_owner_reorders_and_persists():
    source = ui()
    assert 'describe:options.describePinnedCell||null,commitCell:options.commitPinnedCell||null' in source
    assert 'move:(value,before)=>{' in source
    assert 'localStorage.setItem(pinOwner.store.key,JSON.stringify(rest))' in source


def test_header_drag_covers_pinned_columns():
    source = ui()
    assert 'if (options.columnPreferences || pinOwner?.move) {' in source
    assert 'pinOwner.move(value, before)' in source


def test_master_refreshes_without_the_detail_pane():
    source = ui()
    assert 'root.refreshValues = () => {' in source
    assert 'root.refreshMaster = () => {' in source
    assert 'barrelGrid.replaceChildren(...masterNodes)' in source
    assert 'const buildMasters = () => {' in source
    assert 'masterNodes = buildMasters();' in source


def test_ds1_wires_pinned_cells():
    source = ds1()
    assert 'describePinnedCell,commitPinnedCell,' in source
    assert 'function describePinnedCell(propertyKey){' in source
    assert 'function commitPinnedCell(record,propertyKey,value){' in source
    assert 'if(!field||!field.editable||field.type==="longtext")return null;' in source


def test_ds1_patches_rows_on_edit_and_repaints_only_the_table():
    source = ds1()
    assert 'function patchRowValues(table,id,values,display,name,modified){' in source
    assert 'target.values=values;target.display=display||{};' in source
    assert 'else state.pagedView?.refreshValues?.();' in source
    assert 'if(next.reason==="pins"&&state.pagedView?.refreshMaster){state.pagedView.refreshMaster();ds1LabelArt(state.pagedView);}else render();' in source


def test_ds1_lazy_fills_giant_dropdowns():
    source = ds1()
    assert 'if(choices.length>200){' in source
    assert 'new IntersectionObserver(entries=>' in source

def test_ds1_syncs_dependent_detail_controls():
    source = ds1()
    assert 'function syncDetailControl(propertyKey,value,control){' in source
    assert 'other.__lexValueSliderPaint?.();' in source
    assert 'syncDetailControl(field.key,changed.value,control);' in source
    assert 'syncDetailControl(item.key,item.value,control);' in source
