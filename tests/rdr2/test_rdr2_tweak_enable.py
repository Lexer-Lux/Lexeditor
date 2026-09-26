"""Disabling a tweak locks its settings without changing their saved values."""
import ast
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_effect_names_require_observed_symbols():
    tree = ast.parse((ROOT / 'plugins/rdr2/server.py').read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in ('effect_label_map', 'joaat')]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<effect names>', 'exec'), namespace)
    hash_id = namespace['joaat']('EFFECT_HEALTH')
    resolve = namespace['effect_label_map']
    assert resolve([f'0x{hash_id:08X}']) == {}
    assert resolve(['EFFECT_HEALTH', f'0x{hash_id:08X}']) == {hash_id: 'EFFECT_HEALTH'}
    assert resolve(['EFFECT_HEALTH', 'effect_health']) == {}


def test_header_switch_preserves_values_and_locks_only_its_tweak():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1100, 'height': 800})
            page.set_content('<head><base href="http://127.0.0.1:9/"></head><main id="main"></main>')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(content='''
              const el=LexeditorUI.el;
              const state={settingEdits:{},settings:{sections:[
                {name:'Minimap',settings:[{key:'Enabled',value:'1'},{key:'Radius',value:'25'}]},
                {name:'OtherTweak',settings:[{key:'Enabled',value:'1'},{key:'Amount',value:'8'}]}
              ]}};
              const isRO=()=>false,refreshGlobalSave=()=>{};
              const fieldHelp=text=>LexeditorUI.helpButton(text);
            ''' + (ROOT / 'plugins/rdr2/tweaks.js').read_text(encoding='utf-8'))
            page.evaluate('''() => {
              document.querySelector('main').append(LexeditorUI.settingsColumns(buildSettingsCategories().map(renderSettingCategory)));
              refreshSettingAvailability();
            }''')
            switch = page.get_by_role('checkbox', name='Enable Minimap', exact=True)
            assert switch.locator('xpath=ancestor::h2').count() == 1
            switch.uncheck()
            assert page.get_by_role('spinbutton', name='Radius', exact=True).is_disabled()
            assert page.get_by_role('spinbutton', name='Amount', exact=True).is_enabled()
            assert page.get_by_role('spinbutton', name='Radius', exact=True).input_value() == '25'
            assert page.evaluate('state.settingEdits') == {'Minimap|Enabled': '0'}
            shots = os.environ.get('LEXEDITOR_TEST_SHOTS')
            if shots:
                page.screenshot(path=str(Path(shots) / 'rdr2-tweak-switch.png'))
            switch.check()
            assert page.get_by_role('spinbutton', name='Radius', exact=True).is_enabled()
            assert page.evaluate('state.settingEdits') == {}
        finally:
            browser.close()
