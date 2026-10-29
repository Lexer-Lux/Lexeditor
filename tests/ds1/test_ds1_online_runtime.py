"""Online loader: native save isolation, bounded backups and install ownership.

Synthetic saves exercise the actual IAT hook in separate headless processes.
They cannot prove acceptance by FromSoftware's servers or a Steam Cloud upload.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from plugins.ds1 import tweak_mods
from plugins.ds1.mod_support import Ds1ModAdapter

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'plugins/ds1/runtime'
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def build_module():
    spec = importlib.util.spec_from_file_location('ds1_online_build', RUNTIME / 'build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shipped_sources_and_online_dll_match():
    build = build_module()
    for folder, sources in [('', build.SOURCES), ('debug', build.DEBUG_SOURCES), ('online', build.ONLINE_SOURCES)]:
        manifest = json.loads((RUNTIME / 'package' / folder / 'runtime-manifest.json').read_text())
        assert manifest['sourceSha256'] == build.source_hash(sources), f'Rebuild {folder or "everyday"} loader'
        assert manifest['sha256'] == hashlib.sha256((RUNTIME / 'package' / folder / 'dinput8.dll').read_bytes()).hexdigest()
    assert manifest['overhaulRevision'] == build.OVERHAUL_REVISION
    assert manifest['license'] == 'AGPL-3.0-only'
    source = json.loads((RUNTIME / 'overhaul/SOURCE.json').read_text())
    assert source['revision'] == build.OVERHAUL_REVISION
    for name, upstream in [('AntiAntiCheat.h', 'OverhaulDLL/include/AntiAntiCheat.h'),
                           ('AntiAntiCheatASM.asm', 'OverhaulDLL/src/AntiAntiCheatASM.asm')]:
        assert hashlib.sha256((RUNTIME / 'overhaul' / name).read_bytes()).hexdigest() == source['upstreamSha256'][upstream]
    assert 'GNU AFFERO GENERAL PUBLIC LICENSE' in (RUNTIME.parent / 'credits.md').read_text()


def test_native_upstream_filters_keep_matchmaking_but_remove_equipment_reports(tmp_path):
    if sys.platform != 'win32':
        pytest.skip('Windows runtime')
    build = build_module()
    try:
        vcvars = build.find_vcvars()
    except SystemExit:
        pytest.skip('MSVC is needed for the upstream C++ fixture')
    source = Path(__file__).with_name('runtime_reporting_harness.cpp')
    script = tmp_path / 'build.bat'
    script.write_text(f'@echo off\ncall "{vcvars}" >nul\n'
                      f'cl /nologo /EHsc /std:c++17 /D_CRT_SECURE_NO_WARNINGS '
                      f'/I"{RUNTIME / "overhaul"}" "{source}" /Fe:report.exe\n', encoding='utf-8')
    subprocess.run(['cmd', '/c', str(script)], cwd=tmp_path, check=True, capture_output=True, creationflags=FLAGS)
    result = subprocess.run([str(tmp_path / 'report.exe')], cwd=tmp_path, capture_output=True,
                            text=True, timeout=10, creationflags=FLAGS)
    assert result.returncode == 0 and result.stdout.strip() == 'report filters passed', result


def test_install_and_remove_preserve_saves_and_describe_new_runtime(tmp_path):
    assert tweak_mods.launch_notice(tmp_path) == ''
    save = tmp_path / 'DRAKS0005.lexeditor.sl2'
    save.write_bytes(b'progress')
    tweak_mods._write_runtime(tmp_path, b'', [], None)
    assert (tmp_path / 'dinput8.dll').read_bytes() == tweak_mods.loader_bytes(online=True)
    assert Ds1ModAdapter().launch_notice(tmp_path) == tweak_mods.ONLINE_NOTICE
    tweak_mods._write_runtime(tmp_path, None, [], None)
    assert tweak_mods.launch_notice(tmp_path) == ''
    assert save.read_bytes() == b'progress'


def test_existing_loader_description_is_updated_without_resetting_switch(tmp_path):
    folder = tweak_mods.ensure_loader_mod(tmp_path)
    metadata = json.loads((folder / 'mod.json').read_text())
    metadata.update(description='keeps the game offline', enabled=True, author='reader')
    (folder / 'mod.json').write_text(json.dumps(metadata))
    assert tweak_mods.ensure_loader_mod(tmp_path) == folder
    fresh = json.loads((folder / 'mod.json').read_text())
    assert fresh['enabled'] and fresh['author'] == 'reader'
    assert fresh['description'] == tweak_mods.LOADER_DESCRIPTION


@pytest.fixture(scope='module')
def saves_harness(tmp_path_factory):
    if sys.platform != 'win32':
        pytest.skip('Windows save API')
    try:
        zig = build_module().find_zig(None)
    except SystemExit:
        pytest.skip('Zig is needed for the native fixture')
    exe = tmp_path_factory.mktemp('ds1-save-fixture') / 'fixture.exe'
    subprocess.run([zig, 'cc', '-target', 'x86_64-windows-gnu', '-O1', '-municode', '-o', str(exe),
                    str(Path(__file__).with_name('runtime_saves_harness.c')),
                    str(RUNTIME / 'lexeditor_ds1_saves.c')], check=True, creationflags=FLAGS)
    return exe


def run_save(exe, vanilla, mode='read'):
    return subprocess.run([str(exe), mode, str(vanilla)], capture_output=True, text=True,
                          timeout=15, creationflags=FLAGS)


def test_native_save_routing_restart_uninstall_and_cloud_restored_copy(saves_harness, tmp_path):
    vanilla = tmp_path / 'DRAKS0005.sl2'
    modded = tmp_path / 'DRAKS0005.lexeditor.sl2'
    original = tmp_path / 'DRAKS0005.lexeditor.original.bak'
    latest = tmp_path / 'DRAKS0005.lexeditor.latest.bak'
    vanilla.write_bytes(b'vanilla-progress')
    result = run_save(saves_harness, vanilla, 'write')
    assert result.returncode == 0 and result.stdout.strip() == 'read=vanilla-progress', result
    assert vanilla.read_bytes() == original.read_bytes() == latest.read_bytes() == b'vanilla-progress'
    assert modded.read_bytes() == b'modded-progress'
    for _ in range(4):
        result = run_save(saves_harness, vanilla)
        assert result.returncode == 0 and result.stdout.strip() == 'read=modded-progress', result
    assert original.read_bytes() == b'vanilla-progress'
    assert latest.read_bytes() == b'modded-progress'
    assert sorted(p.name for p in tmp_path.glob('*.sl2')) == [modded.name, vanilla.name]
    assert len(list(tmp_path.iterdir())) == 4  # two saves, original backup, latest backup
    result = run_save(saves_harness, vanilla, 'plain')
    assert result.returncode == 0 and result.stdout.strip() == 'read=vanilla-progress', result
    # A Cloud-restored modded save is authoritative, even alongside newer vanilla progress.
    modded.write_bytes(b'cloud-progress')
    vanilla.write_bytes(b'new-vanilla-progress')
    result = run_save(saves_harness, vanilla)
    assert result.returncode == 0 and result.stdout.strip() == 'read=cloud-progress', result
    assert vanilla.read_bytes() == b'new-vanilla-progress'


def test_new_player_creates_only_a_modded_save(saves_harness, tmp_path):
    vanilla = tmp_path / 'DRAKS0005.sl2'
    result = run_save(saves_harness, vanilla, 'write')
    assert result.returncode == 0, result
    assert not vanilla.exists()
    assert (tmp_path / 'DRAKS0005.lexeditor.sl2').read_bytes() == b'modded-progress'
    assert run_save(saves_harness, vanilla).returncode == 0
    assert not vanilla.exists()


@pytest.mark.parametrize('problem', ['backup-directory', 'hardlink', 'oversize', 'staging-directory'])
def test_save_failure_never_falls_back_to_writing_vanilla(saves_harness, tmp_path, problem):
    vanilla = tmp_path / 'DRAKS0005.sl2'
    modded = tmp_path / 'DRAKS0005.lexeditor.sl2'
    vanilla.write_bytes(b'untouched')
    if problem == 'backup-directory':
        (tmp_path / 'DRAKS0005.lexeditor.latest.bak').mkdir()
    elif problem == 'staging-directory':
        (tmp_path / 'DRAKS0005.lexeditor.pending.bak').mkdir()
    elif problem == 'hardlink':
        os.link(vanilla, modded)
    else:
        with modded.open('wb') as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
    result = run_save(saves_harness, vanilla, 'write')
    assert result.returncode != 0, result
    assert vanilla.read_bytes() == b'untouched'


def test_unrelated_file_is_not_redirected(saves_harness, tmp_path):
    unrelated = tmp_path / 'other.sl2'
    unrelated.write_bytes(b'other-save')
    result = run_save(saves_harness, unrelated)
    assert result.returncode == 0 and result.stdout.strip() == 'read=other-save', result
    assert list(tmp_path.iterdir()) == [unrelated]


def test_online_loader_stops_before_starting_an_unsupported_program(saves_harness, tmp_path):
    # Existing network harness loads the shipped DLL, but it is not DSR.
    # The online loader must stop, never just leave an unprotected game running.
    import shutil
    zig = build_module().find_zig(None)
    exe = tmp_path / 'not-the-game.exe'
    subprocess.run([zig, 'cc', '-target', 'x86_64-windows-gnu', '-O1', '-o', str(exe),
                    str(Path(__file__).with_name('runtime_debug_harness.c')), '-lws2_32'], check=True,
                   creationflags=FLAGS)
    shutil.copy2(RUNTIME / 'package/online/dinput8.dll', tmp_path / 'dinput8.dll')
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15, creationflags=FLAGS)
    assert result.returncode != 0
    assert not result.stdout.strip()
    assert 'Unsupported' in (tmp_path / 'lexeditor-ds1-patch.log').read_text()
