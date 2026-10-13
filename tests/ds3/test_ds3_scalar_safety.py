"""Unknown PARAM fields remain visible, protected, and byte-preserving on save."""
from pathlib import Path
import struct

import pytest

from plugins.ds3.formats import FieldSpec, DS3FormatError, RegulationDocument, write_field
from test_ds3_plugin import _bnd4, METADATA


def test_unknown_and_fractional_edits_preserve_regulation_then_valid_edits_reopen():
    document = RegulationDocument(_bnd4(), METADATA)
    table = 'Magic'
    row_id = document.params[table].rows[0].row_id
    fields = document.read_row(table, row_id)['fields']
    unknown = next(field for field in fields if field['key'].lower().startswith('unknown'))
    assert not unknown['editable']
    known = next(field for field in fields if field['editable'] and field['type'] == 'number'
                 and field['dtype'] in {'u8', 'u16', 'u32', 's8', 's16', 's32'})
    before = document.plaintext()
    for key, value in [(unknown['key'], 1), (known['key'], 1.5),
                       (known['key'], float('nan')), (known['key'], True),
                       (known['key'], known['maximum'] + 1)]:
        with pytest.raises(DS3FormatError):
            document.edit(table, row_id, key, value)
        assert document.plaintext() == before and document.dirty_count == 0
    document.edit(table, row_id, known['key'], 1)
    reopened = RegulationDocument(document.export(), METADATA)
    values = {field['key']: field for field in reopened.read_row(table, row_id)['fields']}
    assert values[known['key']]['value'] == 1
    assert values[unknown['key']]['value'] == unknown['value']


@pytest.mark.parametrize('endian', ['<', '>'])
def test_bitfields_and_float_storage_limits_are_enforced(endian):
    data = b'\xa5\x00\x00\x00\x00KEEP'
    bit = FieldSpec('flags', 'u8', 0, bit_offset=1, bit_size=3)
    with pytest.raises(DS3FormatError):
        write_field(data, bit, 2.9, endian)
    changed = write_field(data, bit, 2, endian)
    assert changed[0] == (0xa5 & ~0x0e) | 4 and changed[1:] == data[1:]
    floating = FieldSpec('multiplier', 'f32', 1)
    for value in (floating.maximum * 2, float('inf'), float('nan'), True):
        with pytest.raises(DS3FormatError):
            write_field(data, floating, value, endian)
    changed = write_field(data, floating, floating.maximum, endian)
    assert struct.unpack_from(endian + 'f', changed, 1)[0] == floating.maximum
    assert changed[0] == data[0] and changed[5:] == b'KEEP'


def test_ds3_protected_fields_and_float_bounds_render(tmp_path):
    from playwright.sync_api import sync_playwright

    repo = Path(__file__).resolve().parents[2]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 900, 'height': 620})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(repo / 'ui/framework.css'))
            page.add_script_tag(path=str(repo / 'ui/framework.js'))
            page.add_script_tag(path=str(repo / 'plugins/ds3/editor.js'))
            limit = FieldSpec('multiplier', 'f32', 0).maximum
            page.evaluate('''limit=>{
              const U=LexeditorUI;
              document.querySelector('main').append(U.detailPanel({title:'DS3 parameter',body:[
                U.detailField({label:'Unknown',control:fieldControl('Magic',{id:1},
                  {key:'unknown',value:7,editable:false})}),
                U.detailField({label:'Multiplier',control:fieldControl('Magic',{id:1},
                  {key:'multiplier',label:'Multiplier',value:1,dtype:'f32',type:'number',minimum:-limit,maximum:limit,editable:true})})]}));
            }''', limit)
            unknown = page.locator('input.lex-readonly-field')
            assert unknown.is_disabled() and unknown.is_visible() and unknown.input_value() == '7'
            number = page.locator('input[aria-label=Multiplier]')
            assert float(number.get_attribute('min')) == -limit
            assert float(number.get_attribute('max')) == limit
            assert number.is_visible()
            page.screenshot(path=str(tmp_path / 'ds3-scalar-controls.png'))
        finally:
            browser.close()
