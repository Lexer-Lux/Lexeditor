"""The developer drawer's overview table fits the drawer it is drawn in.

The table carries a column of sentences and a column of task lists, and it used
to push them at their natural width: the drawer grew a horizontal scrollbar
under a table that could have wrapped. The shared-UI file list is a disclosure,
and a disclosure with nothing behind it must not be drawn at all.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / 'ui/default_settings.json').read_text(encoding='utf-8'))

ROWS = [{"id": f"game_{index}", "game": f"GAME {index}",
         "quotes": 10 + index, "copiedLines": index * 3, "copiedRecorded": 0,
         "copiedOver": index == 2}
        for index in range(18)]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@pytest.fixture
def base():
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def open_drawer(page, base, files):
    settings = dict(BASE, developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={}, defaultValues=dict(BASE))
    overview = {"table": {"rows": ROWS, "quotesTotal": 120, "globalQuotes": 30,
                          "sharedUi": {"files": files, "totalShared": 412, "totalHand": 96}}}
    stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>([]),developer_overview:async()=>({json.dumps(overview)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")
    page.add_init_script(stub)
    page.goto(base + '/ui/chooser.html')
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
    page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)
    page.evaluate("setLexerPanel(true)")
    page.wait_for_selector('#lexer-dev-table .lex-column-list', timeout=8000)
    page.wait_for_timeout(400)


MEASURE = """()=>{
  const wrap=document.querySelector('.lexer-dev-table-wrap');
  const list=document.querySelector('#lexer-dev-table .lex-column-list');
  const details=document.querySelector('#lexer-dev-files-wrap');
  return {wrapOverflow:wrap.scrollWidth-wrap.clientWidth,
    listOverflow:list.scrollWidth-list.clientWidth,
    listWidth:list.clientWidth, wrapWidth:wrap.clientWidth,
    detailsHidden:details.hidden, detailsVisible:!!details.offsetParent,
    fileCount:document.querySelectorAll('#lexer-dev-files li').length,
    games:document.querySelectorAll('#lexer-dev-table .lex-column-list-row').length};
}"""


def test_the_overview_table_fits_its_column(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1500, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            open_drawer(page, base, [])
            fit = page.evaluate(MEASURE)
            assert not errors, errors
            assert fit['games'] == len(ROWS), fit
            assert fit['listOverflow'] == 0, fit
            assert fit['wrapOverflow'] == 0, fit
            assert fit['listWidth'] <= fit['wrapWidth'] + 1, fit
            # Nothing to disclose, so nothing is drawn.
            assert fit['fileCount'] == 0 and not fit['detailsVisible'], fit
        finally:
            browser.close()


def test_the_file_disclosure_appears_when_it_has_files(base):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1500, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            open_drawer(page, base, [{"file": "ui/framework.css", "selectors": 400,
                                      "handBuilt": 96, "over": True}])
            fit = page.evaluate(MEASURE)
            assert not errors, errors
            assert fit['fileCount'] == 1 and fit['detailsVisible'], fit
            assert fit['listOverflow'] == 0, fit
        finally:
            browser.close()
