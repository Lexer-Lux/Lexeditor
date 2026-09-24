"""G9: the loading-screen setting is titled 'Loading screen transition' with no description."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))
SETTINGS = dict(BASE, developerMode=True, developerAuthorized=True,
                developerLogin='Lexer-Lux', viewPreferences={},
                defaultValues=dict(BASE),
                updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])


def test_loading_screen_transition_label_has_no_description():
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
            page.wait_for_selector('.lex-global-setting input')
            assert page.get_by_text('Loading screen minimum').count() == 0
            label = page.locator('label[for="lex-default-loadingTransitionMinimumSeconds"]')
            assert label.inner_text() == 'Loading screen transition'
            card = label.locator('xpath=ancestor::section[contains(@class,"lex-global-setting")][1]')
            assert card.locator('p').count() == 0
        finally:
            browser.close()
