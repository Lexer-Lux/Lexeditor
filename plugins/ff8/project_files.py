"""Stage and publish a related set of FF8 mod files with bounded recovery."""
import json
import os
from pathlib import Path
import shutil
import tempfile


def atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix='.ff8-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def commit_files(project, pending, original, *, label, recovery_name,
                 source_guards=(), write=atomic_write):
    project = Path(project).resolve()
    if len(pending) != len(original) or not pending:
        raise ValueError('Publication requires matching, nonempty prepared files and snapshots')
    targets = [Path(path).resolve() for path, _ in pending]
    if len(set(targets)) != len(targets):
        raise ValueError('Publication targets must be distinct')
    for path in targets:
        path.relative_to(project)
    stage = project / recovery_name
    if stage.resolve().parent != project:
        raise ValueError('Recovery must be a direct child of the selected project')
    project.mkdir(parents=True, exist_ok=True)
    try:
        stage.mkdir()
    except FileExistsError as error:
        raise OSError(f'{label} save has pending recovery at {stage}; resolve it before saving again') from error
    retain, installed = False, []
    timestamps = {}

    def current(path):
        return path.read_bytes() if path.exists() else None

    def guard_sources():
        owned = {targets[index] for index in installed}
        for path, expected in source_guards:
            if Path(path).resolve() not in owned and current(Path(path)) != expected:
                raise ValueError(f'{label} source changed during save; reload before retrying')

    try:
        timestamps.update({path: (path.stat().st_atime_ns, path.stat().st_mtime_ns)
                           for path, before in original if before is not None and path.exists()})
        records = []
        for index, ((path, value), (old_path, before)) in enumerate(zip(pending, original)):
            if path != old_path:
                raise ValueError('Prepared file does not match its original snapshot')
            records.append({'path': path.resolve().relative_to(project).as_posix(),
                            'before': None if before is None else f'{index}.before',
                            'timestamps': timestamps.get(path)})
            if before is not None:
                (stage / f'{index}.before').write_bytes(before)
            (stage / f'{index}.after').write_bytes(value)
        (stage / 'files.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        guard_sources()
        for path, before in original:
            if current(path) != before:
                raise ValueError(f'{label} files changed during save; reload before retrying')
        try:
            for index, (path, value) in enumerate(pending):
                guard_sources()
                if current(path) != original[index][1]:
                    raise ValueError(f'{label} files changed during save; reload before retrying')
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / f'{index}.after', path)
                installed.append(index)
        except Exception as save_error:
            failures = []
            for index in reversed(installed):
                path, value = pending[index]
                before = original[index][1]
                try:
                    if current(path) != value:
                        raise OSError('File changed after installation; refusing to overwrite it')
                    if before is None:
                        path.unlink()
                    else:
                        write(path, before)
                        os.utime(path, ns=timestamps[path])
                except Exception as error:
                    failures.append(str(error))
            if failures:
                retain = True
                raise OSError(f'{label} save and restore failed. Originals are retained at {stage}') from save_error
            raise
    finally:
        if not retain:
            assert stage.resolve().parent == project
            shutil.rmtree(stage)
