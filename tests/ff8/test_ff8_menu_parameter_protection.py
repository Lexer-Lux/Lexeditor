"""Unused menu parameters and reserved bits survive edits and source copies."""
import json
from pathlib import Path
import sys
import tempfile

import pytest

from plugins.ff8 import formats, menu_items

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from test_shared_ui_feedback import page, framework

ORIGINAL = bytes([1, 0xA5, 77, 0x81, 0, 0x5A, 3, 0x81, 20, 0xAA, 4, 0x81])


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla.bin'
    output = tmp_path / 'mod' / 'mitem.bin'
    source.write_bytes(ORIGINAL)
    monkeypatch.setattr(formats, 'source_path', lambda *args: output if output.exists() else source)
    monkeypatch.setattr(formats, 'output_path', lambda *args: output)
    return source, output


def edit(index, **changes):
    values = ORIGINAL[index * 4:index * 4 + 4]
    return dict(id=index, typeId=values[0], flags=values[1], param1=values[2], param2=values[3]) | changes


@pytest.mark.parametrize('bad', [edit(0, param1=78), edit(1, param2=1), edit(2, param2=1),
                              edit(0, typeId=2, param2=0)])
def test_menu_protected_changes_reject_batches_and_preserve_existing(files, bad):
    source, output = files
    with pytest.raises(ValueError, match='read-only'):
        formats.save_menu_items([edit((bad['id'] + 1) % 3, flags=0), bad])
    assert not output.exists()
    formats.save_menu_items([edit(0, flags=0)])
    before = output.read_bytes()
    with pytest.raises(ValueError, match='read-only'):
        formats.save_menu_items([edit((bad['id'] + 1) % 3, flags=0), bad])
    assert output.read_bytes() == before
    assert source.read_bytes() == ORIGINAL


def test_menu_documented_changes_preserve_unused_and_reserved_bytes(files):
    source, output = files
    formats.save_menu_items([edit(0, flags=0), edit(1, param1=255, param2=0x82), edit(2, param2=0x82)])
    assert output.read_bytes() == bytes([1, 0, 77, 0x81, 0, 0x5A, 255, 0x82, 20, 0xAA, 4, 0x82])
    assert source.read_bytes() == ORIGINAL


def test_menu_rendered_controls_and_copy_helper_preserve_protected_parameters(page, files):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins' / 'ff8' / 'editor.css'))
    core = (ROOT / 'plugins' / 'ff8' / 'core.js').read_text(encoding='utf-8')
    first, end = '  function numberControl(', '  function ratio255Control('
    start, finish = '  function bitFlagsControl(', '  function menuItemSection('
    assert all(core.count(marker) == 1 for marker in (first, end, start, finish))
    schema = json.loads((formats.SCHEMA_ROOT / 'mitem.json').read_text(encoding='utf-8'))
    rows = menu_items.read_rows(ORIGINAL, {}, formats.SCHEMA_ROOT)['rows']
    page.add_script_tag(content='''
      const el=LexeditorUI.el,toggleRow=LexeditorUI.toggleRow,autoFitControlText=LexeditorUI.autoFitControlText;
      const formatNumber=LexeditorUI.formatNumber,shell={refresh:()=>{}};
      window.state={data:{menuItems:{}}};
    ''' + core[core.index(first):core.index(end)] + core[core.index(start):core.index(finish)])
    page.evaluate('''([schema,rows])=>{
      state.data.menuItems.parameterTypes=schema.param_type;
      window.menuRows=rows;
      window.renderMenu=()=>document.querySelector('main').replaceChildren(LexeditorUI.detailPanel({title:'Menu parameters',body:[
        LexeditorUI.detailField({label:'Unused parameter',control:menuParameterControl(rows[0],'param1')}),
        LexeditorUI.detailField({label:'Status mask',control:menuParameterControl(rows[1],'param2')}),
        LexeditorUI.detailField({label:'Stat mask',control:menuParameterControl(rows[2],'param2')})]}));
      renderMenu();
    }''', [schema, rows])
    assert page.locator('input[type=number]').is_disabled()
    assert page.get_by_role('checkbox', name='Reserved', exact=True).is_disabled()
    assert page.get_by_role('checkbox', name='Unused', exact=True).is_disabled()
    page.get_by_role('checkbox', name='Poison', exact=True).check()
    page.get_by_role('checkbox', name='Str', exact=True).check()
    assert page.evaluate('menuRows.map(row=>row.param2)') == [0x81, 0x83, 0x83]
    page.evaluate("applyMenuParameter(menuRows[0],'param1',0);applyMenuParameter(menuRows[1],'param2',0);applyMenuParameter(menuRows[2],'param2',0)")
    assert page.evaluate('menuRows[0].param1') == 77
    assert page.evaluate('menuRows.map(row=>row.param2)') == [0x81, 0x80, 0x80]
    page.evaluate('renderMenu()')
    assert not page.get_by_role('checkbox', name='Poison', exact=True).is_checked()
    assert not page.get_by_role('checkbox', name='Str', exact=True).is_checked()
    picture = Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'rendered' / 'ff8-menu-protected-parameters.png'
    picture.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(picture))
    saved = page.evaluate('menuRows.map(({id,typeId,flags,param1,param2})=>({id,typeId,flags,param1,param2}))')
    formats.save_menu_items(saved)
    expected = bytearray(ORIGINAL)
    expected[7] = expected[11] = 0x80
    assert files[1].read_bytes() == expected
    assert files[0].read_bytes() == ORIGINAL
