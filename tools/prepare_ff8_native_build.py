"""Prepare the pinned FFNx derivative with the canonical native battle fixes.

Run only against a disposable, clean FFNx build checkout. This never reads,
installs, modifies or uploads FF8_EN.exe or a game installation.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='c056db2783f376a340fcefa6a48cc33618998876'


def prepare(source: Path, patch_output: Path, *, verify_revision: bool=True) -> None:
    source=source.resolve();patch_output=patch_output.resolve()
    if verify_revision:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
        if revision!=BASE:
            raise RuntimeError(f'Expected FFNx {BASE}; found {revision}')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=source,text=True).strip():
        raise RuntimeError('Refusing to modify a dirty FFNx source checkout')
    patch=ROOT/'games/ff8/ffnx_issue_51/package/ISSUE51_DERIVATIVE_SOURCE.patch'
    subprocess.run(['git','apply','--check','--ignore-space-change',str(patch)],cwd=source,check=True)
    subprocess.run(['git','apply','--ignore-space-change',str(patch)],cwd=source,check=True)
    for folder,name in (
        ('ffnx_status_bars','lexeditor_ff8_bars.cpp'),
        ('ffnx_status_bars','lexeditor_ff8_bars.h'),
        ('ffnx_party_switch','lexeditor_ff8_party_switch.cpp'),
        ('ffnx_party_switch','lexeditor_ff8_party_switch.h'),
    ):
        shutil.copyfile(ROOT/f'games/ff8/{folder}/ffnx-src/{name}',source/'src'/name)
    extension_files = [
        'lexeditor_ff8_shared_party.h', 'lexeditor_ff8_shared_party.inc',
        'lexeditor_ff8_stock_tweaks.h', 'lexeditor_ff8_stock_tweaks.cpp',
    ]
    for name in extension_files:
        destination = source / 'src' / ('ff8' if name.endswith('.inc') else '') / name
        shutil.copyfile(ROOT / 'games/ff8/ffnx_gameplay_extensions/ffnx-src' / name, destination)
    # The packaged provenance patch may already include the new switch after
    # this candidate has been validated and promoted; support repeat builds.
    changes={
        'src/cfg.cpp':[
            ('bool enable_ff8_party_switch;', 'bool enable_ff8_party_switch;\nbool enable_ff8_no_magic_consumption;'),
            ('\tenable_ff8_party_switch = config["enable_ff8_party_switch"].value_or(false);',
             '\tenable_ff8_party_switch = config["enable_ff8_party_switch"].value_or(false);\n\tenable_ff8_no_magic_consumption = config["enable_ff8_no_magic_consumption"].value_or(false);'),
            ('bool enable_ff8_hp_bars;','bool enable_ff8_hp_bars;\nbool enable_ff8_gf_hp_bars;'),
            ('\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);',
             '\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);\n\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);'),
        ],
        'src/cfg.h':[
            ('extern bool enable_ff8_party_switch;', 'extern bool enable_ff8_party_switch;\nextern bool enable_ff8_no_magic_consumption;'),
            ('extern bool enable_ff8_hp_bars;','extern bool enable_ff8_hp_bars;\nextern bool enable_ff8_gf_hp_bars;'),
        ],
        'misc/FFNx.toml':[
            ('enable_ff8_party_switch = false', 'enable_ff8_party_switch = false\n\n# Keep spell stock on successful field/battle casts; items still consume.\nenable_ff8_no_magic_consumption = false'),
            ('enable_ff8_hp_bars = false','enable_ff8_hp_bars = false\n\n# Blue junctioned-GF HP bar above each party name.\nenable_ff8_gf_hp_bars = false'),
        ],
    }
    changes['src/ff8_opengl.cpp'] = [
        ('#include "lexeditor_ff8_party_switch.h"', '#include "lexeditor_ff8_party_switch.h"\n#include "lexeditor_ff8_stock_tweaks.h"'),
        ('\tlexeditor_ff8_party_switch_install();', '\tlexeditor_ff8_party_switch_install();\n\tlexeditor_ff8_stock_tweaks_install();'),
    ]
    # Stock reconciliation and actor readiness stay owned by the existing
    # Shared Magic runtime. Add the explicit DLL-caller lifecycle there.
    runtime = source / 'src/ff8/shared_magic_runtime.cpp'
    text = runtime.read_text(encoding='utf-8')
    include = '#include "lexeditor_ff8_shared_party.inc"'
    if include not in text:
        text += '\n' + include + '\n'
    header = '#include "../lexeditor_ff8_shared_party.h"'
    if header not in text:
        text = text.replace('#include "shared_magic_runtime.h"', '#include "shared_magic_runtime.h"\n' + header, 1)
    for anchor in ['void request_activation()\n{', 'void fail_closed_to_canonical(const char *reason)\n{']:
        addition = anchor + '\n    lexeditor_ff8_shared_party_reset();'
        if addition not in text:
            if text.count(anchor) != 1:
                raise RuntimeError('Shared Magic lifecycle anchor changed')
            text = text.replace(anchor, addition, 1)
    runtime.write_text(text, encoding='utf-8')
    for relative,pairs in changes.items():
        path=source/relative;raw=path.read_bytes();newline='\r\n' if b'\r\n' in raw else '\n'
        text=raw.decode('utf-8').replace('\r\n','\n')
        for old,new in pairs:
            # Check the added declaration/parser line, not just the substring
            # (cfg.cpp contains both the declaration and the parser).
            addition=new.split('\n')[-1]
            if addition in text:continue
            if text.count(old)!=1:raise RuntimeError(f'Integration anchor changed: {relative}: {old}')
            text=text.replace(old,new,1)
        path.write_bytes(text.replace('\n',newline).encode('utf-8'))
    # git apply leaves new files untracked. Include EVERY file introduced by
    # the derivative, not just src/: otherwise the published patch silently
    # loses its tests, artifact verifier and reproducible-build entry point.
    patch_paths = [line[6:] for line in patch.read_text(encoding="utf-8").splitlines()
                   if line.startswith("+++ b/")]
    patch_paths.extend('src/' + ('ff8/' if name.endswith('.inc') else '') + name for name in extension_files)
    for name in patch_paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not (source / relative).is_file():
            raise RuntimeError(f"Invalid derivative patch path: {name}")
    subprocess.run(['git','add','--intent-to-add','--',*patch_paths],cwd=source,check=True)
    patch_output.parent.mkdir(parents=True,exist_ok=True)
    with patch_output.open('wb') as output:
        subprocess.run(['git','-c','core.autocrlf=false','diff','--binary','HEAD','--','.'],cwd=source,stdout=output,check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--patch-output',type=Path,required=True)
    args=parser.parse_args();prepare(args.source,args.patch_output)
