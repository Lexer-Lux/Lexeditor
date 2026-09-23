"""Issue #302 source/core checks; optional private-executable identity check.

The executable argument is read locally only. The script records no executable
bytes and never writes or uploads it.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/ff8/ffnx_gameplay_extensions/ffnx-src/interaction_indicator.h"
RUNTIME = ROOT / "plugins/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_interaction_indicators.cpp"
PREPARE = ROOT / "tools/prepare_ff8_native_build.py"
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def static_contract() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    prepare = PREPARE.read_text(encoding="utf-8")
    for token in (
        "kFieldEntities = 0x01D9CF88",
        "kFieldEntityCount = 0x01D9D019",
        "kFieldPlayerEntity = 0x01CD8FD0",
        "kFieldControlLock = 0x01CE4775",
        "kDirectionAndDistance = 0x00477380",
        "kCardgameHandler = 0x005225A0",
        "kFieldInstructions = 0x01D9CF50",
        "kFieldEntrypoints = 0x01D9D0E4",
        "target[kInteractionDisabled] != 0",
        "error < best_error",
        "talk_script_has_cardgame(best)",
        "MODE_FIELD",
    ):
        require(token in source, f"native interaction contract missing {token}")
    require("enable_ff8_interaction_indicators = false" in prepare,
            "candidate switch must default off")
    require("lexeditor_ff8_interaction_indicators_draw();" in prepare,
            "overlay draw integration missing")
    # The runtime must only observe native interaction state. Its source has no
    # interaction-request offset (+0x24A) and no input-state addresses.
    require("0x24A" not in source and "0x01CE48B0" not in source,
            "indicator must not write/request an interaction or poll button edges")


def compile_contract(compiler: str, jsm: Path | None = None) -> None:
    harness = r"""
#include <cassert>
#include <cstdint>
#include "interaction_indicator.h"

using namespace lexeditor_interaction_indicator;

int main()
{
    const std::uint32_t code[] = {
        0x0700001FU,       // PSHN_L literal
        0x0A000124U,       // PSHM_B variable
        0x0000013AU,       // CARDGAME
    };
    assert(opcode(code[0]) == 0x07);
    assert(opcode(code[2]) == 0x13A);
    assert(talk_script_has_cardgame(code, 3));
    assert(!talk_script_has_cardgame(code, 2));
    assert(!talk_script_has_cardgame(nullptr, 0));

    assert(facing_error(0x00, 0x00) == 0);
    assert(facing_error(0x02, 0xFE) == 4);
    assert(facing_error(0xFE, 0x02) == 4);
    assert(facing_error(0x00, 0x40) == 0x40);

    assert(vertical_range(0, 255));
    assert(!vertical_range(0, 256));
    assert(vertical_range(0, -255));
    assert(!vertical_range(0, -256));

    assert(within_talk_radius(95, 48, 48));
    assert(!within_talk_radius(96, 48, 48));
}
"""
    if jsm is not None:
        import struct
        import sys
        sys.path.insert(0, str(ROOT))
        from plugins.ff8.field_scripts import read
        parsed = read(jsm.read_bytes(), jsm.with_suffix('.sym').read_bytes())
        talks = [method for method in parsed['methods'] if method['localId'] == 2]
        positives = [method['name'] for method in talks if 'CARDGAME' in method['source']]
        require(set(positives) == {'seito6::talk', 'seito7::talk', 'seito8::talk', 'seito10::talk'},
                'Expected the four retail bghall_1 card players')
        checks = []
        for index, method in enumerate(talks):
            raw = bytes.fromhex(method['raw'])
            words = struct.unpack(f'<{len(raw)//4}I', raw)
            literal = ','.join(f'0x{word:08X}U' for word in words)
            expected = 'true' if method['name'] in positives else 'false'
            checks.append(f'const std::uint32_t retail{index}[]={{ {literal} }};'
                          f'assert(talk_script_has_cardgame(retail{index},{len(words)})=={expected});')
        harness = harness.replace('int main()\n{', 'int main()\n{\n'+'\n'.join(checks))
        print(f'Retail bghall_1: {len(talks)} Talk scripts, four card targets; private bytes stay temporary')
    with tempfile.TemporaryDirectory(prefix="ff8-interaction-302-") as directory:
        temp = Path(directory)
        (temp / "interaction_indicator.h").write_bytes(CORE.read_bytes())
        (temp / "check.cpp").write_text(harness, encoding="utf-8")
        if Path(compiler).name.casefold() in {"cl", "cl.exe"}:
            command = [compiler, "/nologo", "/EHsc", "/std:c++17",
                       "check.cpp", "/Fe:check.exe"]
            output = temp / "check.exe"
        else:
            output = temp / "check"
            command = [compiler, "-std=c++17", "-Wall", "-Wextra",
                       "check.cpp", "-o", str(output)]
        result = subprocess.run(command, cwd=temp, capture_output=True, text=True)
        require(result.returncode == 0,
                "interaction core compile failed:\n" + result.stdout + result.stderr)
        result = subprocess.run([str(output)], cwd=temp, capture_output=True, text=True)
        require(result.returncode == 0,
                "interaction core execution failed:\n" + result.stdout + result.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--jsm", type=Path, help="Private retail bghall_1.jsm, with adjacent .sym")
    args = parser.parse_args()

    static_contract()
    if args.compile:
        compile_contract(args.compiler, args.jsm)
    if args.exe is not None:
        require(sha256(args.exe) == EXPECTED_EXE,
                "unsupported FF8_EN.exe SHA-256")
    print("PASS: FF8 #302 selector/card classifier source contracts"
          + (" and private executable identity" if args.exe else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
