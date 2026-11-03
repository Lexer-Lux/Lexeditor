"""Recovered Field-to-World request: preview first, compact columns, saved placement."""
from pathlib import Path
import json
import sys
import tempfile
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests/shared'))
from paged_detail import reveal
from plugins.ff8.plugin import FF8Session

OUT = Path(sys.argv[1]) if len(sys.argv)>1 else Path(tempfile.gettempdir())/'lexeditor-dev/ff8-field-return-request'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-field-return-request-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT': project}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=['--mute-audio'])
                try:
                    page = browser.new_page(viewport={'width':1600, 'height':900})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=180000)
                    page.evaluate("state.worldTab='fieldReturns';state.selected.world=0;navigate('world')")
                    pane = page.locator('.world-field-return')
                    pane.wait_for(state='attached')
                    stage = pane.locator('.lex-image-map-stage')
                    reveal(page, stage)
                    original = page.evaluate("({...worldRow(state.data,'fieldReturn',0)})")
                    for width in (1600, 900):
                        page.set_viewport_size({'width':width,'height':900})
                        page.wait_for_timeout(300)
                        table = page.locator('.ff8-record-list').first
                        template = table.evaluate("node=>node.style.getPropertyValue('--lex-column-list-template')")
                        assert 'fr' not in template, template
                        assert table.evaluate('node=>node.scrollWidth<=node.clientWidth+1'), 'Coordinate columns extend beyond the list pane'
                        assert not pane.locator('.lex-notice,.lex-detail-note').count()
                        reveal(page, stage)
                        page.screenshot(path=str(OUT/f'field-returns-{width}.png'))
                    stage.click()
                    large = page.locator('.lex-map-magnifier-body .lex-image-map-stage')
                    large.wait_for(state='visible')
                    assert page.evaluate("({...worldRow(state.data,'fieldReturn',0)})") == original
                    box = large.bounding_box()
                    page.screenshot(path=str(OUT/'field-return-placement.png'))
                    page.mouse.click(box['x']+box['width']*.25, box['y']+box['height']*.75)
                    edited = page.evaluate("({...worldRow(state.data,'fieldReturn',0)})")
                    assert (edited['x'], edited['z']) != (original['x'], original['z'])
                    assert (edited['y'], edited['unknown']) == (original['y'], original['unknown'])
                    page.keyboard.press('Escape')
                    page.locator('#global-save').click()
                    page.wait_for_function('dirtyCount()===0&&document.querySelector("#global-save").disabled', timeout=60000)
                    with urlopen(session.url+'/api/world-map?dataset=current', timeout=60) as response:
                        saved = json.load(response)['fieldReturns'][0]
                    assert all(saved[key] == edited[key] for key in ('x','y','z','unknown'))
                    page.evaluate("state.worldTab='regions';state.selected.world=0;renderWorldMap()")
                    table = page.locator('.ff8-record-list').first
                    assert 'fr' not in table.evaluate("node=>node.style.getPropertyValue('--lex-column-list-template')")
                    page.screenshot(path=str(OUT/'cells-900.png'))
                    assert not errors, errors
                    print('Field Returns: compact shared columns, preview click preserves data, large-map placement saves; Cells uses the same sizing.')
                finally:
                    browser.close()


if __name__ == '__main__':
    main()
