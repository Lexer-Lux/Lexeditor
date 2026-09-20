"""Compare two shared stylesheets on the same live plugin pages.

Usage: python tools/visual_css_compare.py OLD_CSS OUTPUT [plugin ...]
The current framework.css is the new stylesheet. No data is saved. Each
capture uses the same DOM and data for both styles, which avoids differences
caused by two separate plugin loads. Screenshots and computed styles are kept.
"""
from pathlib import Path
import sys

import visual_snapshot as snapshot


def main():
    old_path, output, *plugins = sys.argv[1:]
    for arg in list(plugins):
        if arg.startswith('--tabs='):
            snapshot.TABS_FILTER=set(arg.split('=',1)[1].split(','))
            plugins.remove(arg)
    out = Path(output).resolve()
    before, after = out / 'before', out / 'after'
    before.mkdir(parents=True, exist_ok=True)
    after.mkdir(parents=True, exist_ok=True)

    def css(path):
        # The linked sheet resolves fonts under /shared; an inline sheet
        # resolves them under the page unless these URLs are made absolute.
        return Path(path).read_text(encoding='utf-8').replace('url("assets/', 'url("/shared/assets/')

    old_css = css(old_path)
    new_css = css(snapshot.ROOT / 'ui/framework.css')
    original_capture = snapshot.capture
    snapshot.STYLES = True

    def capture(page, unused, name):
        for text, folder in [(old_css, before), (new_css, after)]:
            page.evaluate('''text => {
                const link = document.querySelector('link[href*="/shared/framework.css"]');
                let style = document.getElementById('lex-css-comparison');
                if (!style) {
                    style = document.createElement('style');
                    style.id = 'lex-css-comparison';
                    link.before(style);
                    link.disabled = true;
                }
                style.textContent = text;
                window.dispatchEvent(new Event('resize'));
            }''', text)
            page.evaluate('document.fonts.ready')
            snapshot.settle(page, 800)
            original_capture(page, folder, name)

    snapshot.capture = capture
    available = snapshot.discover_plugins()
    api = snapshot.HostApi(available)
    notes = []
    try:
        with snapshot.sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for plugin in plugins or sorted(available):
                    print('comparing', plugin, flush=True)
                    notes += snapshot.shoot_plugin(browser, api, plugin, out)
            finally:
                browser.close()
    finally:
        api.stop()
        (out / 'notes.txt').write_text('\n'.join(notes), encoding='utf-8')
    print('\n'.join(notes) or 'no capture errors')
    return bool(notes)


if __name__ == '__main__':
    raise SystemExit(main())
