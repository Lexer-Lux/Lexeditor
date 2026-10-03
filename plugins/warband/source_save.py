"""Publish a Module System source and its bounded latest-source backup."""
import json
import os
from pathlib import Path
import tempfile
import threading


_LOCK = threading.Lock()


def publish_source(path, encoded, expected, *, additional_outputs=()):
    """Stage source, backup and optional guarded metadata before publication."""
    path = Path(path)
    backup = path.with_name(path.name + ".lexeditor.bak")
    folder = path.parent / (".lexeditor-save-recovery-" + path.name)
    outputs = {backup: expected, path: encoded}
    expected_outputs = {path: expected}
    for target, data, previous in additional_outputs:
        target = Path(target)
        if target.resolve() in {other.resolve() for other in outputs}:
            raise ValueError("Source save outputs must have distinct paths")
        outputs[target] = data
        expected_outputs[target] = previous
    with _LOCK:
        for parent in {target.parent for target in outputs}:
            pending = next(parent.glob(".lexeditor-save-recovery-*"), None)
            if pending is not None:
                raise OSError(f"Save blocked by unresolved recovery at {pending}; restore the recorded original state before saving again")
        original = {target: target.read_bytes() if target.exists() else None for target in outputs}
        for target, previous in expected_outputs.items():
            if original[target] != previous:
                raise ValueError(f"{target.name} changed while validating; reload before saving")
        timestamps = {target: (target.stat().st_atime_ns, target.stat().st_mtime_ns)
                      for target, data in original.items() if data is not None}
        temporary, committed = [], []
        recovery_created = False
        retain_recovery = False

        def stage(target, data):
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix="." + target.name + ".",
                                             suffix=".tmp", delete=False) as stream:
                staged = Path(stream.name)
                temporary.append(staged)
                stream.write(data)
            return staged

        def current(target):
            return target.read_bytes() if target.exists() else None

        try:
            staged = {target: stage(target, data) for target, data in outputs.items()}
            folder.mkdir()
            recovery_created = True
            (folder / "state.json").write_text(json.dumps({
                "files": [{"target": str(target.resolve()), "existed": original[target] is not None,
                           "original": str(index) if original[target] is not None else None,
                           "timestamps": timestamps.get(target)}
                          for index, target in enumerate(outputs)]
            }), encoding="utf-8")
            for index, target in enumerate(outputs):
                if original[target] is not None:
                    (folder / str(index)).write_bytes(original[target])
            # Guard the complete batch before publication, then each output again.
            for target in outputs:
                if current(target) != original[target]:
                    raise ValueError(f"{target.name} changed during save; reload before saving")
            for target, candidate in staged.items():
                if current(target) != original[target]:
                    raise ValueError(f"{target.name} changed during save; reload before saving")
                os.replace(candidate, target)
                committed.append(target)
        except Exception as error:
            failures = []
            for target in reversed(committed):
                try:
                    if current(target) != outputs[target]:
                        raise OSError("File changed externally after publication; rollback cannot overwrite it")
                    if original[target] is None:
                        target.unlink()
                    else:
                        os.replace(stage(target, original[target]), target)
                        os.utime(target, ns=timestamps[target])
                except Exception as rollback_error:
                    retain_recovery = True
                    failures.append(f"{target.name}: {rollback_error}")
            if failures:
                raise RuntimeError(f"Source save failed: {error}; rollback failed: {'; '.join(failures)}; original state retained at {folder}") from error
            raise
        finally:
            if recovery_created and not retain_recovery:
                for name in (*map(str, range(len(outputs))), "state.json"):
                    (folder / name).unlink(missing_ok=True)
                folder.rmdir()
            for staged in temporary:
                staged.unlink(missing_ok=True)
    return backup
