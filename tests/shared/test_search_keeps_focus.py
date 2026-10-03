"""The search box keeps focus when its page rebuilds it after the keystroke.

Lexer: "Almost every time I type a letter into the search bar it loses
focus." DS1 filters, then loads the newly selected record and renders again;
that second, later rebuild replaced the box with nothing to restore focus.
"""
from test_shared_ui_feedback import framework, page

BUILD = """() => {
  window.query = '';
  const render = () => document.querySelector('main').replaceChildren(LexeditorUI.bottomSearch({
    key: 'records', label: 'Search records', value: query,
    change: value => { query = value; render(); setTimeout(render, 30); }}));
  render();
}"""


def test_typing_survives_a_late_rebuild(page):
    framework(page)
    page.evaluate(BUILD)
    box = page.get_by_role("searchbox", name="Search records")
    box.click()
    for letter in "rat":
        page.keyboard.type(letter)
        page.wait_for_timeout(80)
    assert page.evaluate("query") == "rat"
    assert page.evaluate("document.activeElement?.dataset.lexBottomSearch") == "records"
    assert page.evaluate("document.activeElement.selectionStart") == 3


def test_leaving_the_box_is_respected(page):
    framework(page)
    page.evaluate(BUILD)
    page.evaluate("document.body.append(LexeditorUI.el('button', {id: 'elsewhere'}, 'Elsewhere'))")
    page.get_by_role("searchbox", name="Search records").click()
    page.keyboard.type("r")
    page.locator("#elsewhere").focus()
    page.evaluate("document.querySelector('main').replaceChildren(LexeditorUI.bottomSearch({key: 'records', label: 'Search records', value: 'r'}))")
    page.wait_for_timeout(50)
    assert page.evaluate("document.activeElement.id") == "elsewhere"
