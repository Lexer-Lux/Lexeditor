"""Localization Add saves/reopens keys across source layouts without replacing data."""
from pathlib import Path
import os
import sys
import tempfile
import pytest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.service_session import LocalPluginSession


@pytest.mark.parametrize('filename,original,key,value', [
    ('en-US.hjson', b'{}\n', 'Mods.ExampleMod.Custom.Greeting', 'Hello player'),
    ('en-US.hjson', b'\xef\xbb\xbf# keep this comment\r\nMods: {\r\n ExampleMod: {\r\n  Original: Original text\r\n  Unknown: 42\r\n }\r\n}\r\n', 'Mods.ExampleMod.Custom.Greeting', 'Hello "player" #1'),
    ('fr-FR_Mods.ExampleMod.hjson', b'# preserve prefixed source\nOriginal: Bonjour\n', 'Custom.Greeting', 'Bonjour joueur é'),
])
def test_localization_add_save_reopen_preserves_source(filename, original, key, value):
    with tempfile.TemporaryDirectory(prefix='lex-terraria-add-') as directory:
        root=Path(directory)
        project=root/'ExampleMod'
        (project/'Localization').mkdir(parents=True)
        (project/'build.txt').write_text('displayName = Example Mod\nauthor = Fixture\nversion = 1.0\n')
        target=project/'Localization'/filename
        target.write_bytes(original)
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
                    key_control=page.get_by_label('New localization key',exact=True)
                    assert key_control.evaluate('e=>e===document.activeElement')
                    if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                        page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'terraria-add-key.png'))
                    key_control.fill(key)
                    page.get_by_label('New localization value',exact=True).fill(value)
                    page.get_by_role('button',name='Add key',exact=True).click()
                    assert target.read_bytes()==original
                    # A key added in this mod carries the shared created-record pen.
                    assert page.locator('.lex-record-source').count()==1
                    page.locator('#global-save').click()
                    # Save disables its button when it starts, before the file is
                    # written, so wait for the file itself.
                    for _ in range(100):
                        if value.split(' ')[0] in target.read_text(encoding='utf-8-sig') and target.read_bytes()!=original:
                            break
                        page.wait_for_timeout(50)
                    assert target.read_bytes()!=original
                    from plugins.terraria.localization import parse_localization_text
                    prefix='Mods.ExampleMod' if filename.startswith('fr-FR_') else ''
                    effective=f'{prefix}.{key}' if prefix else key
                    document=parse_localization_text(target.read_text(encoding='utf-8-sig'),prefix)
                    assert [(e.key,e.value) for e in document.entries if e.key==effective]==[(effective,value)]
                    if original.startswith(b'\xef\xbb\xbf'):assert target.read_bytes().startswith(b'\xef\xbb\xbf')
                    if b'Unknown: 42' in original:assert b'  Unknown: 42\r\n' in target.read_bytes()
                    for line in original.splitlines():
                        if b'comment' in line or b'Original:' in line or b'prefixed source' in line:assert line in target.read_bytes()
                    page.reload()
                    page.wait_for_function('([key,value])=>locCurrent?.entries?.some(e=>e.key===key && e.value===value)',arg=[effective,value])
                    page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                    page.evaluate('navigate("localization")')
                    page.locator('.lex-column-list-row').filter(has_text=effective).click()
                    expect(page.get_by_label('Localization value',exact=True)).to_have_value(value)
                    if os.environ.get('LEXEDITOR_TEST_SHOTS'):
                        page.screenshot(path=str(Path(os.environ['LEXEDITOR_TEST_SHOTS'])/'terraria-reopened-key.png'))
                    # Duplicate Add leaves the original saved entry and bytes intact.
                    before=target.read_bytes()
                    page.get_by_role('button',name='Add localization key',exact=True).click()
                    page.get_by_label('New localization key',exact=True).fill(key)
                    page.get_by_label('New localization value',exact=True).fill('Should not replace')
                    page.get_by_role('button',name='Add key',exact=True).click()
                    expect(page.get_by_text(f'Localization key already exists: {effective}',exact=True)).to_be_visible()
                    assert target.read_bytes()==before
                    assert page.evaluate('locCurrent.entries.filter(e=>e.isNew).length')==0
                finally:
                    browser.close()
        finally:
            session.stop()
