"""Exit Without Saving works while a tweak rebuild is pending.

A stale tweak (installed tweaks differ from the library) counts toward the
dirty total so Save stays available, but abandoning the session must still
reach zero: the rebuild flag is deployment drift, not an unsent edit.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paged_detail import reveal  # noqa: E402
from ds1_fixture import make_archive  # noqa: E402
from test_ds1_exe_patches import HOOK_A, VANILLA, island  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1 import exe_patches, tweak_mods  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TWEAK = '''import json

def build(settings, context):
    return {"native/%s.json": json.dumps(%s)}
'''
SPEC = {"version": 1, "islands": [island("payload", rva=0x10000)],
        "hooks": [{"rva": HOOK_A, "original": "E800000000",
                   "branch": {"opcode": "E8", "island": "payload", "offset": 4}}]}
SCHEMA = {"fields": [{"key": "step", "type": "int", "default": 1, "min": 0, "max": 10}]}


def make_mod(library: Path) -> Path:
    root = library / "Alpha"
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK % ("alpha", repr(SPEC)), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    (root / "settings.json").write_text(json.dumps({"values": {"step": 1}}), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps(
        {"id": "alpha", "name": "Alpha", "enabled": True, "order": 10, "script": {"version": 1}}),
        encoding="utf-8")
    return root


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-exit-discard-') as temp:
        temp = Path(temp)
        game, mod, library = temp / 'game', temp / 'mod', temp / 'library'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / exe_patches.EXECUTABLE).write_bytes(VANILLA)
        mod.mkdir()
        (mod / MARKER).touch()
        make_mod(library)
        loader = tweak_mods.ensure_loader_mod(library)
        data = json.loads((loader / "mod.json").read_text(encoding="utf-8"))
        (loader / "mod.json").write_text(json.dumps({**data, "enabled": True}), encoding="utf-8")
        size, digest, closed = (exe_patches.VANILLA_SIZE, exe_patches.VANILLA_SHA256,
                                tweak_mods.ensure_game_closed)
        exe_patches.VANILLA_SIZE = len(VANILLA)
        exe_patches.VANILLA_SHA256 = hashlib.sha256(VANILLA).hexdigest()
        tweak_mods.ensure_game_closed = lambda: None
        try:
            tweak_mods.apply(game, library)
            tweak_mods.save({"alpha": {"values": {"step": 2}}}, library)
            assert tweak_mods.needs_rebuild(game, library)["needed"] is True
            env = {'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                   'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0',
                   tweak_mods.MODS_ENV: str(library)}
            session = DS1Session(env)
            try:
                session.start()
                with sync_playwright() as play:
                    browser = play.chromium.launch(headless=True)
                    try:
                        page = browser.new_page(viewport={'width': 1200, 'height': 800})
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(session.url)
                        page.wait_for_selector('body[data-ds1-ready="true"]')
                        page.locator('[data-tab="items"]').click()
                        page.wait_for_function(
                            'state.tab==="items" && state.rows.length>0 && !state.error')
                        page.locator('[data-subtab="weapons"]').click()
                        page.wait_for_function(
                            'state.sub==="weapons" && state.rows.length>0 && !state.error')
                        page.locator('.lex-list-row').first.click()
                        page.wait_for_function('state.row && !state.error')
                        control = reveal(page, page.locator(
                            'input[data-field-key][type="number"]').first)
                        old = float(control.input_value().replace(',', ''))
                        low = float(control.get_attribute('min'))
                        high = float(control.get_attribute('max'))
                        value = min(max(old + 1, low), high)
                        if value == old:
                            value = max(low, old - 1)
                        assert value != old
                        control.fill(str(int(value)) if value.is_integer() else str(value))
                        control.press('Tab')
                        page.wait_for_function('state.pending===0 && state.dirty>0')
                        # One param edit plus the stale tweak behind it.
                        assert page.evaluate('state.tweaksNeedRebuild') is True
                        assert page.evaluate(
                            'state.dirty+state.pending+(state.tweaksNeedRebuild?1:0)') == 2
                        page.evaluate("""()=>{
                          window.__dirtySyncs=[];
                          window.pywebview={api:{set_dirty_count:async(n)=>{window.__dirtySyncs.push(n);}}};
                          window.__exited=false;
                          LexeditorUI.confirmUnsavedExit(
                            {dirtyCount:()=>state.dirty+state.pending+(state.tweaksNeedRebuild?1:0),
                             save:()=>save(),discard:()=>discard()},
                            ()=>{window.__exited=true;return true;});
                        }""")
                        page.get_by_role('button', name='Exit Without Saving',
                                         exact=True).click()
                        page.wait_for_function('window.__exited===true')
                        assert page.get_by_text('could not be discarded').count() == 0
                        assert page.evaluate('window.__dirtySyncs.slice(-1)')[0] == 0
                        # The busy state throbs, and the host hears zero before
                        # the exit runs: a deferred discard holds the dialog open.
                        page.evaluate("""()=>{
                          window.__released=false;
                          window.__exited2=false;
                          LexeditorUI.confirmUnsavedExit(
                            {dirtyCount:()=>window.__released?0:1,
                             save:async()=>{},
                             discard:()=>new Promise(done=>{window.__release=()=>{window.__released=true;done();}})},
                            ()=>{window.__exited2=true;return true;});
                        }""")
                        page.get_by_role('button', name='Exit Without Saving',
                                         exact=True).click()
                        assert page.locator('.lex-exit-dialog .lex-dialog-status .lex-loading-status').count() == 1
                        page.evaluate('window.__release()')
                        page.wait_for_function('window.__exited2===true')
                        assert page.evaluate('window.__dirtySyncs.slice(-1)')[0] == 0
                        assert not errors, errors
                    finally:
                        browser.close()
            finally:
                session.stop()
        finally:
            exe_patches.VANILLA_SIZE, exe_patches.VANILLA_SHA256 = size, digest
            tweak_mods.ensure_game_closed = closed
    print('DS1 Exit Without Saving with a pending tweak rebuild passed.')


if __name__ == '__main__':
    main()
