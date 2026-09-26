"""The developer drawer seats its overview table in the column it is given.

The table used to stop at its content and leave the lower half of the drawer
empty. It now grows into the height it has - and it must not be squeezed below
its own rows, because a grid that keeps its stated height while its rows paint
outside the scroll area hides the last games where no scrollbar can reach them.
Below about 1280px the two panels stack: six headings alone need 807px, and a
narrower split forces the table to scroll sideways to its own last column.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "ui/default_settings.json").read_text(encoding="utf-8"))

ROWS = [{"id": f"game_{index}", "game": f"GAME {index}",
         "quotes": 10 + index, "copiedLines": index * 3, "copiedRecorded": 0,
         "copiedOver": index == 2}
        for index in range(18)]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


def open_drawer(page, base, width, height, rows=ROWS):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin="Lexer-Lux", viewPreferences={}, defaultValues=dict(BASE))
    overview = {"table": {"rows": rows, "quotesTotal": 120, "globalQuotes": 30,
                          "sharedUi": {"files": [{"file": "plugins/ff8/places.js",
                                                  "sharedSelectors": 1, "recordedSelectors": 0,
                                                  "handBuiltRows": 0, "recordedRows": 0,
                                                  "over": True}],
                                       "totalShared": 1, "totalHand": 0}}}
    stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>([]),developer_overview:async()=>({json.dumps(overview)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")
    page.set_viewport_size({"width": width, "height": height})
    page.add_init_script(stub)
    page.goto(base + "/ui/chooser.html")
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
    page.wait_for_selector("#loading-screen", state="hidden", timeout=8000)
    page.evaluate("setLexerPanel(true)")
    page.wait_for_selector("#lexer-dev-table .lex-column-list", timeout=8000)
    page.wait_for_timeout(400)


MEASURE = """()=>{
  const wrap=document.querySelector('.lexer-dev-table-wrap');
  const table=document.querySelector('#lexer-dev-table .lex-column-list');
  const rows=[...table.querySelectorAll('.lex-column-list-row')];
  const box=wrap.getBoundingClientRect();
  const last=rows[rows.length-1].getBoundingClientRect();
  return {wrapOverflow:wrap.scrollWidth-wrap.clientWidth,
    verticalOverflow:wrap.scrollHeight-wrap.clientHeight,
    gapBelowLastRow:Math.round(box.bottom-last.bottom),
    rows:rows.length,
    // Rows painted past the bottom of a box that cannot scroll.
    clipped:wrap.scrollHeight<=wrap.clientHeight+1&&last.bottom>box.bottom+1,
    tableGrew:table.getBoundingClientRect().height>=wrap.clientHeight-2,
    files:document.querySelectorAll('#lexer-dev-files li').length};
}"""


@pytest.fixture
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_a_short_table_fills_the_drawer_instead_of_stopping_half_way(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            open_drawer(page, base, 1600, 900, rows=ROWS[:4])
            fit = page.evaluate(MEASURE)
            assert not errors, errors
            assert fit["rows"] == 4, fit
            assert fit["wrapOverflow"] == 0, fit
            assert fit["verticalOverflow"] == 0, fit
            # The last game reaches the bottom of the region it was given,
            # instead of the table stopping and leaving the rest of it blank.
            assert abs(fit["gapBelowLastRow"]) <= 6, fit
            assert fit["tableGrew"], fit
            assert fit["files"] == 1, fit
        finally:
            browser.close()


def test_a_full_drawer_scrolls_instead_of_painting_games_past_the_scrollbar(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            open_drawer(page, base, 1600, 900)
            fit = page.evaluate(MEASURE)
            assert not errors, errors
            assert fit["rows"] == len(ROWS), fit
            assert fit["wrapOverflow"] == 0, fit
            # Every game is either on screen or reachable by scrolling.
            assert not fit["clipped"], fit
            assert fit["tableGrew"], fit
        finally:
            browser.close()


def test_a_narrow_drawer_stacks_its_panels_and_keeps_every_game(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            open_drawer(page, base, 1100, 700)
            fit = page.evaluate(MEASURE)
            assert not errors, errors
            assert fit["rows"] == len(ROWS), fit
            assert fit["wrapOverflow"] == 0, fit
            assert not fit["clipped"], fit
        finally:
            browser.close()


def test_a_stacked_drawer_gives_the_games_panel_the_height_it_needs(base):
    """Stacked, the games table is as tall as its own rows.

    The stacked grid split the drawer between its two rows instead: the table
    was given a four-row window, and because the rows painted on, the last
    games were drawn over the helper cards below with no scrollbar able to
    reach them. Each panel now takes the height its content needs and the
    drawer scrolls.
    """
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            open_drawer(page, base, 1100, 700)
            fit = page.evaluate(MEASURE)
            geometry = page.evaluate("""() => {
              const body=document.querySelector('.lexer-dev-body');
              const games=document.querySelector('.lexer-dev-games');
              const wrap=document.querySelector('.lexer-dev-table-wrap');
              const table=document.querySelector('#lexer-dev-table .lex-column-list');
              return {section:Math.round(games.getBoundingClientRect().height),
                wrapBottom:Math.round(wrap.getBoundingClientRect().bottom),
                sectionBottom:Math.round(games.getBoundingClientRect().bottom),
                table:Math.round(table.getBoundingClientRect().height),
                bodyScroll:body.scrollHeight, bodyClient:body.clientHeight};
            }""")
            assert not errors, errors
            assert fit["tableGrew"], fit
            # The table stays inside the panel that owns it. It used to hang
            # past the panel's bottom edge and paint over the helper cards.
            assert geometry["wrapBottom"] <= geometry["sectionBottom"] + 1, geometry
            # The panel is taller than the drawer, so the drawer scrolls rather
            # than squeezing the table into the height that is left.
            assert geometry["bodyScroll"] > geometry["bodyClient"] + 1, geometry
        finally:
            browser.close()
