"""Maps help must be reachable without selecting a different tab."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui

def main():
    source = plugin_ui('ff8')
    world = re.search(r'const tabsData=(\[.*?\]),wrap=', source).group(1)
    maps = re.search(r'className:"ff8-maps-tabs",tabs:(\[.*?\]),active:', source).group(1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1536, 'height': 900})
        page.route('http://fixture/', lambda r: r.fulfill(body='<body data-lex-plugin="ff8"><main></main></body>', content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(content=(ROOT / 'ui/framework.css').read_text(encoding='utf-8'))
        page.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
        page.add_script_tag(content=(ROOT / 'ui/framework.js').read_text(encoding='utf-8'))
        page.evaluate("""groups => {
            window.changes = 0;
            for (const tabs of groups) document.querySelector('main').append(
                LexeditorUI.subtabBar({tabs, active: tabs[0].id, change: () => window.changes++}));
        }""", page.evaluate('[' + maps + ',' + world + ']'))
        markers = page.locator('.lex-subtab-bar .lex-info-help')
        assert markers.count() == 11
        assert page.locator('button button').count() == 0
        for i in range(markers.count()):
            marker = markers.nth(i)
            marker.focus()
            expected = marker.get_attribute('aria-label')
            assert len(expected) > 70
            assert page.get_by_role('tooltip').inner_text() == expected
            marker.press('Enter')
            marker.click()
            assert page.evaluate('window.changes') == 0
            page.keyboard.press('Escape')
        page.get_by_role('tab').nth(1).click(position={'x': 10, 'y': 10})
        assert page.evaluate('window.changes') == 1
        browser.close()
    print('All 11 Maps tabs have usable help; keyboard and click help do not switch tabs.')

if __name__ == '__main__':
    main()
