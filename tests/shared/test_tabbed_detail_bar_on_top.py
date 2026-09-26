"""A tabbed detail panel carries its tab bar along its top edge.

Lexer, on FF8's Magic: "if a details panel is made tabbed, then the tab bar
should run along its top, like with any other tabbed panel".
"""
from test_shared_ui_feedback import page, framework


def test_tab_bar_sits_above_the_record_heading(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.height = '500px';
      main.append(U.detailPanel({title: 'Aero', attrs: {style: 'height:480px'}, body: [
        U.tabbedPanel({tabs: [{id: 'attack', label: 'Attack data'}, {id: 'junction', label: 'Junction'}],
          active: 'attack', content: id => U.el('p', {}, 'Content of ' + id)})]}));
    }''')
    page.wait_for_timeout(200)
    rows = page.evaluate('''() => {
      const panel = document.querySelector('.lex-detail-panel'), top = panel.getBoundingClientRect().top;
      const at = selector => panel.querySelector(selector).getBoundingClientRect();
      const bar = at('.lex-tabbed-panel-tabs'), heading = at('.lex-detail-panel-heading'), content = at('.lex-tabbed-panel-content');
      return {bar: bar.top - top, heading: heading.top - top, headingHeight: heading.height,
              content: content.top - top, contentBottom: panel.getBoundingClientRect().bottom - content.bottom};
    }''')
    assert rows['bar'] < 8, rows
    assert rows['heading'] >= rows['bar'] and rows['content'] > rows['heading'], rows
    assert rows['headingHeight'] > 30, 'the heading keeps its own height'
    assert rows['contentBottom'] < 8, 'the tab content fills the rest of the panel'
