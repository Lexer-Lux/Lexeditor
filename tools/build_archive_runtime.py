"""Build the offline libarchive DLL on CI with only permissively licensed codecs."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

LIBARCHIVE = '03036ffa409a2aa1c5bbad35be2202641a040fda'  # upstream v3.8.11
VCPKG = 'd4bf063aa46ab095f6e04ae96ebf18c79980a8f5'
CODECS = ('zlib', 'bzip2', 'liblzma', 'lz4', 'zstd')


def run(*args, cwd=None):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def build(output):
    if os.name != 'nt' or os.environ.get('CI') != 'true':
        raise RuntimeError('Build this helper using the remote Build archive reader workflow')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-archive-build-') as temporary:
        root = Path(temporary)
        vcpkg, source, build_dir = root/'vcpkg', root/'libarchive', root/'build'
        for url, commit, destination in (
                ('https://github.com/microsoft/vcpkg.git', VCPKG, vcpkg),
                ('https://github.com/libarchive/libarchive.git', LIBARCHIVE, source)):
            run('git', 'init', destination)
            run('git', 'remote', 'add', 'origin', url, cwd=destination)
            run('git', 'fetch', '--depth', '1', 'origin', commit, cwd=destination)
            run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=destination)
        run(vcpkg/'bootstrap-vcpkg.bat', '-disableMetrics')
        run(vcpkg/'vcpkg.exe', 'install', *(name+':x64-windows-static' for name in CODECS))
        run('cmake', '-S', source, '-B', build_dir, '-A', 'x64',
            '-DCMAKE_TOOLCHAIN_FILE='+str(vcpkg/'scripts/buildsystems/vcpkg.cmake'),
            '-DVCPKG_TARGET_TRIPLET=x64-windows-static',
            '-DBUILD_SHARED_LIBS=ON', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
            '-DENABLE_OPENSSL=OFF', '-DENABLE_LIBB2=OFF', '-DENABLE_LIBXML2=OFF',
            '-DENABLE_EXPAT=OFF', '-DENABLE_ICONV=OFF', '-DENABLE_CNG=ON',
            '-DENABLE_TEST=OFF', '-DENABLE_TAR=OFF', '-DENABLE_CPIO=OFF',
            '-DENABLE_CAT=OFF', '-DENABLE_UNZIP=OFF', '-DENABLE_INSTALL=OFF')
        run('cmake', '--build', build_dir, '--config', 'Release', '--target', 'archive', '--parallel', '2')
        libraries = list(build_dir.rglob('archive.dll')) + list(build_dir.rglob('libarchive.dll'))
        if len(libraries) != 1:
            raise RuntimeError('Expected exactly one built archive DLL: '+str(libraries))
        dll = output/'libarchive.dll'
        shutil.copyfile(libraries[0], dll)
        loaded = ctypes.CDLL(str(dll))
        loaded.archive_version_details.restype = ctypes.c_char_p
        version = loaded.archive_version_details().decode('utf-8')
        if '3.8.11' not in version or any(name in version.lower() for name in ('openssl', 'iconv', 'libxml')):
            raise RuntimeError('Unexpected archive runtime build: '+version)
        licenses = output/'licenses'
        licenses.mkdir(exist_ok=True)
        shutil.copyfile(source/'COPYING', licenses/'libarchive.txt')
        share = vcpkg/'installed/x64-windows-static/share'
        for name in CODECS:
            shutil.copyfile(share/name/'copyright', licenses/(name+'.txt'))
        manifest = {'version':'3.8.11', 'details':version, 'upstream':LIBARCHIVE,
                    'vcpkg':VCPKG, 'sha256':hashlib.sha256(dll.read_bytes()).hexdigest(),
                    'packages':subprocess.check_output([str(vcpkg/'vcpkg.exe'),'list'], text=True)}
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
