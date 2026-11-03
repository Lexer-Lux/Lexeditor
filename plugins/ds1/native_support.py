"""Mod-owned support linked beside prebuilt modules by the shared runtime.

Saved editor properties are source; their stamped support file is generated
output. Standalone loading validates that output without running a builder.
"""
from pathlib import Path
import json

from core.plugin_files import atomic_write
from . import exe_patches

FOLDER = 'native-support'
RULES_FILE = Path(FOLDER)/'native-rules.json'


def rules_output(folder, original):
    from . import native_rules
    source = native_rules._read_optional(Path(folder)/native_rules.SETTINGS_FILE,native_rules.SETTINGS_LIMIT)
    if source is None:
        return None
    value = native_rules.decode_settings(source)
    spec = native_rules.patch_spec(original,value)
    return (json.dumps({**spec,'sourceHash':native_rules.digest(source)},indent=2,allow_nan=False)+'\n').encode()


def validate(spec, owner):
    from .tweak_mods import _digest
    if type(spec) is not dict:
        raise ValueError(f'{owner}: invalid native support component')
    if 'sourceHash' in spec and not _digest(spec['sourceHash']):
        raise ValueError(f'{owner}: invalid native property source stamp')
    return exe_patches.validate(spec,owner)


def owns_project(project, libraries):
    """Whether ordinary library activation supersedes an old global recipe."""
    if not project:
        return False
    from . import native_rules, tweak_mods
    folder = tweak_mods.checked(Path(project['path']))
    return (folder.resolve().parent in {Path(root).resolve() for root in libraries}
            and (folder/'mod.json').is_file() and (folder/native_rules.SETTINGS_FILE).is_file())


def check_source(folder, path, raw):
    """A stamped property artifact must match its saved source, even standalone."""
    from . import native_rules
    if Path(path) != RULES_FILE or 'sourceHash' not in raw:
        return
    source = native_rules._read_optional(Path(folder)/native_rules.SETTINGS_FILE,native_rules.SETTINGS_LIMIT)
    if source is None or native_rules.digest(source) != raw['sourceHash']:
        raise ValueError('Native properties changed or are missing; rebuild this mod before loading it')
    native_rules.decode_settings(source)


def require_built_rules(folder):
    from . import native_rules, tweak_mods
    folder = Path(folder)
    source = tweak_mods.checked(folder/native_rules.SETTINGS_FILE)
    target = tweak_mods.checked(folder/RULES_FILE)
    if source.exists() and not target.is_file():
        raise ValueError('Built native properties are missing; rebuild this mod before loading it')


def build_sources(rows, original):
    from . import tweak_mods
    for row in rows:
        folder = Path(row['path'])
        try:
            output = rules_output(folder,original)
            if output is not None:
                target = tweak_mods.checked(folder/RULES_FILE)
                target.parent.mkdir(parents=True,exist_ok=True)
                before = None
                if target.is_file():
                    with target.open('rb') as stream:
                        before = stream.read(len(output)+1)
                if before != output:
                    atomic_write(target,output)
        except (ValueError,OSError) as error:
            raise tweak_mods.TweakError(f"{row['name']}: {error}",folders=[folder]) from error


def specs(rows):
    from . import tweak_mods
    result = tweak_mods._built(rows,FOLDER,validate)
    for spec in result:
        spec['shared'] = True
    return result
