"""License documents belonging to a mod, independent of its game payload."""
from pathlib import Path, PurePosixPath

from core.plugin_files import is_link

MAX_FILES = 128
MAX_BYTES = 16 * 1024 * 1024


def files(root: Path) -> list[Path]:
    """Find conventional documents and validate explicit mod.json references."""
    from core import mod_metadata
    root = Path(root)
    declared = mod_metadata._stored(root).get('licenseFiles', [])
    if not isinstance(declared, list) or any(not isinstance(name, str) for name in declared):
        raise ValueError('licenseFiles must be a list of paths relative to the mod')
    names = set(declared)
    for path in root.iterdir():
        if path.name.split('.')[0].upper() in ('LICENSE', 'LICENCE', 'COPYING', 'NOTICE') and not path.is_dir():
            names.add(path.name)
    pending = [root/'licenses'] if (root/'licenses').exists() else []
    visited = 0
    while pending:
        directory = pending.pop()
        if is_link(directory) or not directory.is_dir():
            raise ValueError('The licenses folder must be a real directory')
        for path in directory.iterdir():
            visited += 1
            if visited > 1024 or is_link(path):
                raise ValueError('License documents contain a link or too many entries')
            if path.is_dir():
                pending.append(path)
            else:
                names.add(path.relative_to(root).as_posix())
    if len(names) > MAX_FILES:
        raise ValueError('A mod can carry at most 128 license documents')
    total = 0
    result = []
    for name in sorted(names):
        relative = PurePosixPath(name)
        if not name or '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name:
            raise ValueError(f'Invalid license document path: {name}')
        path = root
        for part in relative.parts:
            path = path/part
            if is_link(path):
                raise ValueError(f'License document must not use a link: {name}')
        if not path.is_file():
            raise ValueError(f'License document is missing: {name}')
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise ValueError('License documents exceed 16 MiB')
        result.append(Path(name))
    return result


def copy(root: Path, destination: Path) -> None:
    """Preserve document bytes and paths in a release without deploying them."""
    for relative in files(root):
        with (root/relative).open('rb') as source:
            data = source.read(MAX_BYTES+1)
        if len(data) > MAX_BYTES:
            raise ValueError(f'License document exceeds 16 MiB: {relative}')
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f'License document conflicts with release output: {relative}')
        target.write_bytes(data)
