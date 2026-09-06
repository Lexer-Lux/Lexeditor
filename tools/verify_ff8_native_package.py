"""Strict FFNx shipping checks, Git checkout integrity and installer smoke test.

No game is launched. Installation is exercised only inside a temporary fake
game directory, with the executable identity gate explicitly stubbed. Native
engine execution is tested separately with the private --exe regression.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import ffnx_manager, gameplay_settings
from games.ff8.ffnx_issue_51 import runtime_package
from tools.package_ff8_native_driver import NEW_DRIVER_MARKERS, SUPPORT_FILES, sections


def run() -> None:
    package = runtime_package.verify()
    root = runtime_package.PACKAGE_ROOT
    driver = (root / 'AF3DN.P').read_bytes()
    assert all(marker in driver for marker in NEW_DRIVER_MARKERS)
    assert SUPPORT_FILES <= set(sections((root / 'ISSUE51_DERIVATIVE_SOURCE.patch').read_bytes()))
    print('PASS: shipping package pins, PE exports/manifest, new native modules and full source provenance')

    # Check the actual Git smudge/checkout path, not a Python newline model.
    relative = Path('games/ff8/ffnx_issue_51/package')
    with tempfile.TemporaryDirectory(prefix='ff8-package-checkout-') as directory:
        repo = Path(directory) / 'repo'
        repo.mkdir()
        shutil.copyfile(ROOT / '.gitattributes', repo / '.gitattributes')
        shutil.copytree(root, repo / relative)
        def git(*args):
            subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
        git('init', '-q')
        git('config', 'user.name', 'Package regression')
        git('config', 'user.email', 'regression@localhost')
        git('-c', 'core.autocrlf=true', 'add', '.gitattributes', str(relative))
        git('commit', '-qm', 'byte-exact fixture')
        for mode in ('true', 'false', 'input'):
            checkout = Path(directory) / mode
            checkout.mkdir()
            git('-c', f'core.autocrlf={mode}', '--work-tree', str(checkout),
                'checkout', '-f', 'HEAD', '--', '.')
            checked = runtime_package.verify(checkout / relative)
            assert checked['driverSha256'] == package['driverSha256']
        print('PASS: real Git checkout preserves all package hashes with autocrlf=true/false/input')

    with tempfile.TemporaryDirectory(prefix='ff8-package-mutations-') as directory:
        copy = Path(directory) / 'package'
        shutil.copytree(root, copy)
        target = copy / 'AF3DN.P'
        damaged = bytearray(driver)
        damaged[-1] ^= 1
        target.write_bytes(damaged)
        # Updating the mutable manifest must not authorize a changed binary.
        manifest_file = copy / 'runtime-manifest.json'
        manifest = json.loads(manifest_file.read_text())
        manifest['driverSha256'] = hashlib.sha256(damaged).hexdigest()
        manifest_file.write_text(json.dumps(manifest))
        try:
            runtime_package.verify(copy)
        except runtime_package.RuntimePackageError:
            pass
        else:
            raise AssertionError('Manifest authorized an unreviewed DLL')
        print('PASS: changed driver plus self-updated manifest is rejected by independent pins')

    with tempfile.TemporaryDirectory(prefix='ff8-installer-smoke-') as directory:
        tmp = Path(directory)
        game, runtime = tmp / 'game', tmp / 'runtime'
        game.mkdir()
        exe = game / 'FF8_EN.exe'
        exe.write_bytes(b'non-executable installation fixture')
        (game / 'AF3DN.P').write_bytes(b'old driver fixture')
        config = game / 'FFNx.toml'
        config.write_text('fullscreen = true\ncustom_setting = "retained"\n')
        state = tmp / 'state.json'
        kwargs = dict(state_path=state, backup_root=tmp / 'backups',
                      direct_root=runtime / 'direct', game_running=lambda: False)
        with patch.object(runtime_package, 'verify_game_installation', return_value=exe):
            installed = ffnx_manager.install_derivative(game, **kwargs)
            assert installed['pinnedDerivative'] and installed['sharedMagicInventoryRuntime']
            assert (game / 'AF3DN.P').read_bytes() == driver
            assert exe.read_bytes() == b'non-executable installation fixture'
            assert (game / 'FFNx_steam_api.dll').read_bytes() == (root / 'FFNx_steam_api.dll').read_bytes()
            assert len(list((game / 'shaders').glob('*'))) == package['shaderCount']
            assert any(p.read_bytes() == b'old driver fixture' for p in (tmp / 'backups').rglob('AF3DN.P'))
            gameplay_settings._set_ffnx_runtime_tweaks(config, xp_bars=True, hp_bars=True,
                gf_hp_bars=True, better_targeting=True, party_switch=True, modern_controls=True)
            text = config.read_text()
            for marker in ('fullscreen = true', 'custom_setting = "retained"',
                           'enable_ff8_hp_bars = true', 'enable_ff8_gf_hp_bars = true',
                           'enable_ff8_party_switch = true'):
                assert marker in text, marker
            assert ffnx_manager.install_derivative(game, **kwargs)['pinnedDerivative']
            assert config.read_text() == text
            try:
                ffnx_manager.install_derivative(game, **{**kwargs, 'game_running': lambda: True})
            except RuntimeError:
                pass
            else:
                raise AssertionError('Installer modified a simulated running game')
            assert (game / 'AF3DN.P').read_bytes() == driver
        print('PASS: simulated installation upgrades/backups DLL, preserves config and assets, is repeatable, and refuses a running game')
    print('No real game installation was modified and no game process was launched.')


if __name__ == '__main__':
    run()
