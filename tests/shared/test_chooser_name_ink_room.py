"""A game name on the main menu keeps room for its shadow on every side.

Lexer: "the right side of the FF8 and FF9 game titles on main menu are cut off
when i hover them. the very very right edge". The clamp box that ellipsizes a
long name clips, and it was exactly as wide as the glyphs, so the shadow to
the right of the last letter was cut in a hard line.
"""
import json

from playwright.sync_api import sync_playwright

from test_chooser_cover_treatment import BASE, COVER, base, stub_script  # noqa: F401


def test_hovered_names_leave_room_past_the_last_letter(base):
    settings = dict(BASE, viewPreferences={}, defaultValues=dict(BASE))
    plugins = [{'id': key, 'name': name, 'status': 'added', 'canOpen': True, 'resident': False,
                'dirtyCount': 0, 'problems': [], 'statusText': '',
                'coverArt': {'state': 'ready', 'uri': COVER}}
               for key, name in [('ff8', 'Final Fantasy VIII'), ('ff9', 'Final Fantasy IX'),
                                 ('warband', 'Mount & Blade: Warband')]]
    stub = stub_script(settings)
    stub = stub[:stub.index('plugins:async()=>(')] + f'plugins:async()=>({json.dumps(plugins)}),' + \
        stub[stub.index('loading_quote:'):]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            page.add_init_script(stub)
            page.goto(base + '/ui/chooser.html')
            page.evaluate("dispatchEvent(new Event('pywebviewready'))")
            page.wait_for_selector('.game', timeout=8000)
            page.wait_for_timeout(800)
            for card in page.locator('.game').all():
                card.hover()
                page.wait_for_timeout(250)
                room = card.locator('.game-name-text').evaluate('''text => {
                  const range = document.createRange();
                  range.selectNodeContents(text);
                  const box = text.getBoundingClientRect();
                  const lines = [...range.getClientRects()];
                  return {right: box.right - Math.max(...lines.map(line => line.right)),
                          left: Math.min(...lines.map(line => line.left)) - box.left,
                          text: text.textContent};
                }''')
                assert room['right'] >= 3 and room['left'] >= 3, room
        finally:
            browser.close()
