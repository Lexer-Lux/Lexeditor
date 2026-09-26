"""The shared Add action stages and saves a new key in an empty source file."""
from pathlib import Path
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.service_session import LocalPluginSession


def test_localization_add_from_empty_file():
    with tempfile.TemporaryDirectory(prefix='lex-terraria-add-') as directory:
        root=Path(directory)
        project=root/'ExampleMod'
        (project/'Localization').mkdir(parents=True)
        (project/'build.txt').write_text('displayName = Example Mod\nauthor = Fixture\nversion = 1.0\n')
        target=project/'Localization/en-US.hjson'
        target.write_text('{}\n')
        session=LocalPluginSession(module='plugins.terraria.server',plugin_id='terraria',
            app_root=ROOT,check=lambda:[],extra_env={
                'LEXEDITOR_TERRARIA_PROJECT':str(project),
                'LEXEDITOR_TERRARIA_ROOT':str(root/'install'),
                'LEXEDITOR_TERRARIA_SAVE_ROOT':str(root/'saves'),
                'LEXEDITOR_MOD_READ_ONLY':'0','LEXEDITOR_NO_MOD':'0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser=play.chromium.launch(headless=True)
                try:
                    page=browser.new_page(viewport={'width':1400,'height':900})
                    page.goto(session.url)
                    page.wait_for_function('locCurrent !== null')
                    page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                    page.evaluate('navigate("localization")')
                    page.get_by_role('button',name='Add localization key',exact=True).click()
                    key=page.get_by_label('New localization key',exact=True)
                    assert key.evaluate('e=>e===document.activeElement')
                    if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                        page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'terraria-add-key.png'))
                    key.fill('Mods.ExampleMod.Custom.Greeting')
                    page.get_by_label('New localization value',exact=True).fill('Hello player')
                    page.get_by_role('button',name='Add key',exact=True).click()
                    assert target.read_text()=='{}\n'
                    page.locator('#global-save').click()
                    page.wait_for_function('document.querySelector("#global-save").disabled')
                    assert 'Hello player' in target.read_text()
                    page.reload()
                    page.wait_for_function('locCurrent?.entries?.some(e=>e.key==="Mods.ExampleMod.Custom.Greeting" && e.value==="Hello player")')
                finally:
                    browser.close()
        finally:
            session.stop()
