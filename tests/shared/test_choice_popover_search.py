from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import page, framework


def test_choice_popover_search_filters_and_selects(page):
    framework(page)
    page.evaluate('''() => {
      window.__picked = null;
      const pop = LexeditorUI.choicePopover({label: 'Pick', search: 'Search effects',
        choices: [{label: 'Alpha', value: 1}, {label: 'Beta', value: 2}, {label: 'Gamma', value: 3}],
        select: value => { window.__picked = value; }});
      document.querySelector('main').append(pop);
      pop.openFor(document.querySelector('main'));
    }''')
    search = page.locator('.lex-choice-popover-search')
    assert search.count() == 1
    assert search.get_attribute('placeholder') == 'Search effects'
    assert page.evaluate('document.activeElement.className') == 'lex-choice-popover-search'
    search.fill('amm')
    visible = page.locator('.lex-choice-popover > button:not([hidden])')
    assert visible.count() == 1
    assert visible.first.get_attribute('aria-label') == 'Gamma'
    search.press('ArrowDown')
    assert page.evaluate('document.activeElement.getAttribute("aria-label")') == 'Gamma'
    visible.first.click()
    assert page.evaluate('window.__picked') == 3
    page.locator('.lex-choice-popover').wait_for(state='detached')


def test_choice_popover_without_search_has_no_filter(page):
    framework(page)
    page.evaluate('''() => {
      const pop = LexeditorUI.choicePopover({label: 'Pick',
        choices: [{label: 'Alpha', value: 1}]});
      document.querySelector('main').append(pop);
      pop.openFor(document.querySelector('main'));
    }''')
    assert page.locator('.lex-choice-popover-search').count() == 0
    assert page.locator('.lex-choice-popover > button').count() == 1
