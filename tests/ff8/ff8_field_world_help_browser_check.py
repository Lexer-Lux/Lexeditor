"""Field and World help must be reachable without selecting a different tab."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui

def main():
    source = plugin_ui('ff8')
    world = re.search(r'const tabsData=(\[.*?\]),wrap=', source).group(1)
    field = re.search(r'const fieldDetailTabs=(\[.*?\]);', source).group(1)
    # Every subtab carries its own help, so the number of markers is the number
    # of tabs - counted from the arrays rather than pinned, because the tabs
    # move between screens (the encounter rules and groups now live on the
    # Encounters tab) and a pinned number says nothing about the rule.
    tabs = len(re.findall(r'\{id:', field)) + len(re.findall(r'\{id:', world))
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
        }""", page.evaluate('[' + field + ',' + world + ']'))
        markers = page.locator('.lex-subtab-bar .lex-info-help')
        assert markers.count() == tabs, (markers.count(), tabs)
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
    print('All 19 Field/World subtabs have usable help; keyboard and click help do not switch tabs.')

if __name__ == '__main__':
    main()
