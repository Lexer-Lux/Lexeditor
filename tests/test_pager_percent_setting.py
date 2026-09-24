"""G11: pagination bar height is a percentage of screen height, wired end to end."""
import json
from pathlib import Path

from test_shared_ui_feedback import page, framework
from core.settings_manager import SettingsStore

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))


def test_pager_percent_round_trip_and_clamp(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json', tmp_path / 'defaults.json')
    assert store.snapshot()['pagerBarHeightPercent'] == 6.0
    store.save('daily', pager_bar_height_percent=8.5)
    assert SettingsStore(store.path, store.defaults_path).snapshot()['pagerBarHeightPercent'] == 8.5
    store.save('daily', pager_bar_height_percent=99)
    assert store.snapshot()['pagerBarHeightPercent'] == 12.0
    store.save('daily', pager_bar_height_percent=-4)
    assert store.snapshot()['pagerBarHeightPercent'] == 3.0
    store.save_packaged_defaults({'pagerBarHeightPercent': 30})
    assert store.snapshot()['defaultValues']['pagerBarHeightPercent'] == 12.0


def test_pager_percent_control_and_var(page):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE),
                    updateCheckChoices=[{'value': 'monthly', 'label': 'Monthly'}])
    settings['pagerBarHeightPercent'] = 8
    page.evaluate(f'window.pywebview={{api:{{lexeditor_settings:async()=>({json.dumps(settings)})}}}}')
    framework(page)
    page.evaluate('LexeditorUI.openSettings()')
    page.wait_for_selector('#lex-pagerBarHeightPercent')
    control = page.locator('#lex-pagerBarHeightPercent')
    assert control.is_enabled()
    assert control.get_attribute('min') == '3'
    assert control.get_attribute('max') == '12'
    assert 'screen height' in page.locator('.lex-global-setting', has=control).inner_text()
    assert page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--lex-pager-bar-height').trim()") == '8vh'
    page.evaluate("document.body.append(LexeditorUI.element('div',{class:'lex-pager'}))")
    assert page.locator('.lex-pager').evaluate('n=>getComputedStyle(n).minHeight') == '64px'
