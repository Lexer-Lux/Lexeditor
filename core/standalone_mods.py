"""Move explicitly selected standalone packages into the existing library."""
from __future__ import annotations

import errno
from pathlib import Path
import shutil
import tempfile

from core.mod_library import digest, file_tree, metadata


def adopt(source: Path, library: Path, candidates: list[dict]) -> Path:
    source, library = Path(source), Path(library)
    eligible = {Path(row['path']).absolute() for row in candidates}
    if source.absolute() not in eligible:
        raise ValueError('Choose one of the standalone mods found for this game')
    # Discovery verifies the source ancestry before resolving it. Recheck the
    # tree here so no links introduced since discovery can move with it.
    files = file_tree(source)
    info = metadata(source)
    identity = str(info.get('id') or source.name)
    library.mkdir(parents=True, exist_ok=True)
    for folder in library.iterdir():
        if folder.is_dir() and not folder.name.startswith('.'):
            try:
                other = metadata(folder)
            except (OSError, ValueError):
                continue
            if str(other.get('id') or folder.name).casefold() == identity.casefold():
                raise ValueError(f'The library already contains {info.get("name") or identity}. Nothing was moved.')
    target = library/source.name
    if target.exists() or source.resolve() == library.resolve() or source.resolve() in library.resolve().parents:
        raise ValueError('The destination must be a separate, unused mod folder')
    # The source is an explicitly discovered directory; the target stays one
    # level inside the selected library. Never pass computed paths to a shell.
    if target.resolve().parent != library.resolve():
        raise ValueError('The destination is outside the mod library')
    try:
        source.rename(target)
        return target
    except OSError as error:
        if error.errno != errno.EXDEV and getattr(error, 'winerror', None) != 17:
            raise
    expected = {str(relative): digest(source/relative) for relative in files}
    required = sum((source/relative).stat().st_size for relative in files)
    if shutil.disk_usage(library).free < required:
        raise OSError('There is not enough space to move this mod into the library')
    with tempfile.TemporaryDirectory(prefix='.lexeditor-adopt-', dir=library) as temporary:
        staged = Path(temporary)/source.name
        staged.mkdir()
        for relative in files:
            output = staged/relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source/relative, output)
        if {str(relative): digest(staged/relative) for relative in file_tree(staged)} != expected:
            raise OSError('The copied mod did not match its source; nothing was moved')
        if {str(relative): digest(source/relative) for relative in file_tree(source)} != expected:
            raise OSError('The mod changed while it was being moved; retry when its files are saved')
        staged.rename(target)
    # A verified destination exists before removing the source. Discovery
    # bounds the source to a standalone package under the game directory.
    if source.absolute() not in eligible or source.resolve().parent not in {
            Path(row['path']).resolve().parent for row in candidates}:
        raise ValueError('The standalone mod location changed during the move')
    try:
        shutil.rmtree(source)
    except OSError as error:
        raise OSError(f'The library copy is complete, but the old folder could not be removed: {source}') from error
    return target
