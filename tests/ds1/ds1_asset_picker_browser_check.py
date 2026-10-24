"""Model and icon IDs pick visually: face, thing finder and gallery.

Lexer: a cross-tab ID is a hoverable face plus a finder button, like a
record link. A Model ID names its parts binder and earns the shared
thing finder: the Models tab's binders of its piece become
hold-to-choose candidates, and the binder's number writes back into
the ID. Icon IDs choose from a gallery of every menu icon. Neither
keeps a number box; an ID with no file stays a plain ranged number.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from drb_fixture import make_dcx, make_drb, sprite_shape  # noqa: E402
from tpf_fixture import make_dds_rgba, make_tpf  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def pinned(page, table, row_id):
    page.wait_for_function(
        f'state.selected === "{table}:{row_id}" && state.row && state.row.table === "{table}"'
        f' && state.row.id === {row_id} && document.querySelector(".lex-detail-panel-name")'
        "?.textContent?.includes(state.row.name)")


def field_value(page, table, row_id, field_key, sub):
    return page.evaluate(
        '([table, rowId, fieldKey, sub]) => fetch('
        '`/api/row?table=${table}&id=${rowId}&sub=${sub}`).then(response => response.json())'
        '.then(found => found.row.fields.find(field => field.key === fieldKey).value)',
        [table, row_id, field_key, sub])


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-asset-pick-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive(field_values={
            'EquipParamWeapon': {100: {'iconId': 5, 'equipModelId': 100}}}))
        (game / 'menu').mkdir(parents=True)
        (game / 'menu' / 'menu.drb').write_bytes(make_drb(['Icon00'], {
            'Icon': [('EquIcon_0001', sprite_shape((0, 0, 0, 0), (83, 1, 163, 91), 0))]}))
        sheet = make_dds_rgba(2048, 2048, [(200, 160, 60, 255)] * (2048 * 2048))
        for index, names in enumerate((('Icon00',), ('Icon01', 'Icon10'), ('Icon11', 'Icon12'),
                                       ('Icon20', 'Icon21'), ('Icon30',), ('Icon40',))):
            entries = [(name, sheet) for name in names]
            (game / 'menu' / f'menu_{index}.tpf.dcx').write_bytes(make_dcx(make_tpf(entries)))
        (game / 'parts').mkdir(parents=True)
        for stem in ('WP_A_0100', 'WP_A_0110', 'BD_M_0100'):
            (game / 'parts' / f'{stem}.partsbnd.dcx').write_bytes(b'not a binder')
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="items"]').click()
                    page.wait_for_function('state.tab === "items" && !state.error')
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_function('state.sub === "weapons" && state.rows.length > 0')
                    page.locator('.lex-column-list .lex-list-row', has_text='Item 100').click()
                    pinned(page, 'EquipParamWeapon', 100)
                    page.locator('.lex-tabbed-panel [data-subtab="appearance"]').click()
                    page.wait_for_selector('.ds1-asset-face[data-field-key="equipModelId"]')
                    # Faces replace the number boxes; other numbers keep sliders.
                    for key in ('equipModelId', 'iconId'):
                        assert page.locator(
                            f'input[data-field-key="{key}"]').count() == 0, key
                        face = page.locator(f'.ds1-asset-face[data-field-key="{key}"]')
                        assert face.count() == 1, key
                    model_face = page.locator(
                        '.ds1-asset-face[data-field-key="equipModelId"] .lex-hoverable')
                    assert 'WP_A_0100.partsbnd.dcx' in model_face.inner_text()
                    icon_face = page.locator(
                        '.ds1-asset-face[data-field-key="iconId"] .lex-hoverable')
                    assert 'Icon 5' in icon_face.inner_text()
                    assert icon_face.locator('img.lex-hoverable-icon').count() == 1
                    assert page.locator(
                        '.lex-detail-panel input[type="number"][min]').count() > 0
                    # The icon gallery lists the menu catalog and commits a choice.
                    assert page.locator('button.ds1-icon-gallery').count() == 1
                    page.locator('button.ds1-icon-gallery').click()
                    gallery = page.locator('.ds1-icon-gallery-grid')
                    gallery.wait_for()
                    assert gallery.locator('.ds1-icon-choice').count() > 100
                    assert gallery.locator('.ds1-icon-choice.current').count() == 1
                    page.wait_for_function(
                        'document.querySelector(".ds1-icon-choice.current img")?.complete'
                        ' && document.querySelector(".ds1-icon-choice.current img")'
                        '.naturalWidth > 0')
                    if output:
                        page.screenshot(path=str(output / 'icon-gallery.png'))
                    gallery.locator('.ds1-icon-choice[data-lex-title="Icon 6"]').click()
                    page.wait_for_function(
                        '!document.querySelector(".ds1-icon-gallery-grid")')
                    page.wait_for_function('state.pending === 0')
                    assert field_value(page, 'EquipParamWeapon', 100, 'iconId', 'weapons') == 6
                    # The model finder offers this piece's binders, nothing else.
                    assert page.locator('button.ds1-find-asset').count() == 1
                    page.locator('button.ds1-find-asset').click()
                    page.wait_for_function('state.tab === "models" && state.rows.length === 3')
                    page.wait_for_function(
                        'document.querySelectorAll(".lex-column-list .lex-list-row").length >= 3')
                    rows = page.locator('.lex-column-list .lex-list-row')
                    for stem in ('WP_A_0100', 'WP_A_0110', 'BD_M_0100'):
                        assert rows.filter(has_text=stem).count() == 1, stem
                    for stem in ('WP_A_0100', 'WP_A_0110'):
                        assert rows.filter(has_text=stem).evaluate(
                            'node => node.classList.contains("lex-search-candidate")'), stem
                    assert rows.filter(has_text='BD_M_0100').evaluate(
                        'node => !node.classList.contains("lex-search-candidate")')
                    if output:
                        page.screenshot(path=str(output / 'model-pick.png'))
                    choice = rows.filter(has_text='WP_A_0110')
                    choice.hover()
                    page.mouse.down()
                    page.wait_for_function(
                        '!!document.querySelector(".lex-list-row.selecting")')
                    page.wait_for_timeout(1200)
                    page.mouse.up()
                    page.wait_for_function(
                        'fetch("/api/row?table=EquipParamWeapon&id=100&sub=weapons")'
                        '.then(response => response.json()).then(found => found.row.fields'
                        '.find(field => field.key === "equipModelId").value === 110)')
                    assert field_value(page, 'EquipParamWeapon', 100, 'equipModelId',
                                       'weapons') == 110
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 asset pickers passed.')


if __name__ == '__main__':
    main()
