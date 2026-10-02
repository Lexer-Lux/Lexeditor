"""The DS1 Tweaks tab lists tweak mods, saves their switches and trust, and
reports the installed executable. Uses its own small tweak-mod library and a
game folder without an executable, so it never touches real files."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
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
    destination = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LEXEDITOR_CHECK_ARTIFACTS")
    output = Path(destination) if destination else None
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
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="tweaks"]').click()
                    page.wait_for_function('state.tab==="tweaks" && state.tweaks && !state.tweakBusy')
                    for title in ('INSTALLED GAME', 'EQUIP LOAD PERCENTAGE', 'LATER-GAME AMMUNITION'):
                        page.get_by_text(title, exact=True).wait_for()
                    # No executable here: the problem is stated and Apply is off.
                    page.get_by_text('DarkSoulsRemastered.exe is missing').wait_for()
                    assert page.get_by_role('button', name='Apply', exact=True).is_disabled()
                    page.get_by_role('button', name='Trust this tweak').wait_for()
                    # The same schema-driven controls must remain usable in both sizes.
                    for width, height in ((1440, 900), (1000, 700)):
                        page.set_viewport_size({"width": width, "height": height})
                        page.get_by_role('checkbox', name='Equip Load Percentage').wait_for(state='visible')
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                        if output:
                            page.screenshot(path=str(output / f'ds1-tweaks-{width}x{height}.png'))
                    # A switch saves straight to the library mod.
                    page.get_by_role('checkbox', name='Equip Load Percentage').check()
                    page.wait_for_function('!state.tweakBusy && state.tweaks.tweaks.find(r=>r.id==="equip-load-percentage").enabled')
                    assert json.loads((equip / 'mod.json').read_text(encoding='utf-8'))['enabled'] is True
                    page.get_by_role('button', name='Trust this tweak').click()
                    page.wait_for_function('!state.tweakBusy && state.tweaks.tweaks.every(r=>r.trust==="trusted")')
                    assert script_mods.trust_state(ammo) == 'trusted'
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="tweaks"]').click()
                    page.wait_for_function('state.tab==="tweaks" && state.tweaks')
                    assert page.get_by_role('checkbox', name='Equip Load Percentage').is_checked()
                    assert page.get_by_role('button', name='Trust this tweak').count() == 0
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    evidence = {'tweakMods': 2, 'switchSaved': True, 'trusted': True,
                'missingExecutableReported': True, 'viewports': [[1440, 900], [1000, 700]]}
    if output:
        (output / "ds1-tweak-controls.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
