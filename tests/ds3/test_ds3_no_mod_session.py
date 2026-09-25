"""A DS3 game with no project opens on the game's own data, locked.

This is the state issue 567 describes: nobody has made a mod for this game
yet. The editor must show the installed game's values, refuse every edit, and
offer to create or find a mod instead of pretending the game is broken.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds3"))

from core.service_session import LocalPluginSession  # noqa: E402
from plugins.ds3.formats import encrypt_regulation  # noqa: E402
from test_ds3_plugin import _bnd4  # noqa: E402


@pytest.fixture
def no_mod_session():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds3-no-mod-") as temp_name:
        temp = Path(temp_name)
        source = temp / "installed-Data0.bdt"
        source.write_bytes(encrypt_regulation(_bnd4(), iv=b"\x51" * 16))
        environment = {
            "LEXEDITOR_DS3_SOURCE": str(source),
            "LEXEDITOR_DS3_PROJECT": str(temp / "no-such-project"),
            "LEXEDITOR_DS3_ROOT": str(temp / "game"),
            # What the host sets when it opens a game with no mod.
            "LEXEDITOR_MOD_READ_ONLY": "1",
            "LEXEDITOR_NO_MOD": "1",
        }
        session = LocalPluginSession(module="plugins.ds3.server", plugin_id="ds3",
                                     app_root=ROOT, check=lambda: [], extra_env=environment)
        session.start()
        try:
            yield session
        finally:
            session.stop()


def test_no_mod_session_shows_vanilla_values_and_locks_the_editor(no_mod_session):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            # The host answers the project menu; this stands in for it so the
            # shared control renders the real no-mod snapshot.
            page.add_init_script("""window.pywebview={api:{
              mod_projects:async()=>({pluginId:'ds3',current:'C:/Mods/DarkSouls3',
                canCreate:true,projects:[{path:'C:/Mods/DarkSouls3',name:'DarkSouls3',
                  version:'',valid:false,noMod:true,current:true,
                  problems:['No Dark Souls III project yet at C:/Mods/DarkSouls3. Create one to save changes.']}]}),
              mod_library_status:async()=>({canManage:false,message:'Mod management is not supported for this game yet.'}),
              }};""")
            page.goto(no_mod_session.url + "?lexNoMod=1")
            page.wait_for_selector("nav button[data-tab]", state="attached", timeout=60000)
            page.wait_for_timeout(3000)
            assert not errors, errors
            state = page.evaluate("""()=>{
              const main=document.querySelector('#main');
              const save=document.querySelector('#global-save');
              return {
                readonly:document.documentElement.getAttribute('data-lex-project-readonly'),
                badge:document.querySelector('.lex-shell-header .lex-badge')?.textContent||null,
                saveDisabled:save?save.disabled:null,
                showsGameData:(main?.innerText||'').includes('Kukri'),
                projectTrigger:document.querySelector('.lex-project-control')?.innerText.trim().slice(0,80)||null,
              };
            }""")
            assert state["readonly"] == "true", state
            assert state["badge"] == "NO MOD", state
            assert state["saveDisabled"] is True, state
            assert state["showsGameData"], state
            # The project menu is still the way out of this state.
            assert state["projectTrigger"] and "No mod" in state["projectTrigger"], state
            page.locator(".lex-project-control .lex-project-select").first.click()
            page.wait_for_timeout(300)
            menu = page.evaluate("""()=>{
              const panel=document.querySelector('.lex-project-control');
              const menu=panel.querySelector('.lex-project-menu');
              return {buttons:[...panel.querySelectorAll('button')].map(node=>node.textContent.trim())
                        .filter(Boolean),
                      hidden:menu?menu.hidden:null,
                      children:menu?menu.children.length:null,
                      expanded:panel.querySelector('.lex-project-select')?.getAttribute('aria-expanded')};
            }""")
            print("project menu:", menu)
            labels = menu["buttons"]
            assert menu["hidden"] is False, menu
            assert any("Add a Mod" in label for label in labels), menu
            assert any("Find a Mod" in label for label in labels), menu
            # Editing is refused even though the value came from the game.
            page.locator("#main input").first.click()
            page.keyboard.type("9")
            assert page.evaluate(
                "()=>document.querySelector('#main input').value") != "", "input vanished"
        finally:
            browser.close()
