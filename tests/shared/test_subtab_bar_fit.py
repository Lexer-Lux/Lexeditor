"""A sub-tab bar's names share one size; long names get the room they need.

todo: "Keep panel subtab names readable in narrow columns, including Field's
twelve-tab panel." Fitted one at a time inside equal lanes, "Camera Ranges"
shrank to 8.66px beside a 16px "Tile". The bar is now fitted as a whole.
"""
from test_shared_ui_feedback import page, framework

NAMES = ["Camera", "Camera Ranges", "Dialogue", "Doors", "Exits", "Field Scripts",
         "Movie Camera", "Tile", "Triggers", "Walkmesh", "Misc."]


def mount(page, width):
    page.evaluate('''([names, width]) => {
      const U = LexeditorUI, host = U.el('div', {style: `width:${width}px`});
      document.querySelector('main').replaceChildren(host);
      host.append(U.tabbedPanel({label: 'Field detail', active: 'a0',
        tabs: names.map((name, index) => ({id: 'a' + index, label: name})),
        content: U.el('div', {}, 'content')}));
    }''', [NAMES, width])
    page.wait_for_timeout(600)
    return page.evaluate('''() => {
      const labels = [...document.querySelectorAll('.lex-tabbed-panel-tabs .lex-tab-label-text')];
      const bar = document.querySelector('.lex-tabbed-panel-tabs');
      return {names: labels.map(l => l.textContent), sizes: labels.map(l => getComputedStyle(l).fontSize),
              widths: labels.map(l => Math.round(l.closest('button').getBoundingClientRect().width)),
              clipped: labels.filter(l => l.scrollWidth > l.clientWidth + 1).map(l => l.textContent),
              columns: bar.style.gridTemplateColumns}
    }''')


def test_narrow_bar_uses_one_size_and_gives_long_names_room(page):
    framework(page)
    result = mount(page, 900)
    assert len(set(result["sizes"])) == 1, result["sizes"]
    assert not result["clipped"], result
    widths = dict(zip(result["names"], result["widths"]))
    assert widths["Camera Ranges"] > widths["Tile"] * 1.5, widths


def test_roomy_bar_keeps_equal_lanes(page):
    framework(page)
    page.set_viewport_size({"width": 3200, "height": 800})
    result = mount(page, 3000)
    assert result["columns"] == "", result
    assert max(result["widths"]) - min(result["widths"]) <= 2, result["widths"]
