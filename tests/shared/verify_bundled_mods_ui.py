"""Rendered shared bundle selector, including real host transactions and reload."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from test_bundled_mods import fixture, host_fixture
from types import SimpleNamespace
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    with tempfile.TemporaryDirectory(prefix='lexeditor-bundle-ui-') as temporary:
        manager = fixture(Path(temporary))
        host = host_fixture(manager)
        bundle = str(manager.library / 'Collection')
        host._projects = SimpleNamespace(snapshot=lambda _: {'current': bundle, 'canCreate': True,
            'projects': [{'path': bundle, 'name': 'Collection', 'valid': True, 'current': True}]})
        errors = []
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': 1100, 'height': 850})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('http://fixture.test/**', lambda route: route.fulfill(body='<html><body></body></html>', content_type='text/html'))
                page.goto('http://fixture.test/')
                page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
                page.expose_binding('hostCall', lambda source, name, args: getattr(host, name)(*args))
                page.evaluate('''() => {window.pywebview={api:new Proxy({}, {
                    get:(_,name)=>(...args)=>window.hostCall(name,args)})};}''')
                source = (ROOT / 'ui/framework.js').read_text('utf-8')
                page.add_script_tag(content=source.replace('window.LexeditorUI = {', 'window.LexeditorUI = {openModLibrary,mountProjectControl,'))
                page.evaluate("LexeditorUI.mountProjectControl({plugin:{id:'test',name:'Test'}},document.body)")
                page.get_by_role('button', name='Active mod project').click()
                selector_help = page.locator('.lex-project-menu .lex-info-help')
                assert 'Damage tweak' in selector_help.get_attribute('aria-label')
                selector_help.hover()
                page.get_by_text('This mod contains components attached', exact=False).wait_for(state='visible')
                page.wait_for_timeout(250)
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(output.with_name(output.stem + '-selector.png')))
                page.get_by_role('button', name='Active mod project').click()
                def open_library():
                    page.evaluate("LexeditorUI.openModLibrary('test')")
                    page.get_by_role('checkbox', name='Combat', exact=True).wait_for()
                def apply():
                    page.get_by_role('button', name='Apply enabled mods').click()
                    page.get_by_text('Active mod files updated.', exact=False).wait_for()
                open_library()
                for _ in range(2):
                    page.get_by_role('checkbox', name='Combat', exact=True).check()
                    assert page.get_by_role('checkbox', name='Damage tweak').is_checked()
                    apply()
                    assert manager.tweaks['damage'].read(manager.game)
                    page.get_by_role('checkbox', name='Damage tweak').uncheck()
                    assert not page.get_by_role('checkbox', name='Combat', exact=True).is_checked()
                    apply()
                    assert not manager.adapter.active_mod_ids(manager.game)
                page.get_by_role('checkbox', name='Cost tweak').check()
                assert page.get_by_role('checkbox', name='Balance', exact=True).is_checked()
                assert page.get_by_role('checkbox', name='Damage tweak').is_checked()
                apply()
                page.get_by_role('button', name='Close', exact=True).click()
                open_library()
                assert page.get_by_role('checkbox', name='Balance', exact=True).is_checked()
                assert page.get_by_role('checkbox', name='Cost tweak').is_checked()
                help_marker = page.get_by_role('dialog', name='Mod library').locator('.lex-info-help').first
                help_marker.hover()
                page.get_by_text('Attached tweaks:', exact=False).first.wait_for(state='visible')
                page.wait_for_timeout(250)
                if output:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(output))
                manager.adapter.fail = True
                page.get_by_role('checkbox', name='Balance', exact=True).uncheck()
                page.get_by_role('button', name='Apply enabled mods').click()
                page.get_by_text('deployment failed', exact=False).wait_for()
                assert page.get_by_role('checkbox', name='Balance', exact=True).is_checked()
                assert page.get_by_role('checkbox', name='Cost tweak').is_checked()
                assert manager.state()['components'] == ['Collection/balance']
                assert not errors, errors
                print(json.dumps({'repeatedBothDirections': True, 'reopenedSelection': True,
                                  'rollbackRestoredControls': True, 'browserErrors': errors}))
            finally:
                browser.close()


if __name__ == '__main__':
    main()
