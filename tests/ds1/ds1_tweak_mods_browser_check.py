"""The DS1 Tweaks tab lists tweak mods without switches of their own (the
Mods tab enables a mod), saves trust, and reports the installed executable. Uses its own small tweak-mod library and a
game folder without an executable, so it never touches real files."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
from paged_detail import reveal  # noqa: E402
from ds1_fixture import make_archive  # noqa: E402
from core import script_mods  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1 import tweak_mods  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TWEAK = 'def build(settings, context):\n    return {}\n'


def make(library: Path, mod_id: str, name: str, order: int) -> Path:
    root = library / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK, encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps({"title": name.upper(), "help": f"{name} help."}), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({"id": mod_id, "name": name, "order": order, "enabled": False,
                                               "script": {"version": 1}}), encoding="utf-8")
    return root


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-tweak-tab-') as temp:
        temp = Path(temp)
        game, mod, library = temp / 'game', temp / 'mod', temp / 'library'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        trust = temp / 'trust.json'
        os.environ[script_mods.TRUST_ENV] = str(trust)
        equip = make(library, 'equip-load-percentage', 'Equip Load Percentage', 100)
        ammo = make(library, 'later-game-ammunition', 'Later-Game Ammunition', 110)
        script_mods.set_trusted(equip, True)
        env = {'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod), 'LEXEDITOR_NO_MOD': '0',
               'LEXEDITOR_MOD_READ_ONLY': '0', tweak_mods.MODS_ENV: str(library), script_mods.TRUST_ENV: str(trust)}
        session = DS1Session(env)
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1200, 'height': 800})
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.add_init_script("""(() => {
                      const data={available:true,gameFound:true,installed:false,hasDefaults:true,
                        effects:[{file:'Fixture.fx',label:'Fixture effect',enabled:true,
                          values:{Mode:0},controls:[{name:'Mode',label:'Effect mode',widget:'combo',items:['Normal','Strong']}]}]};
                      window.reshadeCalls=[];
                      const reply=(method,args)=>{window.reshadeCalls.push([method,...args]);return structuredClone(data);};
                      window.pywebview={api:{
                        mod_reshade:async(...args)=>reply('mod_reshade',args),
                        set_reshade_enabled:async(...args)=>{data.installed=args[1];return reply('set_reshade_enabled',args);},
                        set_reshade_value:async(...args)=>{data.effects[0].values[args[2]]=args[3];return reply('set_reshade_value',args);}
                      }};
                    })();""")
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="tweaks"]').click()
                    page.wait_for_function('state.tab==="tweaks" && state.tweaks && !state.tweakBusy')
                    for title in ('INSTALLED GAME', 'EQUIP LOAD PERCENTAGE', 'LATER-GAME AMMUNITION'):
                        reveal(page, page.get_by_text(title, exact=True))
                    assert page.evaluate('reshadeCalls') == [['mod_reshade', 'ds1']]
                    reveal(page, page.get_by_role('switch', name='ReShade on or off')).check()
                    page.wait_for_function('state.reshade.installed===true')
                    reveal(page, page.get_by_role('combobox', name='Effect mode')).select_option('1')
                    page.wait_for_function('state.reshade.effects[0].values.Mode===1')
                    assert page.evaluate('reshadeCalls') == [
                        ['mod_reshade', 'ds1'], ['set_reshade_enabled', 'ds1', True],
                        ['set_reshade_value', 'ds1', 'Fixture.fx', 'Mode', 1]]
                    if output:
                        page.screenshot(path=str(output / 'ds1-reshade.png'))
                    # No executable here: the problem is stated and Apply is off.
                    reveal(page, page.get_by_text('DarkSoulsRemastered.exe is missing'))
                    assert page.get_by_role('button', name='Apply', exact=True).is_disabled()
                    reveal(page, page.get_by_role('button', name='Trust this tweak'))
                    if output:
                        page.screenshot(path=str(output / 'ds1-tweaks.png'))
                    # A tweak is a mod: the Tweaks tab has no switch, only
                    # an OFF mark while its mod is disabled.
                    assert page.get_by_role('checkbox', name='Equip Load Percentage').count() == 0
                    assert page.locator('.lex-tweak-off').count() == 2
                    data = json.loads((equip / 'mod.json').read_text(encoding='utf-8'))
                    (equip / 'mod.json').write_text(json.dumps({**data, 'enabled': True}), encoding='utf-8')
                    reveal(page, page.get_by_role('button', name='Trust this tweak')).click()
                    page.wait_for_function('!state.tweakBusy && state.tweaks.tweaks.every(r=>r.trust==="trusted")')
                    assert script_mods.trust_state(ammo) == 'trusted'
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="tweaks"]').click()
                    page.wait_for_function('state.tab==="tweaks" && state.tweaks')
                    page.wait_for_function('!state.tweakBusy')
                    assert page.locator('.lex-tweak-off').count() == 1
                    assert page.get_by_role('button', name='Trust this tweak').count() == 0
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print(json.dumps({'tweakMods': 2, 'noSwitch': True, 'trusted': True, 'missingExecutableReported': True}))


if __name__ == '__main__':
    main()
