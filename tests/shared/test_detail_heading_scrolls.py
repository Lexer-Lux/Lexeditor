"""A detail panel's heading scrolls with the record, and the margins match.

Lexer: "the header on the details panel shouldn't actually be independent of
the scroll wheel. the scroll wheel should pass through it like everything
else, and the scrolling should move it. IG take the amount of space put on
the right side to make room for it, and make that exact amount the amount of
left-side margin on the panel". A panel whose body fills it and scrolls
inside itself (here, a tabbed panel) keeps its heading in place.
"""
from test_shared_ui_feedback import page, framework


def test_heading_scrolls_away_and_gutters_match(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:12px;height:500px';
      const fields = n => Array.from({length: n}, (_, i) => U.detailField({label: 'Field ' + i,
        control: U.el('input', {type: 'number', value: i})}));
      main.append(U.detailPanel({title: 'Long record', attrs: {id: 'long'},
        body: [U.detailSection({title: 'DATA', body: fields(30)})]}));
      main.append(U.detailPanel({title: 'Tabbed record', attrs: {id: 'tabbed'},
        body: [U.tabbedPanel({tabs: [{id: 'a', label: 'A'}, {id: 'b', label: 'B'}], active: 'a',
          content: () => U.el('div', {}, ...fields(30))})]}));
    }''')
    page.wait_for_timeout(300)
    heading = page.locator('#long > .lex-detail-panel-heading')
    box = heading.bounding_box()
    page.mouse.move(box['x'] + box['width'] * .6, box['y'] + box['height'] / 2)
    page.mouse.wheel(0, 200)
    page.wait_for_timeout(300)
    after = page.evaluate('''() => {
      const panel = document.querySelector('#long'), body = panel.querySelector(':scope > .lex-detail-panel-body');
      const p = panel.getBoundingClientRect(), b = body.getBoundingClientRect();
      return {scrollTop: panel.scrollTop, headingTop: panel.querySelector(':scope > .lex-detail-panel-heading').getBoundingClientRect().top - p.top,
        left: b.left - p.left, right: p.right - b.right};
    }''')
    assert after['scrollTop'] > 100, after
    assert after['headingTop'] < -100, 'the heading moved with the record'
    assert abs(after['left'] - after['right']) <= 1, after

    tabbed = page.evaluate('''() => {
      const panel = document.querySelector('#tabbed');
      return {panelScrolls: panel.scrollHeight > panel.clientHeight + 1,
        body: getComputedStyle(panel.querySelector(':scope > .lex-detail-panel-body')).overflowY};
    }''')
    assert tabbed == {'panelScrolls': False, 'body': 'auto'}, tabbed
