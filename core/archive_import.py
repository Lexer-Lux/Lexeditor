"""Offline archive decoding with the same bounded, contained import rules for every format."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil

ARCHIVE_EXTENSIONS = ('.zip', '.zipx', '.rar', '.7z', '.tar', '.tar.gz', '.tgz',
                      '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.tar.zst', '.tzst',
                      '.cab', '.lha', '.lzh', '.xar', '.cpio', '.ar', '.ctp')
RUNTIME = Path(__file__).resolve().parents[1] / 'assets/helpers/libarchive'


@lru_cache(maxsize=1)
def reader():
    if os.name == 'nt':
        dll = RUNTIME/'libarchive.dll'
        manifest = json.loads((RUNTIME/'manifest.json').read_text(encoding='utf-8'))
        if hashlib.sha256(dll.read_bytes()).hexdigest() != manifest['sha256']:
            raise ValueError('The archive reader is damaged; repair Lexeditor to import archives')
        os.environ['LIBARCHIVE'] = str(dll)
    import libarchive
    return libarchive.file_reader


def extract(source: Path, destination: Path, *, max_files: int, max_bytes: int, allow_executables=False):
    from core.mod_library import relative_path
    seen, count, written, declared = set(), 0, 0, 0
    available = shutil.disk_usage(destination).free
    try:
        with reader()(str(source)) as archive:
            for entry in archive:
                count += 1
                if count > max_files:
                    raise ValueError('The archive exceeds the import file limit')
                if entry.issym or entry.islnk or not (entry.isdir or entry.isfile or entry.filetype == 0):
                    raise ValueError('Archive links and special files cannot be imported')
                name = entry.pathname
                if not isinstance(name, str):
                    raise ValueError('An archive entry has an invalid file name')
                while name.startswith('./'):
                    name = name[2:]
                if name.rstrip('/') in ('', '.') and entry.isdir:
                    continue
                relative = relative_path(name.rstrip('/'))
                key = relative.as_posix().casefold()
                if key in seen:
                    raise ValueError(f'Duplicate path in archive: {relative}')
                seen.add(key)
                # Executables are never written into an import staging area:
                # game executables remain read-only, including scratch copies.
                if not allow_executables and relative.suffix.casefold() == '.exe':
                    raise ValueError(f'{relative}: executable installers are not imported as mods')
                size = entry.size
                if size is not None:
                    if size < 0:
                        raise ValueError('An archive entry has an invalid size')
                    declared += size
                    if declared > max_bytes:
                        raise ValueError('The archive exceeds the import size limit')
                    if declared > available:
                        raise OSError('There is not enough space to open this archive')
                target = destination / relative
                if entry.isdir:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                actual = 0
                with target.open('xb') as output:
                    for block in entry.get_blocks():
                        actual += len(block)
                        written += len(block)
                        if written > max_bytes or size is not None and actual > size:
                            raise ValueError('The archive exceeds its declared import size')
                        if written > available:
                            raise OSError('There is not enough space to open this archive')
                        output.write(block)
                if size is not None and actual != size:
                    raise ValueError(f'{relative}: archive data is incomplete')
    except (ValueError, OSError):
        raise
    except Exception as error:
        detail = getattr(error, 'msg', str(error))
        raise ValueError(f'Could not open {source.name}: {detail}') from error
