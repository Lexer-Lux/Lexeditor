"""Injected localization I/O failures preserve original output and clean staging."""
from pathlib import Path

import pytest
from test_rdr2_item_creation_validation import isolated, fixture
from test_rdr2_catalog_numeric_validation import snapshot
from plugins.rdr2 import server as s


@pytest.mark.parametrize('existing_strings', [False, True])
@pytest.mark.parametrize('failure_target', ['strings.gxt2', 'install.xml'])
def test_failed_replacement_restores_all_outputs_and_retry_saves(isolated, monkeypatch, existing_strings, failure_target):
    root, _ = isolated
    strings = s.ds_dir('mine') / s.LOCALIZATION_FILE
    if existing_strings:
        strings.write_bytes(b'\xef\xbb\xbf[LEXEDITOR OVERRIDES]\r\nOLD = Keep\r\n')
    install = s.ds_dir('mine') / 'install.xml'
    install.write_bytes(b'<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    before = snapshot(root)
    real_replace = Path.replace
    failed = False
    def replace(path, target):
        nonlocal failed
        if Path(target).name == failure_target and not failed:
            failed = True
            raise OSError('Injected replacement failure')
        return real_replace(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    edits = [{'key': 'FIRST', 'value': 'Changed'}]
    with pytest.raises(OSError, match='Injected replacement failure'):
        s.save_localization(edits)
    assert failed
    assert snapshot(root) == before
    assert not list(root.rglob('*.tmp'))
    assert s.save_localization(edits) == 1
    assert s.parse_gxt2(strings) == ({'OLD': 'Keep', 'FIRST': 'Changed'} if existing_strings else {'FIRST': 'Changed'})
    assert not list(root.rglob('*.tmp'))


def test_staging_failure_leaves_outputs_and_cleans_first_temp(isolated, monkeypatch):
    root, _ = isolated
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><Resources/></Install>')
    before = snapshot(root)
    real_temp = s.tempfile.NamedTemporaryFile
    calls = 0
    def temporary(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('Injected staging failure')
        return real_temp(*args, **kwargs)
    monkeypatch.setattr(s.tempfile, 'NamedTemporaryFile', temporary)
    with pytest.raises(OSError, match='Injected staging failure'):
        s.save_localization([{'key': 'FIRST', 'value': 'Changed'}])
    assert snapshot(root) == before
    assert not list(root.rglob('*.tmp'))


def test_rollback_failure_reports_both_errors_and_cleans_staging(isolated, monkeypatch):
    root, _ = isolated
    strings = s.ds_dir('mine') / s.LOCALIZATION_FILE
    strings.write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><Resources/></Install>')
    original_install = install.read_bytes()
    real_replace = Path.replace
    strings_replacements = 0
    def replace(path, target):
        nonlocal strings_replacements
        if Path(target) == install:
            raise OSError('Injected install failure')
        if Path(target) == strings:
            strings_replacements += 1
            if strings_replacements == 2:
                raise OSError('Injected rollback failure')
        return real_replace(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(RuntimeError) as failure:
        s.save_localization([{'key': 'FIRST', 'value': 'Changed'}])
    assert 'Injected install failure' in str(failure.value)
    assert 'rollback failed: strings.gxt2: Injected rollback failure' in str(failure.value)
    assert install.read_bytes() == original_install
    assert not list(root.rglob('*.tmp'))
