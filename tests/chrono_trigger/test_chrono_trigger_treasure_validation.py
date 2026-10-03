"""Treasure edits retain unknown contents bits and validate whole batches."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.field_data import TREASURE_DATA_PATH, TREASURE_OFFSET_PATH, save_treasure
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def files(tmp_path):
    offsets = struct.pack('<IHH', 2, 0, 4) + b'OPAQUE'
    original = b'HEAD' + struct.pack('<BBHH', 1, 2, 0x0E05, 0xBEEF) + struct.pack('<BBHH', 3, 4, 0x800A, 0xCAFE) + struct.pack('<BBHH', 0, 0, 12, 0x1234) + struct.pack('<BBHH', 5, 6, 0x6001, 0x5678)
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(TREASURE_OFFSET_PATH, offsets), (TREASURE_DATA_PATH, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    good = dict(token='0:0', values=dict(xTile=255, yTile=0, kind='armor', localIndex=511))
    expected = b'HEAD' + struct.pack('<BBH', 255, 0, 0x1FFF) + original[8:]
    return tmp_path, game, project, store, offsets, original, good, expected


BAD = [dict(values={field: value}) for field in ('xTile', 'yTile', 'gold', 'localIndex')
       for value in (False, .5, float('inf'), float('nan'), '1.5', None)] + [
    dict(token=False), dict(values=None), dict(values=[]), dict(values=False),
    dict(values=dict(trailingWord=0)), dict(values=dict(aliasScene=0)), dict(values=dict(globalItemId=1)),
    dict(values=dict(kind=None)), dict(values=dict(kind=[])), dict(values=dict(kind='unknown')),
    dict(values=dict(gold=3)), dict(values=dict(gold=65536)), dict(values=dict(localIndex=512)),
    dict(values=dict(xTile=0, yTile=0)), dict(token='0:2'), dict(token='0:3')]


@pytest.mark.parametrize('changes', BAD)
def test_invalid_later_record_preserves_new_and_existing_outputs(files, changes):
    root, _, project, store, offsets, original, good, _ = files
    later = dict(token='0:1', values={}) | changes
    for existing in (False, True):
        if existing:
            save_treasure(store, digest(original), digest(offsets), [good])
        payload = (project / TREASURE_DATA_PATH).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_treasure(store, digest(payload), digest(offsets), [good, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('later', [None, [], False, dict(token='0:0'), dict(token='1:0')])
def test_malformed_duplicate_or_missing_records_reject(files, later):
    root, _, _, store, offsets, original, good, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_treasure(store, digest(original), digest(offsets), [good, later])
    assert snapshot(root) == before


@pytest.mark.parametrize('kind,prefix', [('weapon', 0), ('armor', 0x1000), ('helmet', 0x2000), ('accessory', 0x3000), ('consumable', 0x4000), ('item', 0x5000)])
def test_item_categories_preserve_unknown_bits_and_trailing_words(files, kind, prefix):
    _, game, project, store, offsets, original, good, _ = files
    vanilla = snapshot(game)
    result = save_treasure(store, digest(original), digest(offsets), [good | dict(values=dict(kind=kind, localIndex=511))])
    assert (project / TREASURE_DATA_PATH).read_bytes() == original[:6] + struct.pack('<H', prefix | 0x0FFF) + original[8:]
    assert result['rows'][0]['kind'] == kind
    assert result['rows'][0]['localIndex'] == 511
    assert not (project / TREASURE_OFFSET_PATH).exists()
    assert snapshot(game) == vanilla


def test_position_and_empty_edits_preserve_entire_contents_word(files):
    _, _, project, store, offsets, original, good, _ = files
    save_treasure(store, digest(original), digest(offsets), [good | dict(values={})])
    assert (project / TREASURE_DATA_PATH).read_bytes() == original
    save_treasure(store, digest(original), digest(offsets), [good | dict(values=dict(xTile=255))])
    assert (project / TREASURE_DATA_PATH).read_bytes() == original[:4] + b'\xFF' + original[5:]


def test_unknown_item_bits_cannot_be_reinterpreted_as_gold(files):
    root, _, _, store, offsets, original, good, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='Unknown item contents bits'):
        save_treasure(store, digest(original), digest(offsets), [dict(token='0:1', values=dict(gold=0)), good | dict(values=dict(kind='gold', gold=200))])
    assert snapshot(root) == before


def test_gold_bounds_and_conversion_without_unknown_bits(files):
    _, _, project, store, offsets, original, _, _ = files
    result = save_treasure(store, digest(original), digest(offsets), [dict(token='0:1', values=dict(gold=65534, localIndex=1))])
    payload = original[:12] + struct.pack('<H', 0xFFFF) + original[14:]
    assert (project / TREASURE_DATA_PATH).read_bytes() == payload
    assert result['rows'][1]['gold'] == 65534
    result = save_treasure(store, digest(payload), digest(offsets), [dict(token='0:1', values=dict(kind='weapon', localIndex=0, gold=0))])
    payload = original[:12] + b'\x00\x00' + original[14:]
    assert (project / TREASURE_DATA_PATH).read_bytes() == payload
    result = save_treasure(store, digest(payload), digest(offsets), [dict(token='0:1', values=dict(kind='gold', gold=0))])
    assert (project / TREASURE_DATA_PATH).read_bytes() == original[:12] + b'\x00\x80' + original[14:]
    assert result['rows'][1]['gold'] == 0


def test_http_rejection_and_valid_reload(files):
    _, game, project, _, offsets, original, good, expected = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/treasure/save', data=json.dumps(dict(
                dataSha256=digest(payload), offsetSha256=digest(offsets), edits=edits)).encode(),
                headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    assert json.load(response)['rows'][0]['localIndex'] == 511
                assert (project / TREASURE_DATA_PATH).read_bytes() == expected
            payload = expected if existing else original
            for values in (None, dict(gold=.5), dict(trailingWord=0), dict(kind=[])):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, dict(token='0:1', values=values)], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()


def test_rendered_treasure_type_choices_respect_unknown_bits(files):
    from playwright.sync_api import sync_playwright

    _, game, project, _, _, _, _, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1400, 'height': 900})
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.busy")
                page.evaluate("()=>navigate('treasure')")
                page.wait_for_function("()=>!state.busy&&state.treasure.rows.length===4")
                choices = page.evaluate("""() => state.treasure.rows.slice(0,2).map(row => {
                    const panel=treasureDetail(row);
                    document.body.append(panel);
                    const select=panel.querySelector('select');
                    const result={bits:row.unknownContentsBits, values:[...select.options].map(option=>option.value)};
                    panel.remove();
                    return result;
                })""")
                assert choices[0] == dict(bits=0x0E00, values=['weapon', 'armor', 'helmet', 'accessory', 'consumable', 'item'])
                assert choices[1] == dict(bits=0, values=['weapon', 'armor', 'helmet', 'accessory', 'consumable', 'item', 'gold'])
            finally:
                browser.close()
    assert session.wait_closed()
