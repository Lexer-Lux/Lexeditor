"""Build a native app and OS installer, without bundling private helper binaries."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
VERSION='0.1.0'
RESOURCE_EXTENSIONS={'.html','.css','.js','.json','.csv','.txt','.md','.xml','.svg','.png','.jpg','.jpeg','.webp','.ico','.icns','.ttf','.otf','.woff','.woff2','.toml','.ini','.py','.ps1','.cmd','.bat'}
# Helpers with no proven redistribution grant are never copied into an installer.
FORBIDDEN_PARTS={'__pycache__','.git','worklog','codex','baseline','game-data','out'}


def run(*args: str) -> None:
    subprocess.run(list(map(str,args)),cwd=ROOT,check=True)


def package_notices() -> list[dict]:
    notices=[]
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get('Name','Unknown dependency')
        for file in distribution.files or []:
            if '.dist-info/' not in str(file).replace('\\','/') or not any(word in file.name.lower() for word in ('license','copying','notice')):
                continue
            path=Path(distribution.locate_file(file))
            if path.is_file() and path.stat().st_size<300000:
                try:text=path.read_text('utf-8')
                except UnicodeError:continue
                notices.append({'name':f'{name} {distribution.version} — {file.name}','text':text})
    return notices


def build_app() -> Path:
    generated=ROOT/'build/distribution';generated.mkdir(parents=True,exist_ok=True)
    notices=generated/'distribution-notices.json';notices.write_text(json.dumps(package_notices(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    datas=[]
    for folder in ['ui','assets','games']:
        for path in (ROOT/folder).rglob('*'):
            relative=path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or FORBIDDEN_PARTS.intersection(relative.parts):continue
            if path.suffix.lower() not in RESOURCE_EXTENSIONS:continue
            # Reverse-engineering driver trees are source evidence, not app assets.
            if any(part.startswith('ffnx_') for part in relative.parts):continue
            datas.append((str(path),str(relative.parent)))
    datas.append((str(notices),'ui'))
    modules=['games.'+p.parent.name+'.plugin' for p in (ROOT/'games').glob('*/plugin.py')]
    sys.path.insert(0,str(ROOT))
    from runtime_bootstrap import SERVICE_MODULES
    modules+=sorted(SERVICE_MODULES)
    modules+=['webview.platforms.cocoa'] if sys.platform=='darwin' else ['webview.platforms.winforms','webview.platforms.edgechromium'] if os.name=='nt' else ['webview.platforms.qt']
    # Include text/license provenance, not executables, game DLLs or private exports.
    for path in [ROOT/'tools/magic-rdr/README.md',ROOT/'tools/brf-sync/LICENSE',ROOT/'tools/brf-sync/SOURCE.md']:
        if path.exists():datas.append((str(path),str(path.relative_to(ROOT).parent)))
    icon=ROOT/'ui/assets/lexeditor.ico'
    if not icon.is_file():icon=None
    spec=generated/'Lexeditor.spec'
    text=f'''# Generated from reviewed application resources; private helpers excluded.
from PyInstaller.utils.hooks import collect_submodules
hiddenimports={modules!r}
hiddenimports += collect_submodules("games")
a=Analysis([{str(ROOT/'app.py')!r}], pathex=[{str(ROOT)!r}], binaries=[], datas={datas!r},
 hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=["pytest","playwright","tkinter"], noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name="Lexeditor",debug=False,
 bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon={str(icon) if icon else None!r})
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="Lexeditor")
'''
    if sys.platform=='darwin':text+='app=BUNDLE(coll,name="Lexeditor.app",bundle_identifier="io.github.lexer-lux.lexeditor",info_plist={"NSHighResolutionCapable":True})\n'
    spec.write_text(text,encoding='utf-8')
    run(sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(spec))
    return DIST/'Lexeditor.app/Contents/MacOS/Lexeditor' if sys.platform=='darwin' else DIST/'Lexeditor'/('Lexeditor.exe' if os.name=='nt' else 'Lexeditor')


def smoke(executable: Path) -> None:
    # Packaging must preserve child-service dispatch; launching a second GUI is a failure.
    result=ROOT/'build/distribution/smoke.json'
    env=os.environ.copy()
    env['LEXEDITOR_NO_AUTO_SCAN']='1'
    p=subprocess.run([str(executable),'--smoke-service',str(result)],cwd=Path.home(),env=env,timeout=90)
    if p.returncode or not result.exists():raise RuntimeError('Frozen app/service smoke failed')
    report=json.loads(result.read_text('utf-8'))
    if not report.get('passed') or not report.get('childStopped'):raise RuntimeError('Frozen child did not shut down')
    print(json.dumps(report),flush=True)


def build_installer() -> Path:
    out=DIST/'installers';out.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        script=ROOT/'build/distribution/setup.iss'
        icon=ROOT/'ui/assets/lexeditor.ico'
        script.write_text(f'''[Setup]
AppId=Lexeditor
AppName=Lexeditor
AppVersion={VERSION}
DefaultDirName={{localappdata}}\\Programs\\Lexeditor
DefaultGroupName=Lexeditor
PrivilegesRequired=lowest
OutputDir={out}
OutputBaseFilename=Lexeditor-{VERSION}-windows-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={{app}}\\Lexeditor.exe
[Files]
Source: "{DIST/'Lexeditor'}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{{group}}\\Lexeditor"; Filename: "{{app}}\\Lexeditor.exe"; WorkingDir: "{{app}}"
Name: "{{userdesktop}}\\Lexeditor"; Filename: "{{app}}\\Lexeditor.exe"; WorkingDir: "{{app}}"
[Run]
Filename: "{{app}}\\Lexeditor.exe"; Description: "Open Lexeditor"; Flags: nowait postinstall skipifsilent
''',encoding='utf-8')
        compiler=shutil.which('iscc') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        run(compiler,str(script))
        return out/f'Lexeditor-{VERSION}-windows-setup.exe'
    if sys.platform=='darwin':
        target=out/f'Lexeditor-{VERSION}-macos.pkg'
        run('pkgbuild','--component',str(DIST/'Lexeditor.app'),'--install-location','/Applications',
            '--identifier','io.github.lexer-lux.lexeditor','--version',VERSION,str(target))
        return target
    stage=ROOT/'build/distribution/deb';appdir=stage/'opt/lexeditor'
    if stage.exists():shutil.rmtree(stage)
    shutil.copytree(DIST/'Lexeditor',appdir)
    desktop=stage/'usr/share/applications/lexeditor.desktop';desktop.parent.mkdir(parents=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Lexeditor\nComment=Edit game mods\nExec=/opt/lexeditor/Lexeditor\nTerminal=false\nCategories=Game;Development;\nStartupNotify=true\n',encoding='utf-8')
    arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
    control=stage/'DEBIAN/control';control.parent.mkdir()
    control.write_text(f'Package: lexeditor\nVersion: {VERSION}\nSection: games\nPriority: optional\nArchitecture: {arch}\nMaintainer: Lexer <89482099+Lexer-Lux@users.noreply.github.com>\nDepends: libegl1, libopengl0, libxcb-cursor0, libxkbcommon-x11-0, libnss3, libasound2t64 | libasound2\nDescription: Lexeditor game-mod editor\n Native desktop application. Game installations and optional private helpers are separate.\n')
    target=out/f'Lexeditor-{VERSION}-linux-{arch}.deb'
    run('dpkg-deb','--root-owner-group','--build',str(stage),str(target))
    run('dpkg-deb','--info',str(target))
    return target


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skip-build',action='store_true');args=parser.parse_args()
    exe=build_app() if not args.skip_build else DIST/'Lexeditor'/('Lexeditor.exe' if os.name=='nt' else 'Lexeditor')
    smoke(exe)
    target=build_installer()
    print('Installer:',target,flush=True)

if __name__=='__main__':main()
