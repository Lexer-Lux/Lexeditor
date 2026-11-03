"""Asset fields live outside sections: shipped loose, or dragged out.

Lexer: the split-archive ARCHIVE row sat under PREVIEW, and dragging it
above the section to remove it did nothing - a field had to be in a
section. ARCHIVE now sits loose in the panel, and dropping a property on
a section's title lands it beside that section, above or below by
pointer half. The arrangement persists and undo restores it.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

HEADS = ("[...document.querySelectorAll('.lex-barrelled-master "
         ".lex-column-list-head-cell')].map(c=>c.dataset.columnKey)")
ARCHIVE = "Asset:chr/c0000/c0000.tpfbdt"
GARBAGE = "Asset:chr/c0000/garbage.dds"
LOOSE = """() => {
    const field = document.querySelector('.lex-detail-field[data-lex-layout-field="TEXTURES"]');
    const section = document.querySelector('.lex-detail-panel .lex-detail-section');
    if (!field || !section) return 'missing';
    if (field.closest('.lex-detail-section-content')) return 'inside';
    return (field.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING)
        ? 'loose-before' : 'loose-after';
}"""


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-asset-loose-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'chr' / 'c0000').mkdir(parents=True)
        (game / 'chr' / 'c0000' / 'c0000.tpfbdt').write_bytes(b'split archive bytes')
        (game / 'chr' / 'c0000' / 'garbage.dds').write_bytes(b'not a dds file')
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
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="textures"]').click()
                    page.wait_for_function('state.tab==="textures" && state.rows.length===2 && !state.error')
                    # The split archive names its kind loose: no PREVIEW
                    # section for a file with no preview.
                    page.locator(f'.lex-list-row[data-key="{ARCHIVE}"]').click()
                    page.wait_for_function(f'state.selected==="{ARCHIVE}" && state.assetDetail')
                    page.wait_for_timeout(500)
                    assert page.locator('.lex-detail-panel .lex-detail-section').count() == 0
                    archive = page.locator('.lex-detail-field[data-lex-layout-field="kind"]')
                    assert archive.count() == 1
                    assert archive.locator('.lex-detail-field-label-text').inner_text() == 'ARCHIVE'
                    # Its pin matches the built-in Kind column: no duplicate.
                    heads = page.evaluate(HEADS)
                    assert 'kind' in heads, heads
                    page.locator('.lex-detail-field[data-lex-layout-field="kind"] '
                                 '.lex-column-pin').click()
                    page.wait_for_timeout(400)
                    assert page.evaluate(HEADS) == heads, heads
                    kinds = page.locator('.lex-list-row[data-key] [data-column-key="kind"]').evaluate_all(
                        'nodes=>nodes.map(n=>n.innerText.trim())')
                    assert sorted(kinds) == ['Split archive', 'Textures'], kinds
                    # A property drags out of its section by the title.
                    page.locator(f'.lex-list-row[data-key="{GARBAGE}"]').click()
                    page.wait_for_function(f'state.selected==="{GARBAGE}" && state.assetDetail')
                    page.wait_for_timeout(500)
                    assert page.evaluate(LOOSE) == 'inside'
                    page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',"
                                  "{detail:{developerMode:true}}))")
                    label = page.locator('.lex-detail-panel .lex-detail-field-label-text',
                                         has_text='TEXTURES')
                    title = page.locator('.lex-detail-panel .lex-detail-section-title',
                                         has_text='PREVIEW')
                    label.hover()
                    label.drag_to(title, target_position={'x': 30, 'y': 4})
                    page.wait_for_timeout(600)
                    assert page.evaluate(LOOSE) == 'loose-before'
                    stored = page.evaluate(
                        "()=>{for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);"
                        "if(k.includes('.property-layout.'))return JSON.parse(localStorage.getItem(k));}return null;}")
                    assert stored['loose'] == {'PREVIEW:0/TEXTURES:0': 'PREVIEW:0'}, stored
                    if output:
                        page.screenshot(path=str(output / 'asset-loose.png'))
                    # The loose arrangement survives a reload.
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="textures"]').click()
                    page.wait_for_function('state.tab==="textures" && state.rows.length===2 && !state.error')
                    page.locator(f'.lex-list-row[data-key="{GARBAGE}"]').click()
                    page.wait_for_function(f'state.selected==="{GARBAGE}" && state.assetDetail')
                    page.wait_for_timeout(600)
                    assert page.evaluate(LOOSE) == 'loose-before'
                    # And back inside, by dropping on the section content.
                    # The emptied content keeps a landing pad only mid-drag,
                    # so the pointer walks there instead of jumping to it.
                    page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',"
                                  "{detail:{developerMode:true}}))")
                    label = page.locator('.lex-detail-panel .lex-detail-field-label-text',
                                         has_text='TEXTURES')
                    title = page.locator('.lex-detail-panel .lex-detail-section-title',
                                         has_text='PREVIEW')
                    start = label.bounding_box()
                    pad = title.bounding_box()
                    page.mouse.move(start['x'] + start['width'] / 2,
                                    start['y'] + start['height'] / 2)
                    page.mouse.down()
                    page.mouse.move(pad['x'] + 30, pad['y'] + pad['height'] + 14, steps=12)
                    page.mouse.up()
                    page.wait_for_timeout(600)
                    assert page.evaluate(LOOSE) == 'inside'
                    page.keyboard.press('Control+z')
                    page.wait_for_timeout(600)
                    assert page.evaluate(LOOSE) == 'loose-before'
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 asset loose fields passed.')


if __name__ == '__main__':
    main()
