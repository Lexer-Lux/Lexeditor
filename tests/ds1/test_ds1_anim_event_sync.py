"""Animation Events gating follows the selection; event selection seeks the viewer.

The Events tab is gated on the selected motion having an event file:
picking a motion without one disables it with its reason, and picking
one with one re-enables it. Drilling into events seeks the playhead to
the selected event, and selecting another event seeks to it, paused or
playing state preserved either way.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from flver_fixture import build_flver, make_chrbnd  # noqa: E402
from hkx_fixture import build_tag0  # noqa: E402
from tae_fixture import build_anibnd, build_tae  # noqa: E402
from tpf_fixture import make_dds_rgba, make_tpf  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1.store import RELATIVE  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def make_game(folder):
    game = Path(folder) / 'game'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / 'chr').mkdir(parents=True)
    tag = build_tag0()
    # a87_3300 links anim 3300 in a87.tae (four events); a87_3302
    # links nowhere, so it has no event file at all. a88_3300 lives in
    # the sibling motion bank while its event file stays in the main
    # binder, the way shipped banks divide motions from events.
    (game / 'chr' / 'c1200.anibnd.dcx').write_bytes(build_anibnd(
        {'Skeleton.hkx': tag, 'a87.tae': build_tae(), 'a88.tae': build_tae(),
         'a87_3300.hkx': tag, 'a87_3302.hkx': tag}))
    (game / 'chr' / 'c1200_a9x.anibnd.dcx').write_bytes(build_anibnd(
        {'a88_3300.hkx': tag}))
    red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(
        build_flver(), 'c1200', [('c1200.tpf', make_tpf([('tex0', red)]))]))
    return game


def open_animations(page, url):
    page.goto(url)
    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
    page.locator('button[data-tab="animations"]').click()
    page.wait_for_function('state.tab === "animations" && !state.error', timeout=60000)
    page.wait_for_selector("[data-anim-host][data-ready='true']", timeout=60000)
    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
    page.wait_for_function(
        'document.querySelectorAll("[data-anim-list] .lex-list-row").length > 0',
        timeout=15000)


def events_tab(page):
    return page.locator('[data-anim-left] [data-tabstrip-id="events"]')


def readout(page):
    return page.locator('[data-anim-readout]').text_content()


def test_events_gate_follows_the_selected_motion():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-sync-') as folder:
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(make_game(folder)),
                              'LEXEDITOR_NO_MOD': '1', 'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    open_animations(page, session.url)
                    motions = page.locator('[data-anim-list] .lex-list-row')
                    motions.filter(has_text='a87_3302.hkx').click()
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-anim-left] [data-tabstrip-id="events"]'
                          ).getAttribute('aria-disabled') === 'true'""",
                        timeout=15000)
                    tab = events_tab(page)
                    assert tab.get_attribute('data-lex-title') == \
                        'The current animation has no event file.'
                    motions.filter(has_text='a87_3300.hkx').click()
                    page.wait_for_function(
                        """() => !document.querySelector(
                          '[data-anim-left] [data-tabstrip-id="events"]'
                          ).hasAttribute('aria-disabled')""",
                        timeout=15000)
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        assert errors == []


def test_sibling_bank_motion_drills_into_main_binder_events():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-sync-') as folder:
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(make_game(folder)),
                              'LEXEDITOR_NO_MOD': '1', 'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    open_animations(page, session.url)
                    page.locator('[data-anim-list] .lex-list-row').filter(
                        has_text='a88_3300.hkx').click()
                    page.wait_for_function(
                        """() => !document.querySelector(
                          '[data-anim-left] [data-tabstrip-id="events"]'
                          ).hasAttribute('aria-disabled')""",
                        timeout=15000)
                    events_tab(page).click()
                    page.wait_for_function(
                        'state.animScope.level === "events" && state.rows.length === 4',
                        timeout=15000)
                    assert page.evaluate('state.animEventError') is None
                    first = page.locator('[data-anim-list] .lex-list-row').first.text_content()
                    assert 'at 0.00s' in first, first
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        assert errors == []


def test_event_selection_seeks_the_playhead():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-sync-') as folder:
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(make_game(folder)),
                              'LEXEDITOR_NO_MOD': '1', 'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    open_animations(page, session.url)
                    page.locator('[data-anim-list] .lex-list-row').filter(
                        has_text='a87_3300.hkx').click()
                    page.locator('[data-anim-transport] button[aria-label="Play or pause"]').click()
                    page.locator('[data-anim-transport] button[aria-label="Go to animation end"]').click()
                    assert '\u25b6' in page.locator(
                        '[data-anim-transport] button[aria-label="Play or pause"]').text_content()
                    # Drilling seeks the auto-selected first event (start 0.00s).
                    events_tab(page).click()
                    page.wait_for_function(
                        'document.querySelector("[data-anim-readout]").textContent.includes("0.00s")',
                        timeout=15000)
                    # The seek lands before the list re-renders, so wait for
                    # the event rows themselves before clicking one.
                    page.wait_for_function(
                        'document.querySelector("[data-anim-list] .lex-list-row").textContent.includes("at 0.00s")',
                        timeout=15000)
                    # Selecting the third event (start 1.50s) seeks to it,
                    # still paused. The 0.1s fixture motion wraps cue times
                    # past its end, exactly like marker clicks do, so the
                    # expected readout is computed from the viewer duration.
                    page.locator('[data-anim-list] .lex-list-row').nth(2).click()
                    page.wait_for_function(
                        """() => {
                          const viewer = document.querySelector(
                            '[data-anim-host]')._animViewer;
                          const want = (1.5 % viewer.duration).toFixed(2) + 's';
                          return document.querySelector(
                            '[data-anim-readout]').textContent.includes(want);
                        }""",
                        timeout=15000)
                    assert '\u25b6' in page.locator(
                        '[data-anim-transport] button[aria-label="Play or pause"]').text_content()
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        assert errors == []
