"""A settings page with one very long group lays out quickly and keeps order.

Handed back by the FF7R lane: a card page of about a thousand controls, most
of them one 168-record group, froze the window in one 14-26 s task. Every
split of that group restarted pagination and re-measured every card, and
joining the thirty pieces back moved each row once per later piece.
"""
from test_shared_ui_feedback import page, framework

BUILD = '''() => {
  const U = LexeditorUI;
  const field = (i, j) => U.detailField({label: `Property ${i}.${j}`, showType: true,
    control: j % 2 ? U.el('input', {type: 'checkbox', checked: !!(i % 2)})
                   : U.el('input', {type: 'number', value: i * j, min: 0, max: 999})});
  const group = (name, records, props) => U.detailSection({title: name,
    body: Array.from({length: records}, (_, i) => U.detailSection({title: '#' + i,
      body: Array.from({length: props}, (_, j) => field(i, j))}))});
  window.__long = [];
  new PerformanceObserver(list => list.getEntries().forEach(entry => window.__long.push(entry.duration)))
    .observe({type: 'longtask'});
  document.querySelector('main').append(U.stack(U.settingsColumns(
    [group('BIG GROUP', 168, 6), group('SMALL', 3, 5)], {})));
}'''

ORDER = '''() => [...document.querySelectorAll('.lex-tweaks-paged .lex-detail-field-label-text')]
  .map(label => label.textContent)'''


def test_long_group_settles_quickly_and_rejoins_in_order(page):
    page.set_viewport_size({'width': 1600, 'height': 900})
    framework(page)
    page.evaluate("document.querySelector('main').style.height = '860px'")
    page.evaluate(BUILD)
    page.wait_for_timeout(4000)
    longest = max(page.evaluate('window.__long') or [0])
    assert longest < 5000, f'one task blocked the window for {longest:.0f} ms'
    pages = page.evaluate("document.querySelector('.lex-tweaks-paged').lexPaging().starts.length")
    assert pages > 5, pages

    def every_label():
        names = []
        for _page in range(page.evaluate("document.querySelector('.lex-tweaks-paged').lexPaging().starts.length")):
            names.extend(page.evaluate('''() => [...document.querySelectorAll(
              '.lex-tweaks-paged .lex-tweak-column .lex-detail-field-label-text')].map(label => label.textContent)'''))
            button = page.locator('.lex-tweaks-pages button[aria-label="Next page"]')
            if button.count() and not button.is_disabled():
                button.click()
                page.wait_for_timeout(50)
        return names

    expected = [f'Property {i}.{j}' for i in range(168) for j in range(6)] + \
        [f'Property {i}.{j}' for i in range(3) for j in range(5)]
    assert every_label() == expected
    # A different window height joins every piece back and cuts again.
    page.set_viewport_size({'width': 1300, 'height': 700})
    page.evaluate("document.querySelector('main').style.height = '660px'")
    page.wait_for_timeout(2500)
    page.evaluate("document.querySelector('.lex-tweaks-paged').refreshPages()")
    page.wait_for_timeout(500)
    assert every_label() == expected
