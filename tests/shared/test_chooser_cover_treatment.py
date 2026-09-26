"""The Back to Editor handle's cover art is blurred and darkened, by setting.

The handle is the game cover with an arrow and a save mark over it. Its blur
and its darkening are developer settings, so the art can be a texture at one
value and nearly the cover itself at another. 0% must leave the art alone.
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
COVER = (ROOT / 'ui/assets/blank-game-cover.png').as_uri()


def stub_script(settings):
    plugins = [{'id': 'ff7', 'name': 'Final Fantasy VII', 'status': 'added',
                'canOpen': True, 'resident': True, 'dirtyCount': 0,
                'problems': [], 'statusText': '',
                'coverArt': {'state': 'ready', 'uri': COVER}}]
    return (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(plugins)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")


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


def open_menu(page, base, settings):
    page.add_init_script(stub_script(settings))
    page.goto(base + '/ui/chooser.html')
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
    page.wait_for_selector('#resident-handle:not([hidden])', timeout=8000)
    page.wait_for_selector('#loading-screen', state='hidden', timeout=8000)


TREATMENT = """()=>{
  const handle = document.querySelector('#resident-handle');
  const root = getComputedStyle(document.documentElement);
  const art = getComputedStyle(handle, '::before');
  const film = getComputedStyle(handle, '::after');
  return {
    background: handle.style.backgroundImage,
    blur: root.getPropertyValue('--lex-resident-cover-blur').trim(),
    darken: root.getPropertyValue('--lex-resident-cover-darken').trim(),
    filter: art.filter,
    film: film.backgroundColor,
  };
}"""


def film_alpha(film):
    inside = film[film.index('(') + 1:film.rindex(')')]
    parts = [part.strip() for part in inside.split(',')]
    return float(parts[3]) if len(parts) == 4 else 1.0


def test_cover_settings_are_stored_and_bounded(tmp_path):
    from core.settings_manager import SettingsStore
    store = SettingsStore(tmp_path / 'settings.json', tmp_path / 'defaults.json')
    assert store.snapshot()['residentCoverBlurPixels'] == 8.0
    assert store.snapshot()['residentCoverDarkenPercent'] == 58.0
    store.save_packaged_defaults({'residentCoverBlurPixels': 99,
                                  'residentCoverDarkenPercent': 400})
    saved = store.snapshot()
    assert saved['defaultValues']['residentCoverBlurPixels'] == 24.0
    assert saved['defaultValues']['residentCoverDarkenPercent'] == 100.0
    assert saved['residentCoverBlurPixels'] == 24.0
    assert saved['residentCoverDarkenPercent'] == 100.0
    assert SettingsStore(store.path, store.defaults_path).snapshot()[
        'residentCoverBlurPixels'] == 24.0


def test_cover_is_blurred_and_darkened_at_the_shipped_amounts(base):
    # The treatment at a known pair of values; the shipped defaults are tuned
    # from Developer Mode and change, so the amounts are set here.
    settings = dict(BASE, residentCoverBlurPixels=8.0, residentCoverDarkenPercent=58.0,
                    developerMode=True, developerAuthorized=True,
                    developerLogin='Lexer-Lux', viewPreferences={},
                    defaultValues=dict(BASE))
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            open_menu(page, base, settings)
            page.wait_for_timeout(300)
            drawn = page.evaluate(TREATMENT)
            assert COVER.split('/')[-1] in drawn['background'], drawn
            assert drawn['blur'] == '8px', drawn
            assert drawn['darken'] == '0.58', drawn
            assert 'blur(8px)' in drawn['filter'], drawn
            assert 'brightness(0.42)' in drawn['filter'], drawn
            assert abs(film_alpha(drawn['film']) - 0.43) < 0.01, drawn
            # The arrow and the save mark stay above the treatment.
            assert page.evaluate('''()=>{
              const handle=document.querySelector('#resident-handle');
              const arrow=handle.querySelector('.resident-arrow');
              const box=handle.getBoundingClientRect(), ink=arrow.getBoundingClientRect();
              return getComputedStyle(arrow).zIndex==='1' && ink.width>0 && ink.height>0 &&
                getComputedStyle(handle).overflow==='hidden' && box.width>0;}''')

            # A developer who asks for the bare cover gets the bare cover.
            page.evaluate("""(settings) => dispatchEvent(
              new CustomEvent('lexeditor-settings-changed', {detail: settings}))""",
                          dict(settings, residentCoverBlurPixels=0, residentCoverDarkenPercent=0))
            page.wait_for_timeout(200)
            plain = page.evaluate(TREATMENT)
            assert plain['blur'] == '0px' and plain['darken'] == '0', plain
            assert plain['filter'] in ('none', 'blur(0px) brightness(1)'), plain
            assert film_alpha(plain['film']) == 0, plain

            # And the two settings are clamped to what the control offers.
            page.evaluate("""(settings) => dispatchEvent(
              new CustomEvent('lexeditor-settings-changed', {detail: settings}))""",
                          dict(settings, residentCoverBlurPixels=99,
                               residentCoverDarkenPercent=400))
            page.wait_for_timeout(200)
            capped = page.evaluate(TREATMENT)
            assert capped['blur'] == '24px' and capped['darken'] == '1', capped
            assert not errors, errors
        finally:
            browser.close()
