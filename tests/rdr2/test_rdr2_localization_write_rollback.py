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


@pytest.mark.parametrize('existing_strings', [False, True])
def test_rollback_failure_retains_original_state_and_blocks_retries(isolated, monkeypatch, existing_strings):
    root, _ = isolated
    strings = s.ds_dir('mine') / s.LOCALIZATION_FILE
    if existing_strings:strings.write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    original_strings = strings.read_bytes() if existing_strings else None
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><Resources/></Install>')
    original_install = install.read_bytes()
    real_replace = Path.replace
    real_unlink = Path.unlink
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
    def unlink(path, *args, **kwargs):
        if not existing_strings and path == strings:
            raise OSError('Injected rollback failure')
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', unlink)
    with pytest.raises(RuntimeError) as failure:
        s.save_localization([{'key': 'FIRST', 'value': 'Changed'}])
    assert 'Injected install failure' in str(failure.value)
    assert 'rollback failed: strings.gxt2: Injected rollback failure' in str(failure.value)
    assert install.read_bytes() == original_install
    assert not list(root.rglob('*.tmp'))
    folders = list(root.rglob('.lexeditor-save-recovery-*'))
    assert len(folders) == 1
    folder = folders[0]
    import json
    state = json.loads((folder / 'state.json').read_text())
    assert state['target'] == str(strings.resolve())
    assert state['existed'] is existing_strings
    if existing_strings:assert (folder / 'original').read_bytes() == original_strings
    else:assert not (folder / 'original').exists()
    assert str(folder) in str(failure.value)
    before_retry = snapshot(root)
    monkeypatch.setattr(Path, 'replace', real_replace)
    monkeypatch.setattr(Path, 'unlink', real_unlink)
    for _ in range(2):
        with pytest.raises(OSError, match='blocked by unresolved recovery'):
            s.save_localization([{'key': 'FIRST', 'value': 'Another change'}])
        assert snapshot(root) == before_retry
    if existing_strings:strings.write_bytes((folder / 'original').read_bytes())
    else:strings.unlink()
    (folder / 'original').unlink(missing_ok=True)
    (folder / 'state.json').unlink()
    folder.rmdir()
    assert s.save_localization([{'key': 'FIRST', 'value': 'Recovered'}]) == 1
    assert s.parse_gxt2(strings)['FIRST'] == 'Recovered'
    assert not list(root.rglob('.lexeditor-save-recovery-*'))


def test_recovery_original_staging_failure_prevents_publication(isolated, monkeypatch):
    root, _ = isolated
    strings = s.ds_dir('mine') / s.LOCALIZATION_FILE
    strings.write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    before = snapshot(root)
    write = Path.write_bytes
    def fail(path, data):
        if path.name == 'original' and path.parent.name.startswith('.lexeditor-save-recovery-'):
            raise OSError('Injected recovery staging failure')
        return write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', fail)
    with pytest.raises(OSError, match='Injected recovery staging failure'):
        s.save_localization([{'key': 'FIRST', 'value': 'Changed'}])
    assert snapshot(root) == before
    assert not list(root.rglob('*.tmp'))
    assert not list(root.rglob('.lexeditor-save-recovery-*'))


def test_rollback_staging_failure_has_an_existing_original_recovery_copy(isolated, monkeypatch):
    root, _ = isolated
    strings = s.ds_dir('mine') / s.LOCALIZATION_FILE
    strings.write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    original = strings.read_bytes()
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><Resources/></Install>')
    real_replace = Path.replace
    real_temp = s.tempfile.NamedTemporaryFile
    def replace(path, target):
        if Path(target) == install:raise OSError('Injected publication failure')
        return real_replace(path, target)
    calls = 0
    def temporary(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:raise OSError('Injected rollback staging failure')
        return real_temp(*args, **kwargs)
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(s.tempfile, 'NamedTemporaryFile', temporary)
    with pytest.raises(RuntimeError, match='Injected rollback staging failure'):
        s.save_localization([{'key': 'FIRST', 'value': 'Changed'}])
    folders = list(root.rglob('.lexeditor-save-recovery-*'))
    assert len(folders) == 1
    assert (folders[0] / 'original').read_bytes() == original
    assert not list(root.rglob('*.tmp'))
    (folders[0] / 'original').unlink()
    (folders[0] / 'state.json').unlink()
    folders[0].rmdir()


@pytest.mark.parametrize('change', ['replace', 'delete', 'create'])
def test_output_changed_during_staging_is_not_overwritten(tmp_path, monkeypatch, change):
    target = tmp_path / 'data'
    if change != 'create':target.write_bytes(b'original')
    write = Path.write_text
    def change_source(path, *args, **kwargs):
        result = write(path, *args, **kwargs)
        if path.name == 'state.json':
            if change == 'delete':target.unlink()
            else:target.write_bytes(b'external')
        return result
    monkeypatch.setattr(Path, 'write_text', change_source)
    with pytest.raises(ValueError, match='changed during save'):
        s._commit_file_outputs([(target, b'candidate')], 'Probe')
    assert target.read_bytes() == b'external' if change != 'delete' else not target.exists()
    assert not list(tmp_path.glob('*.tmp'))
    assert not list(tmp_path.glob('.lexeditor-save-recovery-*'))


def test_external_edit_after_publication_is_preserved_during_failed_rollback(tmp_path, monkeypatch):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.write_bytes(b'original first');second.write_bytes(b'original second')
    replace = Path.replace
    def fail(path, target):
        if Path(target) == second:
            first.write_bytes(b'external edit')
            raise OSError('Injected second publication failure')
        return replace(path, target)
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(RuntimeError, match='rollback cannot overwrite it'):
        s._commit_file_outputs([(first, b'candidate first'), (second, b'candidate second')], 'Probe')
    assert first.read_bytes() == b'external edit'
    assert second.read_bytes() == b'original second'
    folders = list(tmp_path.glob('.lexeditor-save-recovery-*'))
    assert len(folders) == 1 and (folders[0] / 'original').read_bytes() == b'original first'
    assert not list(tmp_path.glob('*.tmp'))
    (folders[0] / 'original').unlink();(folders[0] / 'state.json').unlink();folders[0].rmdir()
