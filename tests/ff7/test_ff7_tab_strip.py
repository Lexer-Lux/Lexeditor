"""The FF7 theme's full tab strip must not acquire vertical scrolling."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_ff7_rendered as fixture
ROOT = fixture.ROOT


def test_ff7_tab_strip_height():
    fixture.RenderedTests.setUpClass()
    case = fixture.RenderedTests()
    try:
        case.setUp()
        case.install()
        case.page.route('**/editor.css', lambda route: route.fulfill(path=str(ROOT / 'plugins/ff7/editor.css'), content_type='text/css'))
        font = os.environ.get('LEXEDITOR_TEST_FF7_FONT')
        if font:
            case.page.route('**/assets/ff7-menu.ttf*', lambda route: route.fulfill(path=font, content_type='font/ttf'))
        case.open()
        case.page.evaluate('document.fonts.ready')
        for width in (1600, 800):
            case.page.set_viewport_size({'width': width, 'height': 900})
            case.page.wait_for_timeout(150)
            dimensions = case.page.locator('.lex-nav-frame').evaluate('e=>({height:e.clientHeight,scroll:e.scrollHeight,overflow:getComputedStyle(e).overflowY})')
            shots = os.environ.get('LEXEDITOR_TEST_SHOTS')
            if shots:
                case.page.screenshot(path=str(Path(shots) / f'ff7-{width}.png'))
            assert dimensions['scroll'] <= dimensions['height'], dimensions
    finally:
        case.doCleanups()
        fixture.RenderedTests.tearDownClass()
