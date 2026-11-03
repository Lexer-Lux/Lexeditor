"""RDR2 mod-contents specs compare record identities, not row objects."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def run(browser_path=None):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, **(
            {'executable_path': browser_path} if browser_path else {}))
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 800})
            page.set_default_timeout(5000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/*', lambda route: route.abort())
            page.route('http://fixture/', lambda route: route.fulfill(
                content_type='text/html', body='<main id="main"></main>'))
            page.goto('http://fixture/')
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(path=str(ROOT / 'plugins/rdr2/core.js'))
            page.evaluate('''() => {
              const assert = (ok, what) => { if (!ok) throw new Error('miss: ' + what); };
              state.config = {datasets: {mine: {readonly: false}, vanilla: {readonly: true}}};
              state.ds = 'mine';
              state.modOnly = false;
              // First segments name records; later ones name fields within them.
              assert([...touchedRecords([{'APPLE|buy': 1}])][0] === 'APPLE', 'segment 0');
              assert([...touchedRecords([{'APPLE|buy': 1}], [], 1)][0] === 'buy', 'segment 1');
              assert([...touchedRecords([], [['A', 'B']])].join(',') === 'A,B', 'sets');
              // Object rows compare by record identity, the bug that emptied
              // the Items and Crafting lists as soon as the toggle went on.
              let reset = 0, redraw = 0;
              const spec = modOnlySpec(touchedRecords([{APPLE: 1}]),
                () => reset++, () => redraw++, row => row.key);
              assert(spec.available === true && spec.value === false, 'spec shape');
              assert(spec.changed({key: 'APPLE'}) === true, 'touched object row');
              assert(spec.changed({key: 'PEAR'}) === false, 'untouched object row');
              // Callers without their own shape use key, id or name; string
              // rows (weapon names) compare as themselves.
              const plain = modOnlySpec(touchedRecords([{A: 1}]), null, () => {});
              assert(plain.changed({key: 'A'}) === true, 'default key');
              assert(plain.changed({id: 'A'}) === true, 'default id');
              assert(plain.changed({name: 'A'}) === true, 'default name');
              assert(plain.changed({other: 'A'}) === false, 'unknown shape');
              assert(plain.changed('A') === true, 'string row');
              spec.change(true);
              assert(state.modOnly === true && reset === 1 && redraw === 1, 'change');
              plain.change(false);
              assert(state.modOnly === false, 'null reset tolerated');
              state.ds = 'vanilla';
              assert(modOnlySpec(new Set(), null, () => {}).available === false, 'read-only');
            }''')
            assert not errors, errors
            print('PASS rdr2 mod-only spec identities, defaults and toggle')
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser')
    args = parser.parse_args()
    run(args.browser)
