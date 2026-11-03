"""DS1 layers stay distinguishable: tabs vs panels vs the app behind.

The abyss palette keeps its mood, but the tab buttons, the panels and
the application background behind them must differ by a visible step -
no two adjacent layers melting into one black mass.
"""
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from test_mods_tab import HOST

STEP = 28


def rgb(text):
    return tuple(int(part) for part in re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)', text).groups())


def gap(first, second):
    return sum(abs(first[index] - second[index]) for index in range(3))


@pytest.fixture
def page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        sheet = browser.new_page(viewport={'width': 1400, 'height': 900})
        sheet.route('http://fixture/**', lambda r: r.fulfill(
            body='<main id="main"></main>', content_type='text/html'))
        sheet.goto('http://fixture/')
        sheet.add_style_tag(path=str(ROOT / 'ui/framework.css'))
        sheet.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
        sheet.add_script_tag(path=str(ROOT / 'ui/framework.js'))
        yield sheet
        browser.close()


def backgrounds(page):
    return page.evaluate("""() => {
      const paint = document.createElement("canvas").getContext("2d", {willReadFrequently: true});
      const at = (sel) => {
        paint.fillStyle = getComputedStyle(document.querySelector(sel)).backgroundColor;
        paint.fillRect(0, 0, 1, 1);
        const [red, green, blue] = paint.getImageData(0, 0, 1, 1).data;
        return `rgb(${red}, ${green}, ${blue})`;
      };
      return {app: at('body'), nav: at('.lex-shell-header nav'),
        tab: at('[data-tab="items"]'), tabActive: at('[data-tab="mods"]'),
        panel: at('#main .lex-mods-page .lex-detail-panel'),
        panelTab: at('#main [role="tab"][data-subtab="files"]')};
    }""")


def test_shell_layers_step_down_visibly(page,tmp_path):
    page.evaluate(HOST, {'firstRun': False, 'lexmod': False, 'vanilla': False,
                         'conflicts': False, 'alerts': False, 'bundle': False,
                         'save': False, 'projects': False})
    page.wait_for_timeout(400)
    page.locator('[data-tab="mods"]').click()
    page.get_by_role('textbox', name='Name').wait_for()
    # Measure the palette after the tab's CSS transition, not its first
    # interpolated frame, which can still match the inactive tab on CI.
    page.evaluate('''async()=>{
      await Promise.all(document.querySelector('[data-tab="mods"]').getAnimations()
        .map(animation=>animation.finished.catch(()=>{})));
    }''')
    colors = {name: rgb(value) for name, value in backgrounds(page).items()}
    assert gap(colors['app'], colors['panel']) >= STEP, colors
    assert gap(colors['panel'], colors['tab']) >= STEP, colors
    assert gap(colors['panel'], colors['panelTab']) >= STEP, colors
    assert gap(colors['app'], colors['tab']) >= STEP, colors
    assert gap(colors['tab'], colors['tabActive']) >= STEP, colors
    page.screenshot(path=str(tmp_path/'theme-contrast.png'))
