"""Files consumed by build/load paths, independent of archive composition."""
from pathlib import Path


def loaded_files(folder: Path):
    """Mod-folder-relative consumed files, casefolded for the shared Files tab."""
    from . import mod_loader
    from .tweak_mods import checked
    folder = checked(Path(folder))
    try:
        pairs = mod_loader.content_files(folder, folder.name)
    except (ValueError, OSError):
        pairs = []
    found = {'mod.json'} if (folder/'mod.json').is_file() else set()
    for _key, disk in pairs:
        try:
            found.add(disk.relative_to(folder).as_posix().casefold())
        except ValueError:
            continue
    try:
        from core import script_mods
        from .tweak_mods import BUILT_FOLDERS, built_files
        scripted = script_mods.is_script_mod(folder)
        if scripted:
            for relative in script_mods.consumed_files(folder):
                found.add(relative.as_posix().casefold())
            if checked(folder/script_mods.MANIFEST_FILE).is_file():
                found.add(script_mods.MANIFEST_FILE)
        from . import native_rules, native_support
        if (folder/native_rules.SETTINGS_FILE).is_file():
            found.add(native_rules.SETTINGS_FILE.casefold())
        if scripted or (folder/'runtime.lxd').is_file() or (folder/native_support.FOLDER).is_dir():
            for kind in BUILT_FOLDERS if scripted else BUILT_FOLDERS[1:]:
                for path in built_files(folder,kind):
                    found.add(path.relative_to(folder).as_posix().casefold())
    except (OSError, ValueError):
        pass
    try:
        if checked(folder/'runtime.lxd').is_file():
            found.add('runtime.lxd')
    except (OSError,ValueError):
        pass
    return sorted(found)
