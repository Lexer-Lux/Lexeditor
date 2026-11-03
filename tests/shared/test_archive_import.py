"""Real archive decoding, containment, bounds and recoverable import failures."""
import binascii
import io
from pathlib import Path
import tarfile
import zipfile

import pytest

from core import archive_import, mod_library

FIXTURES = Path(__file__).parent/'fixtures/archives'


def rar(tmp_path, case):
    encoded = (FIXTURES/('test_read_format_'+case+'.rar.uu')).read_bytes().splitlines()
    payload = b''.join(binascii.a2b_uu(line) for line in encoded[1:] if line not in (b'end', b'`', b' '))
    path = tmp_path/(case+'.rar')
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize('case,expected', [
    ('rar3_lowdist_reset', {'lowdist-reset.bin':64}),
    ('rar5_compressed', {'test.bin':1200}),
    ('rar5_multiple_files_solid', {f'test{index}.bin':4096 for index in range(1,5)}),
])
def test_real_compressed_and_solid_rar_files(tmp_path, case, expected):
    with mod_library.package_root(rar(tmp_path, case)) as root:
        assert {path.relative_to(root).as_posix():path.stat().st_size for path in root.rglob('*') if path.is_file()} == expected
        assert all(path.read_bytes() for path in root.rglob('*') if path.is_file())
    assert not root.exists()


@pytest.mark.parametrize('case', ['rar5_symlink', 'rar5_hardlink', 'rar5_unicode', 'rar5_encrypted', 'rar5_bad_tables'])
def test_bad_or_linked_rar_is_an_import_error_and_next_import_still_works(tmp_path, case):
    with pytest.raises(ValueError):
        with mod_library.package_root(rar(tmp_path,case)):
            pass
    with mod_library.package_root(rar(tmp_path,'rar5_compressed')) as root:
        assert (root/'test.bin').stat().st_size == 1200


@pytest.mark.parametrize('format,suffix', [('zip','.zip'), ('7zip','.7z'), ('pax_restricted','.tar')])
def test_offline_formats_and_unicode_roundtrip(tmp_path, format, suffix):
    archive_import.reader()  # Select the bundled DLL before importing the bindings.
    import libarchive
    source = tmp_path/('mod'+suffix)
    expected = {'mod.json':b'{"name":"Example"}', 'folder/日本.txt':b'mod data'}
    if format == 'zip':
        with zipfile.ZipFile(source,'w') as archive:
            for name,data in expected.items(): archive.writestr(name,data)
    else:
        with libarchive.file_writer(str(source), format) as archive:
            for name,data in expected.items():
                archive.add_file_from_memory(name,len(data),data)
    with mod_library.package_root(source) as root:
        assert {path.relative_to(root).as_posix():path.read_bytes() for path in root.rglob('*') if path.is_file()} == expected


def test_compressed_tar_accepts_conventional_dot_root(tmp_path):
    source = tmp_path/'mod.tar.gz'
    with tarfile.open(source,'w:gz') as archive:
        directory = tarfile.TarInfo('./')
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        entry = tarfile.TarInfo('./mod.json')
        entry.size = 2
        archive.addfile(entry,io.BytesIO(b'{}'))
    with mod_library.package_root(source) as root:
        assert (root/'mod.json').read_bytes() == b'{}'


@pytest.mark.parametrize('names', [('../outside',), ('C:/outside',), ('A.txt','a.txt'), ('file:stream',)])
def test_archive_paths_and_case_aliases_are_refused(tmp_path,names):
    source = tmp_path/'bad.zip'
    with zipfile.ZipFile(source,'w') as archive:
        for name in names:
            archive.writestr(name,b'data')
    with pytest.raises(ValueError):
        with mod_library.package_root(source):
            pass
    assert not (tmp_path/'outside').exists()


def test_file_and_byte_caps_apply_before_import(tmp_path,monkeypatch):
    source = tmp_path/'mod.zip'
    with zipfile.ZipFile(source,'w') as archive:
        archive.writestr('first',b'abcd')
        archive.writestr('second',b'efgh')
    monkeypatch.setattr(mod_library,'MAX_FILES',1)
    with pytest.raises(ValueError,match='file limit'):
        with mod_library.package_root(source): pass
    monkeypatch.setattr(mod_library,'MAX_FILES',100)
    monkeypatch.setattr(mod_library,'MAX_BYTES',3)
    with pytest.raises(ValueError,match='size limit'):
        with mod_library.package_root(source): pass


def test_archive_truncation_is_not_a_successful_empty_import(tmp_path):
    source = rar(tmp_path,'rar5_compressed')
    source.write_bytes(source.read_bytes()[:100])
    with pytest.raises(ValueError):
        with mod_library.package_root(source): pass


def test_rar_inspection_and_import_reach_the_same_library_pipeline(tmp_path):
    import json
    from types import SimpleNamespace
    source = rar(tmp_path,'rar5_compressed')
    adapter = SimpleNamespace(inspect=lambda root,files: {
        'valid':Path('test.bin') in files,'problems':[],'packages':['test.bin'],'notDeployed':[]})
    library = mod_library.ModLibrary(tmp_path/'library')
    report = library.inspect(source,adapter)
    assert report['valid'] and 'test.bin' in report['files']
    assert report['metadata']['name'] == 'rar5_compressed'
    target = library.import_mod('game',source,adapter,'RAR mod')
    assert (target/'test.bin').stat().st_size == 1200
    assert json.loads((target/'mod.json').read_text())['name'] == 'RAR mod'
