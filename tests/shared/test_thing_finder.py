"""The universal thing finder: one trigger for the hold-to-choose searcher."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402,F811 (fixture)
from test_tab_rename import mount_shell  # noqa: E402


def open_finder(page, hold_ms=150):
    page.evaluate("""holdMs => {
      const U = LexeditorUI;
      window.accepted = [];
      window.origins = 0;
      window.shown = [];
      window.showCandidates = () => {
        const candidate = U.decorateSearchCandidate(
          U.el('button', {onclick: () => shown.push(7)}, 'Candidate'),
          {type: 'items', value: 7});
        document.querySelector('main').replaceChildren(candidate);
      };
      window.showSource = () => document.querySelector('main')
        .replaceChildren(U.el('p', {}, 'Source'));
      document.querySelector('main').append(U.thingFinderButton({
        label: 'Choose an item', type: 'items', holdMs,
        prompt: 'Choose the item for the test.',
        target: showCandidates,
        origin: () => { origins++; showSource(); },
        accept: value => accepted.push(value)}));
    }""", hold_ms)
    page.locator('.lex-thing-finder').click()


def test_thing_finder_button_opens_the_searcher_with_its_prompt(page, tmp_path):
    framework(page)
    mount_shell(page, developer=False)
    open_finder(page)
    bar = page.locator('.lex-searcher-bar')
    bar.wait_for()
    assert page.locator('.lex-searcher-prompt').inner_text() == 'Choose the item for the test.'
    assert not page.locator('.lex-nav-frame').is_visible()
    page.screenshot(path=str(tmp_path / 'thing-finder-bar.png'))
    candidate = page.get_by_role('button', name='Candidate', exact=True)
    candidate.click()
    assert page.evaluate('shown') == [7]
    assert page.evaluate('accepted') == []
    candidate.hover()
    page.mouse.down()
    page.wait_for_function('accepted.length === 1')
    page.mouse.up()
    assert page.evaluate('accepted') == [7]
    assert page.evaluate('origins') == 1
    assert page.locator('.lex-searcher-bar').count() == 0
    assert page.locator('.lex-nav-frame').is_visible()


def test_thing_finder_back_button_and_cancel_return_to_source(page):
    framework(page)
    mount_shell(page, developer=False)
    open_finder(page)
    bar = page.locator('.lex-searcher-bar')
    bar.wait_for()
    page.locator('.lex-searcher-context').click()
    assert page.locator('main').evaluate('e=>e.inert')
    assert 'blue return button' in bar.inner_text()
    page.locator('.lex-searcher-context').click()
    assert not page.locator('main').evaluate('e=>e.inert')
    assert page.evaluate('origins') == 1
    page.get_by_role('button', name='Cancel selection', exact=True).click()
    assert page.evaluate('origins') == 2
    assert page.locator('.lex-searcher-bar').count() == 0
    assert page.locator('main').inner_text() == 'Source'
    assert page.locator('.lex-nav-frame').is_visible()


def test_thing_finder_field_pairs_a_value_with_its_button(page):
    framework(page)
    mount_shell(page, developer=False)
    page.evaluate("""() => {
      const U = LexeditorUI;
      window.opened = 0;
      document.querySelector('main').append(
        U.thingFinderField(U.el('span', {}, 'Potion'), {label: 'Choose an item',
          type: 'items', prompt: 'Choose an item.', fillValue: true,
          target: () => opened++, origin: () => {}, accept: () => {}}));
    }""")
    field = page.locator('.lex-choice-field')
    assert field.count() == 1
    assert 'lex-choice-field-fill' in (field.get_attribute('class') or '')
    assert field.inner_text().startswith('Potion')
    button = field.locator('.lex-thing-finder')
    assert button.count() == 1
    assert button.get_attribute('aria-label') == 'Choose an item'
    assert button.get_attribute('data-lex-title') == 'Choose an item'
    assert button.locator('svg').count() == 1
    button.click()
    assert page.evaluate('opened') == 1
    assert page.locator('.lex-searcher-bar').count() == 1


def test_disabled_thing_finder_stays_shut(page):
    framework(page)
    mount_shell(page, developer=False)
    page.evaluate("""() => {
      document.querySelector('main').append(LexeditorUI.thingFinderButton({
        label: 'Choose an item', disabled: true, type: 'items',
        prompt: 'Choose an item.', target: () => {}, origin: () => {}}));
      document.querySelector('.lex-thing-finder').click();
    }""")
    assert page.locator('.lex-thing-finder').is_disabled()
    assert page.locator('.lex-searcher-bar').count() == 0


def test_custom_content_keeps_its_own_face(page):
    framework(page)
    mount_shell(page, developer=False)
    page.evaluate("""() => {
      const U = LexeditorUI;
      window.opened = 0;
      document.querySelector('main').append(U.thingFinderButton({
        label: 'Choose a card', type: 'cards', prompt: 'Choose a card.',
        target: () => opened++, origin: () => {},
        content: U.el('span', {class: 'card-face'}, 'Card art')}));
    }""")
    button = page.locator('.lex-thing-finder')
    assert 'lex-thing-finder-custom' in (button.get_attribute('class') or '')
    assert button.locator('.card-face').inner_text() == 'Card art'
    assert button.locator(':scope > svg').count() == 0
    button.click()
    assert page.evaluate('opened') == 1
