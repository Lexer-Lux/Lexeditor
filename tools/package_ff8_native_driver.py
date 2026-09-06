"""Package an explicitly reviewed FFNx build; never touch a game installation.

The caller must supply the driver digest and source revision of the reviewed
Actions artifact. Reconstruct source from the pinned FFNx base, check that the
candidate's compilation inputs match, and run its linked-binary verifier before
updating the package, manifest, and independent hash lock as one Git change.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_ff8_native_build import BASE, prepare
from tools.verify_ff8_linked_runtime import verify as verify_linked
from games.ff8.ffnx_issue_51 import runtime_package

SUPPORT_FILES = {
    'tests/lexeditor_live_conditions_test.cpp',
    'tests/lexeditor_shared_magic_config_test.cpp',
    'tools/verify_issue51_runtime_artifact.py',
    'tools/verify_issue51_shared_magic_runtime.py',
    'verify-issue51-build.ps1',
}
NEW_DRIVER_MARKERS = (
    b'enable_ff8_gf_hp_bars', b'enable_ff8_party_switch',
    b'enable_ff8_no_magic_consumption', b'lexeditor_ff8_shared_party_contract_version',
    b'lexeditor_ff8_no_consume_battle_debit',
    b'Party Switch: slot %d, character %d -> %d; retiring old model.',
    b'Party Switch: slot %d %s; ATB %u.',
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sections(patch: bytes) -> dict[str, str]:
    text = patch.decode('utf-8').replace('\r\n', '\n')
    require(text.startswith('diff --git '), 'Not a Git source patch')
    result = {}
    for part in text.split('diff --git ')[1:]:
        header, _, body = part.partition('\n')
        match = re.fullmatch(r'a/(\S+) b/\1', header)
        require(match is not None, f'Unexpected patch path: {header}')
        name = match[1]
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                f'Unsafe patch path: {name}')
        require(name not in result, f'Duplicate patch path: {name}')
        result[name] = body
    return result


def verify_compilation_patch(candidate: bytes, complete: bytes) -> None:
    """Allow only restoration of the five support files omitted by old helper."""
    actual, expected = sections(candidate), sections(complete)
    require(set(actual) <= set(expected), 'Candidate patch has unexpected files')
    require(set(expected) - set(actual) <= SUPPORT_FILES,
            'Candidate patch is missing production source')
    for name, body in actual.items():
        require(body == expected[name], f'Candidate compiled different source: {name}')
    require(SUPPORT_FILES <= set(expected), 'Full provenance is missing build/test support')


def package(candidate: Path, ffnx_source: Path, *, driver_sha256: str,
            build_revision: str, build_run: int) -> dict:
    candidate = candidate.resolve()
    require(re.fullmatch(r'[0-9a-f]{64}', driver_sha256) is not None,
            'An explicit reviewed driver SHA-256 is required')
    require(re.fullmatch(r'[0-9a-f]{40}', build_revision) is not None and build_run > 0,
            'A reviewed source revision and Actions run are required')
    driver = candidate / 'AF3DN.P'
    require(sha256(driver) == driver_sha256, 'Candidate does not match reviewed driver digest')
    build = (candidate / 'BUILD.txt').read_text(encoding='utf-8-sig')
    require(f'Editor source: {build_revision}' in build and f'FFNx source: {BASE}' in build,
            'Build receipt does not match requested source revisions')
    require(sha256(candidate / 'FFNx.pdb') != hashlib.sha256(b'').hexdigest(), 'Empty build symbols')
    old_root = ROOT / 'games/ff8/ffnx_issue_51/package'
    licence = old_root / 'COPYING.TXT'
    require(licence.read_bytes().replace(b'\r\n', b'\n') ==
            (candidate / 'LICENSE').read_bytes().replace(b'\r\n', b'\n'),
            'Candidate licence changed beyond line endings')
    require('games/ff8/ffnx_issue_51/package/** -text' in
            (ROOT / '.gitattributes').read_text(), 'Pinned package lacks byte-preserving Git attributes')

    with tempfile.TemporaryDirectory(prefix='ff8-package-') as folder:
        work = Path(folder)
        complete_patch = work / 'ISSUE51_DERIVATIVE_SOURCE.patch'
        prepare(ffnx_source, complete_patch)
        verify_compilation_patch((candidate / complete_patch.name).read_bytes(), complete_patch.read_bytes())
        verify_linked(ffnx_source / 'tools/verify_issue51_runtime_artifact.py', driver)
        image, _ = runtime_package._pe_exports(driver)
        runtime_package._reject_unloadable_manifest(image)
        require(all(marker in image for marker in NEW_DRIVER_MARKERS),
                'Candidate lacks the newly compiled GF bar / model retirement modules')
        stage = work / 'package'
        shutil.copytree(old_root, stage)
        shutil.copyfile(driver, stage / 'AF3DN.P')
        shutil.copyfile(complete_patch, stage / complete_patch.name)
        manifest = json.loads((stage / 'runtime-manifest.json').read_text())
        patch_hash = sha256(complete_patch)
        # Keep the historical pinned licence bytes (CRLF) and include it in
        # this commit. An attributes-only change does not necessarily rewrite
        # an existing Windows checkout's previously converted licence file.
        (stage / 'COPYING.TXT').write_bytes(
            licence.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        licence_hash = sha256(stage / 'COPYING.TXT')
        shader_files = sorted((stage / 'shaders').glob('*'))
        shader_files = [p for p in shader_files if p.is_file()]
        shader_digest = hashlib.sha256(''.join(
            f'{p.name} {sha256(p)}\n' for p in shader_files).encode()).hexdigest()
        recovery = ('The original run compiled and linked successfully, but licence '
                    'staging used the wrong filename. The archived DLL/PDB and '
                    'CMake cache were recovered without changing the binary; all '
                    'linked-artifact and package checks were rerun before publication.'
                    if 'Recovered from' in build else '')
        report = f'''# Lexeditor FFNx battle repair build

## Artifact and source

- FFNx base: `{BASE}`
- Editor build revision: `{build_revision}`
- Actions build run: `{build_run}`
- Supported private game SHA-256: `{runtime_package.SUPPORTED_GAME_SHA256}`
- Identity: `{manifest['identity']}`
- Driver SHA-256: `{driver_sha256}`
- Driver size: {driver.stat().st_size} bytes; PE32 x86 DLL
- PDB SHA-256: `{sha256(candidate / 'FFNx.pdb')}` (build artifact, not installed)
- Complete source patch SHA-256: `{patch_hash}`
- GPL licence SHA-256: `{licence_hash}`
- Steamworks library unchanged: `{sha256(stage / runtime_package.STEAM_API_NAME)}`
- Existing matching-base shader set retained: {len(shader_files)} files;
  sorted filename/hash-list SHA-256 `{shader_digest}`.

{recovery}

## Changes

Party Switch retires the outgoing model through native event 69 before event
66 loads its replacement. Native saved/kernel names are resolved and measured
before drawing. Cancellation keeps the turn; invalidated reserves reload the
original character; the HUD cache is refreshed after a completed replacement.
Red HP bars use row y+14, not padded glyph dimensions. The independent blue
GF HP bar uses row y+1, fills left-to-right, and uses live charging HP rather
than stale saved HP. Existing XP, targeting, startup and modern-controls code
is retained. Party Switch explicitly relinquishes and re-registers the replaced
actor's shared-stock mirror, rather than copying its private record over the
canonical pool. Shared Magic works with the configured stock cap (1–255);
lossless migration refuses overflow. No Magic Consumption hooks only field and
battle spell-cast debits, never the shared Item debit path. Drops After Mug is
a separate guarded one-byte Hext change, retaining Mug-once and reward-once checks.

## Build reproduction

Use the exact FFNx base and its pinned vcpkg submodule. Apply the complete
`ISSUE51_DERIVATIVE_SOURCE.patch`. The build uses MSVC x86 on the
`windows-2025-vs2026` runner, CMake 4.2.0, Ninja, Release, and the
`x86-windows-static` triplet with `VCPKG_BUILD_TYPE release`.
Configure with `FFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON`,
`FFNX_LEXEDITOR_LIVE_CONDITIONS=ON`, and `FFNX_DEPLOY_TO_GAME_DIRS=OFF`,
then run `cmake --build .build --parallel 4`.
The full command sequence is in `.github/workflows/native-dependencies.yml`.
The complete patch restores test/verifier support omitted by the earlier
preparation helper; every candidate patch section was compared unchanged.
No production compilation inputs differ from the reviewed build artifact.
Pinned package files are marked `-text` to prevent checkout newline conversion.

## Validation boundary

The linked artifact verifier passed, including its eleven mutation controls,
and the PE architecture, embedded XML manifest and new runtime markers were
checked before packaging. Repository regressions cover all 255 stock caps and three party slots with
repeated swaps, concurrent Draw/cast, canonical save/reload and cancellation.
The linked no-consumption register-ABI hook is executed for all 256 stock values.
Repository regressions also exercise compiled production
policy/render code and configuration serialization. The private executable
checks exercise native name resolution and model retirement/loading with
resource I/O stubbed. None of these is a live-game or visual acceptance test.
No game executable or private battle capture is distributed or installed by
this packaging command. This report does not claim in-game acceptance.
'''
        (stage / 'ISSUE51_BUILD_REPORT.md').write_text(report, encoding='utf-8', newline='\n')
        hashes = {'driver': driver_sha256, 'license': licence_hash,
                  'sourcePatch': patch_hash, 'buildReport': sha256(stage / 'ISSUE51_BUILD_REPORT.md')}
        manifest['driverSha256'] = driver_sha256
        manifest['exports'] = sorted(runtime_package.REQUIRED_EXPORTS)
        for key in ('license', 'sourcePatch', 'buildReport'):
            manifest['provenance'][key + 'Sha256'] = hashes[key]
        (stage / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        verifier = ROOT / 'games/ff8/ffnx_issue_51/runtime_package.py'
        code = verifier.read_text(encoding='utf-8')
        for key, digest in hashes.items():
            code, count = re.subn(r'("' + key + r'": ")[0-9a-f]{64}("[ ,\n])',
                                 lambda m: m[1] + digest + m[2], code)
            require(count == 1, f'Expected one independent artifact pin for {key}')
        staged_verifier = work / 'runtime_package.py'
        staged_verifier.write_text(code, encoding='utf-8')
        spec = importlib.util.spec_from_file_location('reviewed_ff8_package', staged_verifier)
        reviewed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reviewed)
        checked = reviewed.verify(stage)
        require(checked['driverSha256'] == driver_sha256, 'Staged package was not validated')
        outputs = {old_root / name: (stage / name).read_bytes() for name in (
            'AF3DN.P', 'COPYING.TXT', 'ISSUE51_DERIVATIVE_SOURCE.patch', 'ISSUE51_BUILD_REPORT.md', 'runtime-manifest.json')}
        outputs[verifier] = code.encode('utf-8')
        before = {p: p.read_bytes() for p in outputs}
        try:
            for path, content in outputs.items():
                path.write_bytes(content)
        except Exception:
            for path, content in before.items():
                path.write_bytes(content)
            raise
        return {'driverSha256': driver_sha256, 'hashes': hashes,
                'paths': [str(p.relative_to(ROOT)).replace('\\', '/') for p in outputs]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--ffnx-source', type=Path, required=True)
    parser.add_argument('--driver-sha256', required=True)
    parser.add_argument('--build-revision', required=True)
    parser.add_argument('--build-run', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.candidate, args.ffnx_source, driver_sha256=args.driver_sha256,
                             build_revision=args.build_revision, build_run=args.build_run), indent=2))
