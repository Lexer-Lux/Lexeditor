"""DS1 Messages view: the Maps tab lists a map's developer messages.

The Messages tab reads the open map's view like Lights does, with one
row per soapstone message and its Blood writing words resolved beside
it. Until the map view carries messages the pane says so plainly
instead of failing; the preview plumbing below already resolves real
Blood writing entries through the Text tab's endpoint.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.msb import MESSAGE_EVENT, MESSAGE_TEXT_BANK
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

MAP = 'm10_00_00_00.msb'
WORDS = {1000: 'Path ahead', 1001: 'Treasure ahead\nCheck twice'}


def build_map_with_messages():
    parts = (('enemy', 2, 0, 0, 120000), ('player', 4, 0, 1, None),
             ('piece', 0, 0, 1, None), ('chest', 1, 0, 1, None),
             ('zone', 5, 0, 1, None))
    points = (('pt0', (1.0, 2.0, 3.0)), ('pt1', (4.0, 5.0, 6.0)))

    def msg(name, seq, point, text):
        return (name, MESSAGE_EVENT, seq, 2, (4, point, -1, 0),
                struct.pack('<2i', MESSAGE_TEXT_BANK + text, 1))

    events = (msg('msg0', 0, 0, 1000), msg('msg1', 1, 1, 1001),
              ('oa0', 7, 0, 2, (4, 0, -1, 0), struct.pack('<4i', 1, 2, 3, 4)),
              ('end0', 11, 0, 2, (4, 0, -1, 0), bytes(32)))
    return build_msb(parts=parts, points=points, events=events)


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-messages-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(
            make_menu_archive(extra={'Blood_writing_.fmg': dict(WORDS)}))
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / MAP).write_bytes(build_map_with_messages())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView && !state.error')
                    assert page.evaluate('state.mapView.map') == MAP
                    page.wait_for_selector('[data-tabstrip-id="messages"]')
                    tabs = page.locator('[data-tabstrip-id]').evaluate_all(
                        'nodes=>nodes.map(n=>n.dataset.tabstripId)')
                    assert tabs == ['maps', 'placements', 'lights', 'messages', 'collision'], tabs
                    page.locator('[data-tabstrip-id="messages"]').click()
                    page.wait_for_function('state.mapTab==="messages"')
                    if page.evaluate('state.mapView.messages===undefined'):
                        note = page.locator('[data-maps-side] .lex-detail-note')
                        assert note.count() == 1
                        assert 'not available in this build' in note.inner_text()
                    else:
                        rows = page.locator('[data-maps-side] .lex-column-list-row')
                        assert rows.count() == 2, rows.count()
                        first = page.evaluate(
                            'messageTextPreview(1000).then(t=>t)')
                        assert first == 'Path ahead', first
                    # The preview plumbing resolves real Blood writing words.
                    assert page.evaluate('messageTextPreview(1000)') == 'Path ahead'
                    assert page.evaluate('messageTextPreview(1001)') == 'Treasure ahead'
                    assert page.evaluate('messageTextPreview(9999)') == '(no message text 9999)'
                    # Rows render (not the unavailable note) once the view carries them.
                    assert page.evaluate(
                        'Array.isArray(state.mapView.messages)') is True
                    rows = page.locator('[data-maps-side] .lex-column-list-row')
                    assert rows.count() == 2, rows.count()
                    rows.nth(0).click()
                    page.wait_for_function(
                        'state.row?.table === "m10_00_00_00.msb"'
                        ' && String(state.row?.id).startsWith("message:") && !state.error')
                    # Editing the text re-points the cached message and its preview.
                    text = page.locator('input[data-field-key="text"]')
                    assert text.count() == 1
                    text.fill('1001')
                    page.locator('.lex-detail-panel-heading').click()
                    page.wait_for_function('state.mapView.messages[0].textId === 1001')
                    assert 'Treasure ahead' in page.locator('#main').inner_text()
                    # Duplicate under the next free identity, then remove it again.
                    page.locator('[data-row-action="duplicate"]').click()
                    page.wait_for_function(
                        'document.querySelectorAll('
                        "'[data-maps-side] .lex-column-list-row').length === 3")
                    page.locator('[data-row-action="remove"]').click()
                    page.locator('.lex-dialog').wait_for()
                    page.locator('.lex-dialog button',
                                 has_text='Remove').last.click()
                    page.wait_for_function(
                        'document.querySelectorAll('
                        "'[data-maps-side] .lex-column-list-row').length === 2")
                    assert not errors, errors
                    # The detail face lands on the Text tab entry it names.
                    page.evaluate('navigate("text","fmg-blood-writing","Blood_writing_.fmg:1000")')
                    page.wait_for_function(
                        'state.tab==="text" && state.row?.table==="Blood_writing_.fmg"'
                        ' && state.row?.id===1000 && !state.error')
                    assert 'Path ahead' in page.locator('#main').inner_text()
                    # Placements and Lights still render beside Messages.
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView && !state.error')
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"')
                    page.wait_for_selector('[data-maps-dir] .lex-column-list')
                    page.locator('[data-tabstrip-id="lights"]').click()
                    page.wait_for_function('state.mapTab==="lights"')
                    page.wait_for_selector('[data-maps-side] .lex-column-list, [data-maps-side] .lex-detail-note')
                    assert not errors, errors
                    assert page.locator('.lex-dialog').count() == 0
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        print('DS1 Messages view passed.')


if __name__ == '__main__':
    main()
