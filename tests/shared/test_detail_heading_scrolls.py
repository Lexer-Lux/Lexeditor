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
      // Sections flow into paged columns by default; a panel that opts out
      // of that flow is the one that scrolls, heading and all.
      main.append(U.detailPanel({title: 'Long record', attrs: {id: 'long'}, paginate: false,
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

def test_unpaged_tab_scroller_survives_late_content_growth(page):
    """An unpaged tab keeps scrolling after its content grows past the fit.

    The paginate fit writes inline overflow-y hidden when a tab fits, and
    nothing re-fits when content grows in place afterwards. The stale
    inline style used to clip the late fields with no scrollbar and a dead
    wheel; the shared scroller rule now keeps overflow-y auto.
    """
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:12px;height:500px';
      const fields = (n, prefix) => Array.from({length: n}, (_, i) => U.detailField({label: prefix + i,
        control: U.el('input', {type: 'number', value: i})}));
      window.extraFields = () => fields(40, 'Late ');
      main.append(U.detailPanel({title: 'Tabbed record', attrs: {id: 'tabbed'},
        body: [U.tabbedPanel({tabs: [{id: 'a', label: 'A'}], active: 'a',
          paginate: {unpaged: true}, content: () => fields(4, 'Field ')})]}));
    }''')
    page.wait_for_timeout(400)
    state = page.evaluate('''() => {
      const scroller = document.querySelector('#tabbed .lex-tweaks-scroll');
      return {found: !!scroller,
        overflows: scroller ? scroller.scrollHeight > scroller.clientHeight + 1 : None};
    }''')
    assert state == {'found': True, 'overflows': False}, state
    page.evaluate('''() => {
      const scroller = document.querySelector('#tabbed .lex-tweaks-scroll');
      const host = scroller.querySelector('.lex-detail-field').parentElement;
      host.append(...window.extraFields());
    }''')
    page.wait_for_timeout(300)
    grown = page.evaluate('''() => {
      const scroller = document.querySelector('#tabbed .lex-tweaks-scroll');
      return {computed: getComputedStyle(scroller).overflowY,
        overflows: scroller.scrollHeight > scroller.clientHeight + 1};
    }''')
    assert grown['overflows'], grown
    assert grown['computed'] == 'auto', grown
    box = page.locator('#tabbed .lex-tweaks-scroll').bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(300)
    top = page.evaluate("() => document.querySelector('#tabbed .lex-tweaks-scroll').scrollTop")
    assert top > 0, top
    page.evaluate("() => { const s = document.querySelector('#tabbed .lex-tweaks-scroll'); s.scrollTop = s.scrollHeight; }")
    page.wait_for_timeout(200)
    visible = page.evaluate('''() => {
      const s = document.querySelector('#tabbed .lex-tweaks-scroll');
      const fields = [...s.querySelectorAll('.lex-detail-field')];
      const last = fields[fields.length - 1].getBoundingClientRect();
      return {lastBottom: last.bottom, boxBottom: s.getBoundingClientRect().bottom};
    }''')
    assert visible['lastBottom'] <= visible['boxBottom'] + 1, visible
