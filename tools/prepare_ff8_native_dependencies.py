"""Prepare a pinned x264 Git transport overlay for the Actions FFNx build.

VideoLAN's archive endpoint can return an HTML challenge instead of source.
Read the original port from FFNx's exact vcpkg baseline, retain its patches and
package metadata, and fetch the same x264 commit through Git instead.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess

BASELINE = 'c3867e714dd3a51c272826eea77267876517ed99'
X264_REF = '31e19f92f00c7003fa115047ce50978bc98c3a0d'
ARCHIVE_SHA512 = (
    '707ff486677a1b5502d6d8faa588e7a03b0dee45491c5cba89341be4be23d3f2e'
    '48272c3b11d54cfc7be1b8bf4a3dfc3c3bb6d9643a6b5a2ed77539c85ecf294'
)


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def git_transport(port: bytes) -> bytes:
    text = port.decode('utf-8')
    anchors = {
        f'set(ref {X264_REF})': f'set(ref {X264_REF})',
        'vcpkg_from_gitlab(': 'vcpkg_from_git(',
        '    GITLAB_URL https://code.videolan.org/\n':
            '    URL https://code.videolan.org/videolan/x264.git\n',
        '    REPO videolan/x264\n': '',
        f'    SHA512 {ARCHIVE_SHA512}\n': '',
        '    REF "${ref}"': '    REF "${ref}"',
        '    HEAD_REF master': '    HEAD_REF master',
        '    PATCHES\n': '    PATCHES\n',
    }
    for old in anchors:
        if text.count(old) != 1:
            raise ValueError(f'Unexpected pinned x264 port: {old.strip()}')
    for old, new in anchors.items():
        text = text.replace(old, new)
    return text.encode('utf-8')


def prepare(ffnx: Path, overlay: Path, provenance: Path) -> None:
    manifest = json.loads((ffnx / 'vcpkg.json').read_text(encoding='utf-8'))
    if manifest.get('builtin-baseline') != BASELINE:
        raise ValueError('Unexpected FFNx vcpkg baseline')
    target = overlay / 'x264'
    if target.exists() or provenance.exists():
        raise ValueError('Dependency overlay/provenance must be a new output')
    repo = ffnx / 'vcpkg'
    try:
        git(repo, 'cat-file', '-e', f'{BASELINE}^{{commit}}')
    except subprocess.CalledProcessError:
        git(repo, 'fetch', '--depth=1', 'origin', BASELINE)
    files = {}
    for entry in git(repo, 'ls-tree', '-rz', f'{BASELINE}:ports/x264').split(b'\0'):
        if not entry:
            continue
        header, raw_name = entry.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        path = PurePosixPath(name)
        if (header.split()[0] != b'100644' or path.is_absolute()
                or '..' in path.parts or '\\' in name or ':' in name):
            raise ValueError(f'Unexpected x264 port file: {name}')
        files[name] = git(repo, 'show', f'{BASELINE}:ports/x264/{name}')
    metadata = json.loads(files['vcpkg.json'])
    if (metadata.get('name'), metadata.get('version'), metadata.get('port-version')) != (
            'x264', '0.164.3108', 2):
        raise ValueError('Unexpected x264 package version')
    required = {'version.diff.in', 'uwp-cflags.patch', 'parallel-install.patch',
                'allow-clang-cl.patch', 'configure.patch'}
    if not required.issubset(files):
        raise ValueError('Incomplete pinned x264 patch set')
    files['portfile.cmake'] = git_transport(files['portfile.cmake'])
    # No output is created until all inputs have passed validation.
    target.mkdir(parents=True)
    for name, content in files.items():
        output = target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(
        f'vcpkg baseline: {BASELINE}\n'
        f'x264: 0.164.3108#2; source commit: {X264_REF}\n'
        'Transport: https://code.videolan.org/videolan/x264.git\n'
        'Original port metadata and patches retained; only archive transport replaced.\n',
        encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ffnx', type=Path)
    parser.add_argument('--overlay', required=True, type=Path)
    parser.add_argument('--provenance', required=True, type=Path)
    args = parser.parse_args()
    prepare(args.ffnx, args.overlay, args.provenance)
