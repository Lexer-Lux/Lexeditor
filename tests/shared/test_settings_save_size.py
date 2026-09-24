"""G10: the Settings menu save button is at least double its old 38x36 size."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))
SETTINGS = dict(BASE, developerMode=True, developerAuthorized=True,
                developerLogin='Lexer-Lux', viewPreferences={},
                defaultValues=dict(BASE),
                updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])


def test_settings_save_button_doubled():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('http://fixture/**', lambda r: r.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate(f'window.pywebview={{api:{{lexeditor_settings:async()=>({json.dumps(SETTINGS)})}}}}')
            page.evaluate('LexeditorUI.openSettings()')
            page.wait_for_selector('.lex-settings-save-control')
            box = page.locator('.lex-global-settings .lex-settings-save-control').bounding_box()
            assert box['width'] >= 76, box
            assert box['height'] >= 72, box
            icon = page.locator('.lex-global-settings .lex-settings-save-control svg').bounding_box()
            assert icon['width'] >= 44, icon
            assert icon['height'] >= 44, icon
        finally:
            browser.close()
