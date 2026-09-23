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


def integrate_shared_magic_notifications(source: Path) -> None:
    """Show a failed load-time migration through Lexeditor's message queue.

    The queue owns what is shown and for how long: it holds the message long
    enough to read, wraps it to FF8's message width, and refuses to restack it
    when the per-frame heartbeat asks again. FFNx's overlay is only the surface
    it is drawn on - it fades on an accelerating decay tuned for one-word
    notices - so replacing that with a native message box later is one function
    rather than a rewrite.
    """
    path = source/'src/ff8/shared_magic_runtime.cpp'
    text = path.read_text(encoding='utf-8')
    if 'lexeditor_ff8_toast_push' in text:
        return
    declaration = (
        "// Lexeditor's own in-game messages go to the FF8-style box in\n"
        "// lexeditor_ff8_toast.cpp, which owns the queue and the drawing.\n"
        "bool g_warning_started = false;"
    )
    queue_message = (
        "        {\n"
        "            const std::string message =\n"
        "                migration_warning_template(result.error, g_stock_limit);\n"
        "            lexeditor_ff8_toast_push(message.c_str(), true);\n"
        "            append_runtime_log((message + \"\\n\").c_str());\n"
        "        }\n"
        "        g_requested = false;\n        g_warning = MergeError::none;"
    )
    heartbeat = (
        "void ff8_shared_magic_heartbeat()\n{\n"
        "    // Nothing to drain here any more: the message box owns the queue,\n"
        "    // holds each sentence long enough to read, and draws it the way FF8\n"
        "    // draws its own. FFNx's popup fades on a decay tuned for one word.\n"
    )
    changes = [
        ('#include "../log.h"',
         '#include "../log.h"\n#include "../common.h"\n#include "../lexeditor_ff8_toast.h"'),
        ('bool g_warning_started = false;', declaration),
        ('        g_requested = false;\n        g_warning = MergeError::none;', queue_message),
        ('void ff8_shared_magic_heartbeat()\n{', heartbeat),
    ]
    for old, new in changes:
        if text.count(old) != 1:
            raise RuntimeError(f'Shared Magic notification anchor changed: {old}')
        text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')



def integrate_flare_owner(source: Path, *, startup: bool = False) -> None:
    """Wire only FF8 gates; preserve native encounter/music handling afterward."""
    changes = {
        'src/common.cpp': [
            ('#include "lexeditor_ff8_party_switch.h"', '#include "lexeditor_ff8_party_switch.h"\n#include "lexeditor_ff8_flare_owner.h"'),
            ('\tlexeditor_ff8_party_switch_tick();', '\tlexeditor_ff8_party_switch_tick();\n\tlexeditor_ff8_flare_tick();\n\tlexeditor_ff8_flare_service_stationary_field();'),
        ],
        'src/ff8_opengl.cpp': [
            ('#include "lexeditor_ff8_party_switch.h"', '#include "lexeditor_ff8_party_switch.h"\n#include "lexeditor_ff8_flare_owner.h"'),
            ('\tif (gamehacks.wantsBattle()) ret = ff8_externals.sub_47CA90();',
             '\tret = lexeditor_ff8_flare_field_gate(gamehacks.wantsBattle());\n\tif (ret < 0) ret = gamehacks.wantsBattle() ? ff8_externals.sub_47CA90() : 0;'),
            ('\tif (gamehacks.wantsBattle()) ret = ff8_externals.sub_541C80(battle_id);',
             '\tret = lexeditor_ff8_flare_world_gate(battle_id, gamehacks.wantsBattle());\n\tif (ret < 0) ret = gamehacks.wantsBattle() ? ff8_externals.sub_541C80(battle_id) : 0;'),
        ],
    }
    if startup:
        changes['src/ff8_opengl.cpp'].append(('\tlexeditor_ff8_modern_controls_install();',
            '\tlexeditor_ff8_modern_controls_install();\n\tlexeditor_ff8_flare_owner_install();'))
    prepared = {}
    for relative, pairs in changes.items():
        path=source/relative; text=path.read_text(encoding='utf-8')
        if relative=='src/common.cpp' and 'lexeditor_ff8_flare_service_stationary_field();' not in text:
            text=text.replace('\tlexeditor_ff8_flare_tick();', '\tlexeditor_ff8_flare_tick();\n\tlexeditor_ff8_flare_service_stationary_field();')
        for old,new in pairs:
            if new in text: continue
            if text.count(old)!=1: raise RuntimeError(f'Signal Flare integration anchor changed: {relative}: {old}')
            text=text.replace(old,new,1)
        prepared[path]=text
    for path,text in prepared.items(): path.write_text(text,encoding='utf-8')


def prepare(source: Path, patch_output: Path, *, verify_revision: bool=True) -> None:
    source=source.resolve();patch_output=patch_output.resolve()
    if verify_revision:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
        if revision!=BASE:
            raise RuntimeError(f'Expected FFNx {BASE}; found {revision}')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=source,text=True).strip():
        raise RuntimeError('Refusing to modify a dirty FFNx source checkout')
    patch=ROOT/'plugins/ff8/ffnx_issue_51/package/ISSUE51_DERIVATIVE_SOURCE.patch'
    subprocess.run(['git','apply','--check','--ignore-space-change',str(patch)],cwd=source,check=True)
    subprocess.run(['git','apply','--ignore-space-change',str(patch)],cwd=source,check=True)
    integrate_shared_magic_notifications(source)
    for folder,name in (
        ('ffnx_status_bars','lexeditor_ff8_bars.cpp'),
        ('ffnx_status_bars','lexeditor_ff8_bars.h'),
        ('ffnx_status_bars','lexeditor_ff8_hp_colors.h'),
        ('ffnx_party_switch','lexeditor_ff8_party_switch.cpp'),
        ('ffnx_party_switch','lexeditor_ff8_party_switch.h'),
    ):
        shutil.copyfile(ROOT/f'plugins/ff8/{folder}/ffnx-src/{name}',source/'src'/name)
    # Modern Controls is also present in the provenance patch, but its maintained
    # sources move faster than that immutable build snapshot. Always overlay the
    # current audited implementation after applying the pinned derivative patch.
    for name in (
        'camera_axis.h',
        'battle_camera.h',
        'vehicle_drive.h',
        'lexeditor_ff8_modern_controls.cpp',
        'lexeditor_ff8_modern_controls.h',
    ):
        shutil.copyfile(ROOT/'plugins/ff8/ffnx_modern_controls'/name, source/'src'/name)
    # Lexeditor's own in-game messages. The queue decides what is shown and
    # for how long, the layout decides where the box sits and how it fades,
    # and the third file is the only part that touches a device.
    for name in ('toast_queue.h', 'toast_layout.h'):
        shutil.copyfile(ROOT/'plugins/ff8/ffnx_toasts'/name, source/'src'/name)
    for name in ('lexeditor_ff8_toast.h', 'lexeditor_ff8_toast.cpp'):
        shutil.copyfile(ROOT/'plugins/ff8/ffnx_toasts/ffnx-src'/name, source/'src'/name)
    extension_files = [
        'flare_encounter.h', 'lexeditor_ff8_flare.cpp',
        'flare_request.h', 'lexeditor_ff8_flare_owner.h', 'lexeditor_ff8_flare_owner.cpp',
        'flare_item.h', 'flare_shop.h', 'lexeditor_ff8_flare_item.cpp', 'lexeditor_ff8_flare_shop.cpp', 'lexeditor_ff8_flare_menu.cpp',
        'lexeditor_ff8_shared_party.h', 'lexeditor_ff8_shared_party.inc',
        'lexeditor_ff8_stock_tweaks.h', 'lexeditor_ff8_stock_tweaks.cpp',
        'lexeditor_ff8_gf_spellbooks.h', 'lexeditor_ff8_gf_spellbooks.cpp',
        'reptile_atb_runtime.h', 'lexeditor_ff8_reptile_atb.h',
        'lexeditor_ff8_reptile_atb.cpp',
        'interaction_indicator.h', 'lexeditor_ff8_interaction_indicators.h',
        'lexeditor_ff8_interaction_indicators.cpp',
    ]
    for name in extension_files:
        destination = source / 'src' / ('ff8' if name.endswith('.inc') else '') / name
        shutil.copyfile(ROOT / 'plugins/ff8/ffnx_gameplay_extensions/ffnx-src' / name, destination)
    # The packaged provenance patch may already include the new switch after
    # this candidate has been validated and promoted; support repeat builds.
    changes={
        'src/cfg.cpp':[
            ('bool enable_ff8_party_switch;', 'bool enable_ff8_party_switch;\nbool enable_ff8_no_magic_consumption;'),
            ('\tenable_ff8_party_switch = config["enable_ff8_party_switch"].value_or(false);',
             '\tenable_ff8_party_switch = config["enable_ff8_party_switch"].value_or(false);\n\tenable_ff8_no_magic_consumption = config["enable_ff8_no_magic_consumption"].value_or(false);'),
            ('bool enable_ff8_no_magic_consumption;',
             'bool enable_ff8_no_magic_consumption;\nbool enable_ff8_interaction_indicators;'),
            ('\tenable_ff8_no_magic_consumption = config["enable_ff8_no_magic_consumption"].value_or(false);',
             '\tenable_ff8_no_magic_consumption = config["enable_ff8_no_magic_consumption"].value_or(false);\n\tenable_ff8_interaction_indicators = config["enable_ff8_interaction_indicators"].value_or(false);'),
            ('bool enable_ff8_hp_bars;','bool enable_ff8_hp_bars;\nbool enable_ff8_better_hp_colors;\nbool enable_ff8_gf_hp_bars;'),
            ('\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);',
             '\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);\n\tenable_ff8_better_hp_colors = config["enable_ff8_better_hp_colors"].value_or(false);\n\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);'),
            ('bool enable_ff8_gf_hp_bars;','bool enable_ff8_gf_hp_bars;\nbool enable_ff8_ingame_time;'),
            ('\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);',
             '\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);\n\tenable_ff8_ingame_time = config["enable_ff8_ingame_time"].value_or(false);'),
            # The Modern Controls overlay reads its camera turn rate; the
            # provenance patch predates that setting.
            ('bool enable_ff8_modern_controls;', 'bool enable_ff8_modern_controls;\ndouble ff8_modern_controls_camera_speed;'),
            ('\tenable_ff8_modern_controls = config["enable_ff8_modern_controls"].value_or(false);',
             '\tenable_ff8_modern_controls = config["enable_ff8_modern_controls"].value_or(false);\n\tff8_modern_controls_camera_speed = config["ff8_modern_controls_camera_speed"].value_or(1.0);'),
        ],
        'src/cfg.h':[
            ('extern bool enable_ff8_party_switch;', 'extern bool enable_ff8_party_switch;\nextern bool enable_ff8_no_magic_consumption;'),
            ('extern bool enable_ff8_no_magic_consumption;',
             'extern bool enable_ff8_no_magic_consumption;\nextern bool enable_ff8_interaction_indicators;'),
            ('extern bool enable_ff8_hp_bars;','extern bool enable_ff8_hp_bars;\nextern bool enable_ff8_better_hp_colors;\nextern bool enable_ff8_gf_hp_bars;'),
            ('extern bool enable_ff8_gf_hp_bars;','extern bool enable_ff8_gf_hp_bars;\nextern bool enable_ff8_ingame_time;'),
            ('extern bool enable_ff8_modern_controls;', 'extern bool enable_ff8_modern_controls;\nextern double ff8_modern_controls_camera_speed;'),
        ],
        'misc/FFNx.toml':[
            ('enable_ff8_party_switch = false', 'enable_ff8_party_switch = false\n\n# Keep spell stock on successful field/battle casts; items still consume.\nenable_ff8_no_magic_consumption = false'),
            ('enable_ff8_no_magic_consumption = false',
             'enable_ff8_no_magic_consumption = false\n\n# Show non-invasive field interaction and Triple Triad opponent HUD cues.\nenable_ff8_interaction_indicators = false'),
            ('enable_ff8_hp_bars = false','enable_ff8_hp_bars = false\n\n# Smoothly tint living HP numbers by remaining HP; KO stays native.\nenable_ff8_better_hp_colors = false\n\n# Blue junctioned-GF HP bar above each party name.\nenable_ff8_gf_hp_bars = false'),
            ('enable_ff8_gf_hp_bars = false','enable_ff8_gf_hp_bars = false\n\n# Show the computer local clock on FF8 main menu without changing PLAY time.\nenable_ff8_ingame_time = false'),
            ('enable_ff8_modern_controls = false', 'enable_ff8_modern_controls = false\n\n# Battle camera turn rate as a multiple of the shipped speed, 0.2 to 4.\nff8_modern_controls_camera_speed = 1.0'),
        ],
    }
    # The message box draws in the same ImGui frame the status bars use, and
    # keeps that frame alive on its own account: a toast must appear whether or
    # not any bar is switched on.
    changes['src/overlay.cpp'] = [
        ('#include "lexeditor_ff8_bars.h"',
         '#include "lexeditor_ff8_bars.h"\n#include "lexeditor_ff8_toast.h"\n#include "lexeditor_ff8_interaction_indicators.h"'),
        ('    lexeditor_ff8_bars_draw();',
         '    lexeditor_ff8_bars_draw();\n    lexeditor_ff8_toast_draw();\n    lexeditor_ff8_interaction_indicators_draw();'),
    ]
    changes['src/renderer.cpp'] = [
        ('#include "lexeditor_ff8_bars.h"',
         '#include "lexeditor_ff8_bars.h"\n#include "lexeditor_ff8_toast.h"\n#include "lexeditor_ff8_interaction_indicators.h"'),
    ]
    changes['src/ff8_opengl.cpp'] = [
        ('\tret->draw_paletted2D = common_draw_paletted2D;',
         '\tret->draw_paletted2D = lexeditor_ff8_hp_colors_requested() ? lexeditor_ff8_hp_colors_draw_paletted2D : common_draw_paletted2D;'),
        ('#include "lexeditor_ff8_party_switch.h"', '#include "lexeditor_ff8_party_switch.h"\n#include "lexeditor_ff8_stock_tweaks.h"\n#include "lexeditor_ff8_gf_spellbooks.h"\n#include "lexeditor_ff8_reptile_atb.h"'),
        ('\tlexeditor_ff8_party_switch_install();', '\tlexeditor_ff8_party_switch_install();\n\tlexeditor_ff8_stock_tweaks_install();\n\tlexeditor_ff8_gf_spellbooks_install();\n\tlexeditor_ff8_reptile_atb_install();'),
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
            # Earlier derivatives may contain only part of this addition.
            # Checking only the last line skipped Better HP Colors whenever
            # GF HP bars were already present.
            if new.startswith(old+'\n'):
                additions=new[len(old)+1:].split('\n')
                missing=[line for line in additions if line not in text.splitlines()]
                if not missing:continue
                replacement=old+'\n'+'\n'.join(missing)
            else:
                if new in text:continue
                replacement=new
            if text.count(old)!=1:raise RuntimeError(f'Integration anchor changed: {relative}: {old}')
            text=text.replace(old,replacement,1)
        path.write_bytes(text.replace('\n',newline).encode('utf-8'))
    for relative in ('src/renderer.cpp', 'src/overlay.cpp'):
        path = source / relative
        raw = path.read_bytes()
        newline = '\r\n' if b'\r\n' in raw else '\n'
        text = raw.decode('utf-8').replace('\r\n', '\n')
        gate = 'if (enable_devtools || lexeditor_ff8_bars_enabled())'
        wanted = ('if (enable_devtools || lexeditor_ff8_bars_enabled() || '
                  'lexeditor_ff8_toast_enabled() || '
                  'lexeditor_ff8_interaction_indicators_enabled())')
        if wanted not in text and gate in text:
            text = text.replace(gate, wanted)
            path.write_bytes(text.replace('\n', newline).encode('utf-8'))
    integrate_flare_owner(source, startup=True)
    # git apply leaves new files untracked. Include EVERY file introduced by
    # the derivative, not just src/: otherwise the published patch silently
    # loses its tests, artifact verifier and reproducible-build entry point.
    patch_paths = [line[6:] for line in patch.read_text(encoding="utf-8").splitlines()
                   if line.startswith("+++ b/")]
    patch_paths.extend('src/' + ('ff8/' if name.endswith('.inc') else '') + name for name in extension_files)
    patch_paths.extend(('src/toast_layout.h', 'src/lexeditor_ff8_toast.h',
                        'src/lexeditor_ff8_toast.cpp', 'src/lexeditor_ff8_hp_colors.h'))
    for relative in ('src/battle_camera.h', 'src/vehicle_drive.h'):
        if relative not in patch_paths:
            patch_paths.append(relative)
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
