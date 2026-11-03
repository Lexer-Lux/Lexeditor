"""Legal documents remain ordinary files and survive player exports."""
import json
import os
from pathlib import Path

import pytest
from core import mod_licenses, mods_service
from test_shared_ui_feedback import page
from test_mods_tab import HOST


def make_mod(root, **metadata):
    root.mkdir(exist_ok=True)
    (root/'mod.json').write_text(json.dumps({'name':'Example', **metadata}))
    return root


def test_discovery_and_lossless_copy(tmp_path):
    root = make_mod(tmp_path/'mod', licenseFiles=['legal/custom.txt'])
    for name in ('LICENSE.txt', 'NOTICE', 'licenses/vendor/COPYING', 'legal/custom.txt'):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'Full license\r\nCopyright\r\n')
    release = tmp_path/'release'
    mod_licenses.copy(root, release)
    assert mods_service.mod_row(root)['licenseFiles'] == [p.as_posix() for p in mod_licenses.files(root)]
    for relative in mod_licenses.files(root):
        assert (root/relative).read_bytes() == (release/relative).read_bytes()
    assert not (release/'mod.json').exists()


@pytest.mark.parametrize('name', ['../outside', '/outside', 'C:/outside', 'legal\\outside', '', 'missing.txt'])
def test_bad_declarations_are_actionable_errors(tmp_path, name):
    root = make_mod(tmp_path/'mod', licenseFiles=[name])
    with pytest.raises(ValueError):
        mod_licenses.files(root)
    assert mods_service.mod_row(root)['error']


def test_links_are_rejected(tmp_path):
    root = make_mod(tmp_path/'mod', licenseFiles=['LICENSE'])
    outside = tmp_path/'outside'
    outside.write_text('private')
    try:
        (root/'LICENSE').symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks requires Windows developer mode')
    with pytest.raises(ValueError, match='link'):
        mod_licenses.copy(root, tmp_path/'release')


def test_ds1_release_preserves_documents_and_references(tmp_path, monkeypatch):
    from plugins.ds1 import runtime_mods, native_support
    root = make_mod(tmp_path/'mod', licenseFiles=['legal/terms.txt'])
    (root/'legal').mkdir()
    (root/'legal/terms.txt').write_bytes(b'Terms\r\n')
    (root/'LICENSE').write_bytes(b'License\n')
    (root/runtime_mods.FILENAME).write_bytes(b'fixture')
    monkeypatch.setattr(runtime_mods, 'read', lambda _: b'fixture')
    monkeypatch.setattr(runtime_mods, 'inspect', lambda _: {'requiresData':False})
    monkeypatch.setattr(native_support, 'rules_output', lambda *_: None)
    release = runtime_mods.write_release(root, tmp_path/'release', b'')
    assert json.loads((release/'mod.json').read_text())['licenseFiles'] == ['LICENSE','legal/terms.txt']
    assert (release/'legal/terms.txt').read_bytes() == b'Terms\r\n'
    (root/'legal/terms.txt').unlink()
    with pytest.raises(ValueError, match='missing'):
        runtime_mods.write_release(root, tmp_path/'second', b'')
    assert not (tmp_path/'second').exists()


def test_license_documents_appear_in_shared_details(page):
    page.add_script_tag(path=str(Path(__file__).resolve().parents[2]/'ui/framework.js'))
    host = HOST.replace("description: 'Mine.', credits: '',", "description: 'Mine.', credits: '', licenseFiles: ['LICENSE.txt', 'licenses/Crow.txt'],")
    page.evaluate(host, {})
    page.locator('[data-tab="mods"]').click()
    page.get_by_text('LICENSE FILES', exact=True).wait_for()
    assert page.get_by_role('textbox').filter(visible=True).count() > 0
    assert page.locator('input[value="licenses/Crow.txt"]').count() == 1
    screenshot = os.environ.get('LEXEDITOR_LICENSE_SCREENSHOT')
    if screenshot:
        page.screenshot(path=screenshot)
