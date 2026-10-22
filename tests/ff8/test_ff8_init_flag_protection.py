"""Starting Data keeps unproven bits intact through saves and source copies."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, init_data
from plugins.ff8.server import create_server
from test_ff8_init_write_validation import files, snapshot

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from test_shared_ui_feedback import page, framework


UNKNOWN = [('config', 'flags', 0xA5 ^ bit) for bit in (2, 4, 8)] + [
    ('character', 'status', 0xA5A5 ^ (1 << bit)) for bit in range(7, 16)]


@pytest.mark.parametrize('kind,field,value', UNKNOWN)
def test_init_unknown_flags_reject_batch_without_outputs(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='unknown flags are read-only'):
        formats.save_init([dict(kind='general', field='gil', value=123),
                           dict(kind=kind, id=1 if kind == 'character' else 0, field=field, value=value)])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('kind,field,value', UNKNOWN)
def test_init_unknown_flags_preserve_existing_output(files, kind, field, value):
    root, _, _ = files
    formats.save_init([dict(kind='general', field='gil', value=123)])
    before = snapshot(root)
    with pytest.raises(ValueError, match='unknown flags are read-only'):
        formats.save_init([dict(kind='config', field='volume', value=77),
                           dict(kind=kind, id=1 if kind == 'character' else 0, field=field, value=value)])
    assert snapshot(root) == before


def changes():
    return [dict(kind='config', field='flags', value=0xB5),
            dict(kind='config', field='map_seal', value=0),
            dict(kind='character', id=1, field='status', value=0xA5A7),
            dict(kind='character', id=1, field='junctioned_gfs', value=0xFFFF)]


def assert_reload(source, output):
    original = bytes([0xA5]) * (init_data.FULL_SIZE + 19)
    expected = bytearray(original)
    expected[init_data.CONFIG_OFFSET + 4] = 0xB5
    expected[init_data.CONFIG_OFFSET + 7] = 0
    base = init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE
    expected[base + 150:base + 152] = b'\xa7\xa5'
    expected[base + 88:base + 90] = b'\xff\xff'
    assert (output / 'init.out').read_bytes() == bytes(expected)
    assert (source / 'init.out').read_bytes() == original
    rows = formats.init_rows()
    for change in changes():
        owner = rows['config'] if change['kind'] == 'config' else rows['characters']['rows'][1]
        assert next(field['value'] for field in owner['fields'] if field['field'] == change['field']) == change['value']
    lookup = next(field['lookup'] for field in rows['config']['fields'] if field['field'] == 'flags')
    assert {entry['mask'] for entry in lookup['entries'] if entry.get('readonly')} == {2, 4, 8}


def test_init_known_flags_reload_and_preserve_unknown_bits(files):
    _, source, output = files
    assert formats.save_init(changes())['saved'] == 4
    assert_reload(source, output)


def test_init_flag_http_rejects_unknown_delta_then_saves_known_changes(files):
    root, source, output = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/init/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([changes()[0], dict(kind='character', id=1, field='status', value=0xA4A5)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request(changes()), timeout=5) as response:
            assert json.load(response)['saved'] == 4
        assert_reload(source, output)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


@pytest.mark.parametrize('kind,field_name,control_name,writable', [
    ('config', 'flags', 'Battle vibration trigger', 0xF1),
    ('character', 'status', 'Death', 0x7F),
])
def test_init_flag_controls_and_reference_setter_keep_unknown_bits(page, files, kind, field_name, control_name, writable):
    _, source, output = files
    rows = formats.init_rows()
    owner = rows['config'] if kind == 'config' else rows['characters']['rows'][1]
    field = next(field for field in owner['fields'] if field['field'] == field_name)
    original = field['value']
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins' / 'ff8' / 'editor.css'))
    party = (ROOT / 'plugins' / 'ff8' / 'party.js').read_text(encoding='utf-8')
    places = (ROOT / 'plugins' / 'ff8' / 'places.js').read_text(encoding='utf-8')
    start, end = '  function fieldControl(', '  function enemyDisplayName('
    assert party.count(start) == party.count(end) == 1
    begin, finish = '  function initOwner(', '  function startingFields('
    assert places.count(begin) == places.count(finish) == 1
    page.add_script_tag(content='''
      const el=LexeditorUI.el,shell={refresh:()=>{}},conceptIcon=()=>null;
      const sourceControl=(control,read,vanilla,refs,set)=>{window.copyReference=set;return control;};
      window.state={vanilla:{},references:[],referenceData:{}};
    ''' + party[party.index(start):party.index(end)] + places[places.index(begin):places.index(finish)])
    page.evaluate('''([field,kind])=>{
      window.field=field;
      window.renderFlags=()=>document.querySelector('main').replaceChildren(LexeditorUI.detailPanel({
        title:'Starting Data',body:[LexeditorUI.detailField({label:field.label,control:initFieldSource(field,kind,1)})]
      }));
      renderFlags();
    }''', [field, kind])
    if kind == 'config':
        for name in ('Unknown bit 1', 'Unknown bit 2', 'Unknown bit 3'):
            assert page.get_by_role('checkbox', name=name, exact=True).is_disabled()
    page.get_by_role('checkbox', name=control_name, exact=True).uncheck()
    assert page.evaluate('field.value') == original ^ 1
    page.evaluate('copyReference(0)')
    expected = original & ~writable
    assert page.evaluate('field.value') == expected
    page.evaluate('renderFlags()')
    assert not page.get_by_role('checkbox', name=control_name, exact=True).is_checked()
    if kind == 'config':
        assert page.get_by_role('checkbox', name='Unknown bit 2', exact=True).is_checked()
    page.wait_for_timeout(150)
    picture = Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'rendered' / f'ff8-starting-{kind}-flags.png'
    picture.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(picture))
    formats.save_init([dict(kind=kind, id=1 if kind == 'character' else 0, field=field_name, value=expected)])
    raw = (output / 'init.out').read_bytes()
    offset = init_data.CONFIG_OFFSET + 4 if kind == 'config' else init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE + 150
    size = 1 if kind == 'config' else 2
    original_bytes = bytes([0xA5]) * (init_data.FULL_SIZE + 19)
    expected_bytes = bytearray(original_bytes)
    expected_bytes[offset:offset + size] = expected.to_bytes(size, 'little')
    assert raw == bytes(expected_bytes)
    assert (source / 'init.out').read_bytes() == original_bytes
