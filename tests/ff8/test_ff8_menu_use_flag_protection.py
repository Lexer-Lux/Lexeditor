"""Stored use flags ignored by special item types are preserved."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, menu_items
from plugins.ff8.server import create_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from test_shared_ui_feedback import page, framework

TYPES = (9, 12, 13, 14, 15, 19, 0)
ORIGINAL = b''.join(bytes([kind, 0xA5, 1, 2]) for kind in TYPES)


def edit(index, **changes):
    return dict(id=index, typeId=TYPES[index], flags=0xA5, param1=1, param2=2) | changes


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla.bin'
    output = tmp_path / 'mod' / 'mitem.bin'
    source.write_bytes(ORIGINAL)
    monkeypatch.setattr(formats, 'source_path', lambda *args: output if output.exists() else source)
    monkeypatch.setattr(formats, 'output_path', lambda *args: output)
    return source, output


@pytest.mark.parametrize('index', range(6))
def test_ignored_use_flags_reject_batch_without_changing_existing_files(files, index):
    source, output = files
    with pytest.raises(ValueError, match='use flags are read-only'):
        formats.save_menu_items([edit(6, flags=0xA4), edit(index, flags=0)])
    assert not output.exists()
    formats.save_menu_items([edit(6, flags=0xA4)])
    before = output.read_bytes()
    with pytest.raises(ValueError, match='use flags are read-only'):
        formats.save_menu_items([edit(6, flags=0xA3), edit(index, flags=0)])
    assert output.read_bytes() == before
    assert source.read_bytes() == ORIGINAL


@pytest.mark.parametrize('target', TYPES[:6])
def test_type_change_to_ignored_flags_preserves_original_flags(files, target):
    with pytest.raises(ValueError, match='use flags are read-only'):
        formats.save_menu_items([edit(6, typeId=target, flags=0)])
    assert not files[1].exists()
    formats.save_menu_items([edit(6, typeId=target)])
    expected = bytearray(ORIGINAL)
    expected[24] = target
    assert files[1].read_bytes() == expected


def test_known_use_flags_and_magazine_parameters_remain_editable(files):
    source, output = files
    formats.save_menu_items([edit(0, param1=3, param2=9), edit(6, flags=0xA4)])
    expected = bytearray(ORIGINAL)
    expected[2:4] = bytes([3, 9])
    expected[25] = 0xA4
    assert output.read_bytes() == expected
    assert source.read_bytes() == ORIGINAL
    payload = menu_items.read_rows(output.read_bytes(), {}, formats.SCHEMA_ROOT)
    assert {row['id'] for row in payload['types'] if row['flagsReadonly']} == set(TYPES[:6])


def test_use_flag_http_rejection_then_valid_save(files):
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/menu-items/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edit(6, flags=0xA4), edit(0, flags=0)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert not files[1].exists()
        with urlopen(request([edit(6, flags=0xA4)]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        assert files[1].read_bytes() == ORIGINAL[:25] + bytes([0xA4]) + ORIGINAL[26:]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_rendered_use_flags_and_copy_helper_keep_ignored_flags(page, files):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins' / 'ff8' / 'editor.css'))
    core = (ROOT / 'plugins' / 'ff8' / 'core.js').read_text(encoding='utf-8')
    start, end = '  function bitFlagsControl(', '  function menuItemSection('
    assert core.count(start) == core.count(end) == 1
    payload = menu_items.read_rows(ORIGINAL, {}, formats.SCHEMA_ROOT)
    page.add_script_tag(content='const toggleRow=LexeditorUI.toggleRow,shell={refresh:()=>{}};window.state={data:{}};' + core[core.index(start):core.index(end)])
    page.evaluate('''payload=>{
      state.data.menuItems=payload;window.rows=payload.rows;
      window.renderFlags=()=>document.querySelector('main').replaceChildren(LexeditorUI.detailPanel({
        title:'Menu use flags',body:rows.map(row=>LexeditorUI.detailField({label:row.typeName,
          control:menuFlagsControl(row)}))}));renderFlags();
    }''', payload)
    for index in range(6):
        controls = page.locator('.lex-detail-field').nth(index).get_by_role('checkbox')
        assert controls.count() == 8
        assert controls.evaluate_all('inputs=>inputs.every(input=>input.disabled)')
    normal = page.locator('.lex-detail-field').nth(6)
    normal.get_by_role('checkbox', name='Usable in menu', exact=True).uncheck()
    page.evaluate('rows.forEach(row=>applyMenuFlags(row,0));renderFlags()')
    assert page.evaluate('rows.map(row=>row.flags)') == [0xA5] * 6 + [0]
    picture = Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'rendered' / 'ff8-menu-use-flags.png'
    picture.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(picture))
    formats.save_menu_items(page.evaluate('rows.map(({id,typeId,flags,param1,param2})=>({id,typeId,flags,param1,param2}))'))
    assert files[1].read_bytes() == ORIGINAL[:25] + bytes([0]) + ORIGINAL[26:]
    assert files[0].read_bytes() == ORIGINAL
