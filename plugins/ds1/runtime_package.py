"""Package the standalone loader with a private, prebuilt Python runtime.

This is an author utility. Players extract the result; no Python installation,
compiler, pip, builder scripts, or editor interface is needed on their machine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SKIP_LIB = frozenset({'site-packages','test','tests','tkinter','idlelib','turtledemo','ensurepip','venv','__pycache__'})


def inputs():
    if os.name != 'nt':
        raise ValueError('Build the Windows loader package on Windows')
    python = Path(sys.base_prefix)
    version = f'{sys.version_info.major}{sys.version_info.minor}'
    binaries = [(python/name,Path(name)) for name in ('pythonw.exe',f'python{version}.dll','python3.dll')]
    binaries += [(path,Path(path.name)) for path in python.glob('vcruntime*.dll')]
    binaries += [(path,Path('DLLs')/path.name) for path in (python/'DLLs').iterdir() if path.suffix.lower() in ('.pyd','.dll')]
    library = []
    for directory, folders, names in os.walk(python/'Lib'):
        folders[:] = [name for name in folders if name not in SKIP_LIB]
        library += [Path(directory)/name for name in names if name.endswith('.py')]
    engine = [(path,Path('engine')/path.relative_to(ROOT)) for directory in ('core','plugins/ds1')
              for path in (ROOT/directory).glob('*.py')]
    engine += [(ROOT/name,Path('engine')/name) for name in ('plugins/__init__.py','plugins/ds3/formats.py')
               if (ROOT/name).is_file()]
    engine += [(path,Path('engine')/path.relative_to(ROOT)) for path in (ROOT/'plugins/ds1/metadata').rglob('*') if path.is_file()]
    for source,_ in binaries+engine:
        if not source.is_file():
            raise FileNotFoundError(source)
    return python,version,binaries,library,engine


def plan() -> dict:
    python,version,binaries,library,engine = inputs()
    return {'python':version,'files':len(binaries)+len(library)+len(engine),
            'sourceBytes':sum(path.stat().st_size for path,_ in binaries+engine)+sum(path.stat().st_size for path in library)}


def package(destination: Path) -> Path:
    from . import tweak_mods
    from .runtime import build
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a new, empty loader-package destination')
    manifest = json.loads((build.ONLINE_PACKAGE/'runtime-manifest.json').read_text())
    if manifest['sourceSha256'] != build.source_hash(build.ONLINE_SOURCES):
        raise ValueError('Rebuild the online loader from the current source before packaging')
    python,version,binaries,library,engine = inputs()
    destination.mkdir(parents=True)
    runtime = destination/'lexeditor-runtime'
    runtime.mkdir()
    for source,relative in binaries+engine:
        target = runtime/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    with zipfile.ZipFile(runtime/f'python{version}.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for source in library:
            archive.write(source,source.relative_to(python/'Lib').as_posix())
    (runtime/f'python{version}._pth').write_text(f'python{version}.zip\n.\nDLLs\n',encoding='utf-8')
    license_file = python/'LICENSE.txt'
    if license_file.is_file():
        shutil.copy2(license_file,runtime/'Python-LICENSE.txt')
    (destination/'dinput8.dll').write_bytes(tweak_mods.loader_bytes(online=True))
    shutil.copy2(ROOT/'plugins/ds1/credits.md',destination/'Loader-credits.txt')
    (destination/'README.txt').write_text(
        'Extract these files beside DarkSoulsRemastered.exe.\n'
        'Place each downloaded mod folder in the same game directory, or its mods subfolder.\n'
        'Start the game through Steam. Prebuilt data mods combine automatically.\n'
        'Lexeditor, Python installations and compilers are not required.\n'
        'Lexeditor can later offer to move these mods into your shared mod library.\n'
        'See Loader-credits.txt for licenses and source references.\n',encoding='utf-8')
    return destination
