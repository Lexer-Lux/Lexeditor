"""The native dependency workaround keeps the source and package pins intact."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import prepare_ff8_native_dependencies as dependencies
from ff8_native_workflow import WORKFLOW


def authored_port():
    return (
        f'set(ref {dependencies.X264_REF})\n'
        'configure_file("version.diff.in" "version.diff" @ONLY)\n'
        'vcpkg_from_gitlab(\n'
        '    GITLAB_URL https://code.videolan.org/\n'
        '    OUT_SOURCE_PATH SOURCE_PATH\n'
        '    REPO videolan/x264\n'
        '    REF "${ref}"\n'
        f'    SHA512 {dependencies.ARCHIVE_SHA512}\n'
        '    HEAD_REF master\n'
        '    PATCHES\n'
        '        "version.diff"\n'
        '        uwp-cflags.patch\n'
        '        parallel-install.patch\n'
        '        allow-clang-cl.patch\n'
        '        configure.patch\n'
        ')\n'
        'vcpkg_make_configure(SOURCE_PATH "${SOURCE_PATH}")\n'
    ).encode()


def fixture_repo(tmp_path, monkeypatch, mutation=None):
    ffnx = tmp_path / 'ffnx'
    repo = ffnx / 'vcpkg'
    port = repo / 'ports' / 'x264'
    port.mkdir(parents=True)
    files = {
        'portfile.cmake': authored_port(),
        'vcpkg.json': json.dumps({'name': 'x264', 'version': '0.164.3108',
                                 'port-version': 2, 'license': 'GPL-2.0-or-later',
                                 'features': {'asm': {'description': 'Preserve'}}}).encode(),
        **{name: f'authored patch {name}\n'.encode() for name in (
            'version.diff.in', 'uwp-cflags.patch', 'parallel-install.patch',
            'allow-clang-cl.patch', 'configure.patch')},
        'nested/unchanged.txt': b'Unknown bytes\r\n\x00\xff',
    }
    if mutation:
        mutation(files)
    for name, content in files.items():
        output = port / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
    dependencies.git(repo, 'init')
    dependencies.git(repo, 'config', 'core.autocrlf', 'false')
    dependencies.git(repo, 'add', '.')
    dependencies.git(repo, '-c', 'user.name=Authored Fixture',
                     '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    baseline = dependencies.git(repo, 'rev-parse', 'HEAD').decode().strip()
    monkeypatch.setattr(dependencies, 'BASELINE', baseline)
    (ffnx / 'vcpkg.json').write_text(json.dumps({'builtin-baseline': baseline}))
    # A changed checkout must not replace the baseline's source or patch bytes.
    (port / 'portfile.cmake').write_bytes(b'poisoned working tree')
    (port / 'configure.patch').write_bytes(b'poisoned working tree')
    return ffnx, files


def test_overlay_reads_baseline_and_preserves_patch_and_metadata_bytes(tmp_path, monkeypatch):
    ffnx, files = fixture_repo(tmp_path, monkeypatch)
    overlay = tmp_path / 'overlay'
    provenance = tmp_path / 'candidate' / 'DEPENDENCIES.txt'
    dependencies.prepare(ffnx, overlay, provenance)
    for name, content in files.items():
        actual = (overlay / 'x264' / name).read_bytes()
        if name == 'portfile.cmake':
            assert b'vcpkg_from_git(' in actual
            assert b'URL https://code.videolan.org/videolan/x264.git' in actual
            assert dependencies.X264_REF.encode() in actual
            assert actual[actual.index(b'    HEAD_REF'):] == content[content.index(b'    HEAD_REF'):]
            assert b'vcpkg_from_gitlab(' not in actual
            assert b'SHA512' not in actual
        else:
            assert actual == content
    assert dependencies.BASELINE in provenance.read_text()
    assert dependencies.X264_REF in provenance.read_text()
    with pytest.raises(ValueError, match='new output'):
        dependencies.prepare(ffnx, overlay, provenance)


@pytest.mark.parametrize('invalid', ['ref', 'checksum', 'version', 'missing_patch', 'baseline'])
def test_changed_pins_fail_before_output(tmp_path, monkeypatch, invalid):
    def mutate(files):
        if invalid == 'ref':
            files['portfile.cmake'] = files['portfile.cmake'].replace(
                dependencies.X264_REF.encode(), b'0' * 40)
        elif invalid == 'checksum':
            files['portfile.cmake'] = files['portfile.cmake'].replace(
                dependencies.ARCHIVE_SHA512.encode(), b'0' * 128)
        elif invalid == 'version':
            files['vcpkg.json'] = files['vcpkg.json'].replace(b'0.164.3108', b'0.164.9999')
        elif invalid == 'missing_patch':
            del files['configure.patch']
    ffnx, _ = fixture_repo(tmp_path, monkeypatch, mutate)
    if invalid == 'baseline':
        (ffnx / 'vcpkg.json').write_text('{"builtin-baseline":"wrong"}')
    overlay = tmp_path / 'overlay'
    provenance = tmp_path / 'candidate' / 'DEPENDENCIES.txt'
    with pytest.raises(ValueError):
        dependencies.prepare(ffnx, overlay, provenance)
    assert not overlay.exists()
    assert not provenance.exists()


def test_native_configure_consumes_overlay_without_changing_compile_gates():
    assert 'python editor/tools/prepare_ff8_native_dependencies.py ffnx' in WORKFLOW
    assert '-DVCPKG_OVERLAY_PORTS=$env:GITHUB_WORKSPACE/dependency-ports' in WORKFLOW
    assert '-DFFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON' in WORKFLOW
    assert '-DFFNX_LEXEDITOR_LIVE_CONDITIONS=ON' in WORKFLOW
    assert '-DFFNX_DEPLOY_TO_GAME_DIRS=OFF' in WORKFLOW
