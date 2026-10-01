"""Ground names edit, save, reload, and propagate to linked terrain labels."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from plugins.ff8.plugin import FF8Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ground-names-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session,sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1600,'height':950})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
            page.evaluate("state.activeSource='mine';state.worldTab='groundTypes';state.selected.world=6;navigate('world')")
            heading=page.get_by_role('textbox',name='Ground name',exact=True)
            original=heading.input_value()
            headers=page.locator('.lex-column-list-head-cell').all_text_contents()
            assert any('ID' in value and 'GROUND' not in value for value in headers),headers
            assert any('NAME' in value and 'DESCRIPTION' not in value for value in headers),headers
            heading.fill('Green meadow')
            heading.press('Tab')
            assert page.evaluate('worldGroundLabel(6)')=='6 · Green meadow'
            assert page.evaluate('dirtyCount()')==1
            page.evaluate('saveAll()')
            stored=Path(project)/'.lexeditor-world-names.json'
            assert json.loads(stored.read_text())=={'6':'Green meadow'}
            assert not list(Path(project).rglob('wmsetus.obj'))
            page.evaluate("async()=>{await reloadEditable();render()}")
            assert heading.input_value()=='Green meadow'
            assert page.evaluate('dirtyCount()')==0
            output=Path(tempfile.gettempdir())/'lexeditor-dev'/'ground-names.png'
            output.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(output))
            heading.fill('')
            heading.press('Tab')
            page.evaluate('saveAll()')
            assert json.loads(stored.read_text())=={}
            page.evaluate("async()=>{await reloadEditable();render()}")
            assert heading.input_value()==original
            assert not errors,errors
            browser.close()
    print('Ground names save/reload/reset with linked labels and no game binary writes.')


if __name__=='__main__':
    main()
