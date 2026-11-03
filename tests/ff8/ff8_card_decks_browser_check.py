"""Real-service starting rare-card editing, global Save and reopen."""
from pathlib import Path
import json
import os
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ff8 import paths, cards
from plugins.ff8.plugin import FF8Session
from playwright.sync_api import sync_playwright


def payload(url):
    with urlopen(url + '/api/cards', timeout=120) as response:
        return json.load(response)


def main():
    if not (paths.GAME_ROOT / 'FF8_EN.exe').exists():
        print('SKIP: installed FF8 required for real-service deck editor')
        return
    with tempfile.TemporaryDirectory(prefix='lexeditor-card-decks-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT': project}) as session:
            original = payload(session.url)
            first, second = original['rows'][77:79]
            assert first['startingOwner'] == 200 and second['startingOwner'] == 201
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True, args=['--mute-audio'])
                try:
                    page = browser.new_page(viewport={'width':1600,'height':900})
                    errors=[]
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    def open_deck():
                        page.wait_for_function("()=>typeof state!=='undefined'&&!state.booting",timeout=180000)
                        page.evaluate("()=>navigate('cards')")
                        page.get_by_role('tab',name='DECKS',exact=True).click()
                        search=page.get_by_label('Search decks',exact=True)
                        search.wait_for(timeout=180000)
                        search.fill('200')
                        row=page.locator('.ff8-card-decks .lex-column-list-row').filter(has_text='#200').first
                        row.click()
                        page.get_by_role('button',name=f"Remove {first['name']} from deck 200",exact=True).wait_for()
                    open_deck()
                    page.get_by_role('button',name='Add rare card to deck 200',exact=True).click()
                    page.get_by_role('button',name=second['name'],exact=True).click()
                    page.get_by_role('button',name=f"Remove {second['name']} from deck 200",exact=True).wait_for()
                    page.wait_for_function('()=>dirtyCount()>0')
                    page.evaluate("()=>document.querySelector('#global-save').click()")
                    page.wait_for_function('()=>dirtyCount()===0',timeout=120000)
                    assert payload(session.url)['rows'][78]['startingOwner'] == 200
                    page.reload()
                    open_deck()
                    page.get_by_role('button',name=f"Remove {second['name']} from deck 200",exact=True).wait_for()
                    assert page.locator("section[aria-label='STARTING RARE CARDS'] img").count() == 2
                    page.wait_for_function("()=>[...document.querySelectorAll(\"section[aria-label='STARTING RARE CARDS'] img\")].every(image=>image.complete&&image.naturalWidth>0)")
                    page.get_by_role('button',name='Pin Starting rare cards column',exact=True).click()
                    page.locator('.lex-column-list-head-cell[data-column-key="rareCards"]').wait_for()
                    page.get_by_label('Search decks',exact=True).fill('')
                    if not os.environ.get('CI'):
                        screenshot=Path(tempfile.gettempdir())/'lexeditor-dev'/'todo-real-card-decks.png'
                        screenshot.parent.mkdir(parents=True,exist_ok=True)
                        page.wait_for_timeout(300)
                        page.screenshot(path=str(screenshot))
                    assert not errors, errors
                except Exception:
                    print('Decks browser errors:', errors, flush=True)
                    print(page.locator('body').inner_text()[:3500], flush=True)
                    raise
                finally:
                    browser.close()
            edits=cards.project_edits(Path(project),(paths.GAME_ROOT/'FF8_EN.exe').read_bytes())
            assert edits == [{'id':78,'field':'startingOwner','value':200}]
            assert '8DFF20 = ' in (Path(project)/cards.HEXT).read_text()
        with FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
            assert payload(session.url)['rows'][78]['startingOwner'] == 200
    print('PASS real-service Decks: actual rare artwork, assignment, global Save, reload, pinning, generated Hext and service restart')


if __name__ == '__main__':
    main()
