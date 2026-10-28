"""Isolate identified mod failures when building and deploying mods."""
from pathlib import Path

class ModBuildError(ValueError):
    """A mod-owned failure, raised only before deployment or after rollback."""

    def __init__(self, folders, detail: str):
        self.folders = tuple(Path(folder).resolve() for folder in folders)
        self.detail = str(detail)
        super().__init__(self.detail)


def activate_with_recovery(adapter, mods: list[Path], game_root: Path) -> dict:
    """Disable failed mods and their dependents, then install the remaining set.

    Unattributed failures still stop deployment. No exception message parsing,
    stale payload reuse, or retry without removing an identified failed mod.
    """
    from core import mod_requires, mods_service
    active = [Path(folder).resolve() for folder in mods]
    identities = {}
    for folder in active:
        try:
            identities[folder] = (mod_requires.mod_id(folder), mod_requires.display_name(folder))
        except (OSError, ValueError):
            identities[folder] = (folder.name, folder.name)
    disabled = []
    while True:
        try:
            result = adapter.activate(active, game_root)
            return {**(result or {}), "disabledMods": disabled}
        except ModBuildError as error:
            failed = set(error.folders)
            if not failed or not failed <= set(active):
                raise
            removed = set(failed)
            while True:
                ids = {identities[folder][0] for folder in removed}
                dependents = set()
                for folder in active:
                    if folder in removed:
                        continue
                    try:
                        required = mod_requires.needs(folder)
                    except (OSError, ValueError):
                        # Its own invalid requirement will be attributed on the
                        # next preparation, rather than hiding this failure.
                        continue
                    if ids.intersection(required):
                        dependents.add(folder)
                if not dependents:
                    break
                removed.update(dependents)
            for folder in active:
                if folder in removed:
                    try:
                        mods_service.set_enabled(folder, False)
                    except ValueError:
                        # Unreadable metadata is already an off/error library
                        # row. Preserve it for repair instead of overwriting it.
                        row = mods_service.mod_row(folder)
                        if row.get('enabled') or not row.get('error'):
                            raise
                    disabled.append({"folder": folder.name,
                                     "name": identities[folder][1],
                                     "error": error.detail if folder in failed else
                                     "A required mod could not be built."})
            active = [folder for folder in active if folder not in removed]
