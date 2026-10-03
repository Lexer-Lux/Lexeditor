"""Every record pane lays its sections out in columns, not only the ones that ask.

The column flow used to be a per-call `paginate` flag: DS1's Attacks pane had
it, its Enemies pane (sections inside a tabbed panel) did not, and stayed one
column however wide the window was.
"""
from test_shared_ui_feedback import framework, page

BUILD = """(kind) => {
  const {detailPanel, tabbedPanel, detailSection, detailField, el} = LexeditorUI;
  const section = title => detailSection({title, body: [1, 2, 3].map(n =>
    detailField({label: `${title} ${n}`, control: el('input', {type: 'number', value: n})}))});
  const sections = ['Alpha', 'Beta', 'Gamma'].map(section);
  const panel = kind === 'tabbed'
    ? detailPanel({title: 'Record', body: [tabbedPanel({tabs: [{id: 'a', label: 'A'}], active: 'a', content: sections})]})
    : kind === 'single' ? detailPanel({title: 'Record', paginate: false, body: sections})
    : detailPanel({title: 'Record', body: sections});
  const main = document.querySelector('#main') || document.body.appendChild(el('main', {id: 'main'}));
  main.style.cssText = 'display:flex;height:600px;width:1500px';
  main.replaceChildren(panel);
}"""

COLUMNS = """() => new Set([...document.querySelectorAll('.lex-detail-section-title')]
  .filter(node => node.offsetParent).map(node => Math.round(node.getBoundingClientRect().left))).size"""


def columns(page, kind):
    page.set_viewport_size({"width": 1600, "height": 800})
    framework(page)
    page.evaluate(BUILD, kind)
    page.wait_for_timeout(300)
    return page.evaluate(COLUMNS)


def test_a_panel_of_sections_flows_into_columns_by_default(page):
    assert columns(page, "plain") == 3


def test_sections_inside_a_tabbed_panel_flow_too(page):
    assert columns(page, "tabbed") == 3


def test_paginate_false_keeps_one_column(page):
    assert columns(page, "single") == 1
