"""Render the DS1 Info tab's Apply/Restore controls; never touches a real game."""
import hashlib
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def field_value(page, label):
    return page.get_by_text(label, exact=True).locator('xpath=following::input[1]').input_value()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output: output.mkdir(parents=True, exist_ok=True)
    raw = make_archive()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-deploy-ui-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir()
        (mod / MARKER).touch()
        (mod / RELATIVE).parent.mkdir(parents=True)
        edited = ItemDocument(raw)
        edited.edit('EquipParamGoods', 100, 'sellValue', 42)
        (mod / RELATIVE).write_bytes(edited.export())
        original_hash = hashlib.sha256(raw).hexdigest()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1280, 'height': 800})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.evaluate('navigate("info")')
                    page.wait_for_function('state.tab==="info" && state.deployment && !state.error')
                    if output: page.screenshot(path=str(output / 'info-before-apply.png'))

                    apply_button = page.get_by_role('button', name='Apply', exact=True)
                    restore_button = page.get_by_role('button', name='Restore original', exact=True)
                    apply_button.wait_for()
                    assert apply_button.is_enabled()
                    assert restore_button.is_disabled()

                    apply_button.click()
                    dialog = page.locator('.lex-dialog')
                    dialog.wait_for()
                    assert 'Apply this mod to the installed game' in dialog.inner_text()
                    dialog.get_by_role('button', name='Apply', exact=True).click()
                    page.wait_for_function('state.deployment && state.deployment.enabled===true')
                    assert ItemDocument((game / RELATIVE).read_bytes()).value('EquipParamGoods', 100, 'sellValue') == 42
                    assert restore_button.is_enabled()
                    if output: page.screenshot(path=str(output / 'info-after-apply.png'))

                    # Keep the service open across Apply, a later edit/save, and
                    # Reapply. The backup is now Vanilla, not the deployed file.
                    page.evaluate('''async () => {
                        await api('/api/edit', {table:'EquipParamGoods',id:100,field:'sellValue',value:43});
                        await api('/api/save', {});
                        await loadDeployment();render();
                    }''')
                    assert field_value(page, 'UP TO DATE') == 'No, reapply after the latest save'
                    page.get_by_role('button', name='Reapply', exact=True).click()
                    dialog.get_by_role('button', name='Apply', exact=True).click()
                    page.wait_for_function('!state.deployBusy && state.deployment.stale===false')
                    assert ItemDocument((game / RELATIVE).read_bytes()).value('EquipParamGoods', 100, 'sellValue') == 43

                    restore_button.click()
                    dialog.wait_for()
                    assert 'Restore the original installed param archive' in dialog.inner_text()
                    dialog.get_by_role('button', name='Restore original', exact=True).click()
                    page.wait_for_function('state.deployment && state.deployment.enabled===false')
                    assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == original_hash
                    if output: page.screenshot(path=str(output / 'info-after-restore.png'))

                    # --- Honest labels for states a real crash/external-change/other-project
                    # install could leave behind: must never claim "restored" or "this
                    # project" when the facts don't support it. Client state is mutated
                    # directly and re-rendered through the real render() pipeline.
                    page.evaluate('''() => {
                        state.deployment = {...state.deployment, everApplied:true, enabled:false,
                          backupOk:true, changedExternally:false, pendingRecovery:true,
                          matchesOriginal:false, thisProjectActive:false, stale:false};
                        render();
                    }''')
                    assert field_value(page, 'APPLIED') == 'Unknown — an interrupted operation needs Apply or Restore to finish'
                    if output: page.screenshot(path=str(output / 'info-pending-recovery.png'))

                    page.evaluate('''() => {
                        state.deployment = {...state.deployment, everApplied:true, enabled:true,
                          backupOk:true, changedExternally:false, pendingRecovery:false,
                          matchesOriginal:false, thisProjectActive:false, stale:false};
                        render();
                    }''')
                    assert field_value(page, 'APPLIED') == "Yes, a different project's edits"
                    assert field_value(page, 'UP TO DATE') == '-'
                    if output: page.screenshot(path=str(output / 'info-other-project-active.png'))

                    page.evaluate('''() => {
                        state.deployment = {...state.deployment, everApplied:true, enabled:false,
                          backupOk:false, changedExternally:false, pendingRecovery:false,
                          matchesOriginal:false, thisProjectActive:false, stale:false};
                        render();
                    }''')
                    assert field_value(page, 'APPLIED') == 'Unknown — the preserved original is missing or changed'
                    if output: page.screenshot(path=str(output / 'info-backup-missing.png'))

                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == original_hash
    print('ds1 deployment UI render check passed')


if __name__ == '__main__':
    main()
