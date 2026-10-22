"""Hover cards and help bubbles die with their anchor.

Removing an element fires no mouseleave, so tab switches, record
selects and re-renders orphaned their cards: a help text from one tab
and a preview image from another sat on screen until Escape. An anchor
leaving the document now closes its card.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  document.querySelector('main').replaceChildren(
    U.detailField({label: 'Model', property: 'model',
      control: U.hoverable({content: 'WP_A_1504', targetType: 'ds1-asset',
        targetId: 'c1202', targetLabel: 'model in Models',
        preview: () => U.el('img', {src: 'icon.png', alt: ''})})}),
    U.detailField({label: 'Kind', property: 'kind',
      help: U.infoHelp('Many textures packed into a whole file.'),
      control: U.el('input', {value: 'archive'})}));
}"""


def mount(page):
    framework(page)
    mount_shell(page, True)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def test_hover_preview_dies_with_its_anchor(page):
    mount(page)
    page.locator('.lex-hoverable').hover()
    page.locator('.lex-hover-preview').wait_for()
    page.evaluate("document.querySelector('main').replaceChildren()")
    page.wait_for_timeout(300)
    assert page.locator('.lex-hover-preview').count() == 0


def test_help_bubble_dies_with_its_marker(page):
    mount(page)
    page.locator('.lex-info-help').hover()
    page.locator('.lex-help-popover').wait_for()
    page.evaluate("document.querySelector('main').replaceChildren()")
    page.wait_for_timeout(300)
    assert page.locator('.lex-help-popover').count() == 0
