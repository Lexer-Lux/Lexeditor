"""Compile the real Shared Magic reconciliation layer and Party Switch bridge.

Only platform memory/I/O is substituted. The pool core and bridge are compiled
unchanged, and actor/save accessors are extracted from the complete derivative
source. No game executable, save, or installed game is used.
"""
from __future__ import annotations
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'games/ff8/ffnx_issue_51'
EXT = ROOT / 'games/ff8/ffnx_gameplay_extensions/ffnx-src'


def runtime_source() -> str:
    patch = (CORE / 'package/ISSUE51_DERIVATIVE_SOURCE.patch').read_text(encoding='utf-8')
    section = patch.split('diff --git a/src/ff8/shared_magic_runtime.cpp b/src/ff8/shared_magic_runtime.cpp\n', 1)[1].split('\ndiff --git ', 1)[0]
    if 'new file mode' not in section:
        raise AssertionError('Expected complete added runtime source in derivative patch')
    return '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+') and not line.startswith('+++'))


def function(source: str, name: str) -> str:
    match = re.search(r'(?m)^[\w\s:*<>]+\b' + re.escape(name) + r'\([^;]*?\)\n\{', source)
    if not match:
        raise AssertionError('Missing production function ' + name)
    start = match.start()
    body = source.index('{', match.start()); depth = 0
    for end in range(body, len(source)):
        depth += source[end] == '{'
        depth -= source[end] == '}'
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError('Unclosed function ' + name)


def native_layer() -> str:
    runtime = runtime_source()
    methods = '\n'.join(function(runtime, name) for name in (
        'read_saved','write_saved','read_actor','read_actors','write_actor',
        'mirror_actors','preserve_canonical','adopt_saved_change','adopt_actor_change'))
    bridge = (EXT/'lexeditor_ff8_shared_party.inc').read_text(encoding='utf-8')
    bridge = re.sub(r'^#include .*$', '', bridge, flags=re.M)
    return r'''
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <cassert>
#include <cstdio>
#include "shared_magic_core.h"
#include "lexeditor_ff8_shared_party.h"
#define __cdecl
#define __declspec(x)
using namespace lexeditor::ff8::shared_magic;
using ActorInventories=std::array<MagicInventory,3>;
constexpr std::size_t kActorCount=3,kActorStride=0x1D0,kActorMagicOffset=0x82,kActorMagicStride=5;
RuntimeState g_state;
std::array<bool,3> g_actor_ready{};
std::size_t g_frame_depth=0;
std::uint32_t g_internal_depth=0,g_private_transaction_depth=0,g_reconciliation_owner_depth=0;
std::uint64_t g_reconcile_attempts=0,g_reconcile_successes=0;
struct Character { unsigned char magics[64]; unsigned char untouched[88]; };
struct Save { Character chars[8]; } save;
std::array<unsigned char,3*0x1D0> actors{};
std::array<unsigned,3> refreshes{};
void refresh(int slot) { ++refreshes[slot]; }
struct Externals { Save *savemap=&save; unsigned char *shared_magic_battle_actor_base=actors.data();
    std::uintptr_t shared_magic_actor_refresh=reinterpret_cast<std::uintptr_t>(&refresh); } ff8_externals;
constexpr int MODE_BATTLE=1;
struct Mode { int driver_mode=MODE_BATTLE; } mode;
Mode *getmode_cached() { return &mode; }
void ffnx_warning(const char *,...) {}
void fail_closed_to_canonical(const char *) { assert(false && "Unexpected canonical invariant failure"); }
''' + methods + '\n' + bridge


def run() -> None:
    source = native_layer() + (ROOT/'tools/fixtures/ff8_native/shared_party_cases.cpp').read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='ff8-shared-party-') as folder:
        cpp=Path(folder)/'test.cpp';exe=Path(folder)/'test'
        cpp.write_text(source, encoding='utf-8')
        subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-O1','-g',
            '-I',str(CORE),'-I',str(EXT),str(cpp),str(CORE/'shared_magic_core.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True,timeout=20)

if __name__ == '__main__': run()
