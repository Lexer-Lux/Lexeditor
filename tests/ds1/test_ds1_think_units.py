"""Think distances carry their metre unit.

Eleven think fields say "In metres" in their help (plus the four battle
distances, the same family), but none showed a unit: units wired off
label suffixes and these labels have none. The fifteen distance fields
now render unit fields in metres; neighboring non-distances stay plain.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def test_think_distances_show_metres():
    raw = make_archive()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-thinkunits-') as temp:
        game, mod = Path(temp) / 'game', Path(temp) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0',
                              'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('[data-tab="ai"]').click()
                    page.wait_for_function(
                        'state.tab==="ai" && state.sub==="ai" && state.row?.table==="NpcThinkParam"'
                        ' && !state.error', timeout=60000)
                    page.wait_for_timeout(400)
                    units = page.locator('.lex-detail-panel [data-lex-unit="m"]')
                    assert units.count() >= 15, units.count()
                    assert page.locator(
                        '.lex-detail-panel .lex-detail-field:has-text("Team Attack Weight")'
                        ' [data-lex-unit]').count() == 0
                finally:
                    browser.close()
        finally:
            session.stop()
