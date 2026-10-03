"""Publish a Module System source and its bounded latest-source backup."""
import json
import os
from pathlib import Path
import tempfile
import threading


_LOCK = threading.Lock()


def publish_source(path, encoded, expected):
    """Stage both outputs and retain recovery originals if rollback fails."""
    path = Path(path)
    backup = path.with_name(path.name + ".lexeditor.bak")
    folder = path.parent / (".lexeditor-save-recovery-" + path.name)
    outputs = {backup: expected, path: encoded}
    with _LOCK:
        if folder.exists():
            raise OSError(f"Save blocked by unresolved recovery at {folder}; restore the recorded original state before saving again")
        original = {target: target.read_bytes() if target.exists() else None for target in outputs}
        if original[path] != expected:
            raise ValueError(f"{path.name} changed while validating; reload before saving")
        timestamps = {target: (target.stat().st_atime_ns, target.stat().st_mtime_ns)
                      for target, data in original.items() if data is not None}
        temporary, committed = [], []
        recovery_created = False
        retain_recovery = False

        def stage(target, data):
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + target.name + ".",
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
            # Guard the complete pair before publication, then each output again.
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
                for name in ("0", "1", "state.json"):
                    (folder / name).unlink(missing_ok=True)
                folder.rmdir()
            for staged in temporary:
                staged.unlink(missing_ok=True)
    return backup
