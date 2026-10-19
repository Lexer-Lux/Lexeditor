"""UI scale moves in five-percent increments only."""
import pytest
from test_shared_ui_feedback import page, framework


def mount(page, stored=None):
    page.evaluate('''(stored) => {
      window.pywebview = {api: {ui_scale: async () => ({percent: stored})}};
      document.querySelector('main').replaceChildren(LexeditorUI.uiScaleControl());
    }''', stored)


def test_slider_steps_by_five(page):
    framework(page)
    mount(page, 100)
    slider = page.locator('.lex-ui-scale input[type="range"]')
    assert slider.get_attribute('step') == '5'
    assert slider.get_attribute('min') == '50'
    assert slider.get_attribute('max') == '150'


@pytest.mark.parametrize('stored,shown', [(103, '105%'), (102, '100%'), (200, '150%'), (20, '50%')])
def test_stored_values_snap_and_clamp(page, stored, shown):
    framework(page)
    mount(page, stored)
    output = page.locator('.lex-ui-scale output')
    page.wait_for_function(f'document.querySelector(".lex-ui-scale output").textContent === "{shown}"')
    assert output.inner_text() == shown
    assert page.locator('.lex-ui-scale input[type="range"]').get_attribute('aria-valuetext') == shown


def test_input_event_snaps_display(page):
    framework(page)
    mount(page, 100)
    page.locator('.lex-ui-scale input[type="range"]').evaluate('''n => {
      n.value = 103;
      n.dispatchEvent(new Event('input', {bubbles: true}));
    }''')
    assert page.locator('.lex-ui-scale output').inner_text() == '105%'


def test_right_click_resets_to_100(page):
    framework(page)
    mount(page, 125)
    page.wait_for_function('document.querySelector(".lex-ui-scale output").textContent === "125%"')
    page.locator('.lex-ui-scale').click(button='right')
    page.wait_for_function('document.querySelector(".lex-ui-scale output").textContent === "100%"')
