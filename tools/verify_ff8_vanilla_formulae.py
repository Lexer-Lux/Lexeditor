"""Prove the three vanilla Formulae descriptions against FF8_EN.exe."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def instructions(data: bytes, pe: pefile.PE, start: int, size: int) -> dict[int, str]:
    offset = pe.get_offset_from_rva(start - pe.OPTIONAL_HEADER.ImageBase)
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    return {item.address: f"{item.mnemonic} {item.op_str}".strip()
            for item in decoder.disasm(data[offset:offset + size], start)}


def require_code(code: dict[int, str], address: int, expected: str) -> None:
    actual = code.get(address)
    if actual != expected:
        raise AssertionError(f"{address:#x}: expected {expected!r}; found {actual!r}")


def verify_executable() -> dict:
    data = EXE.read_bytes()
    assert sha256(data).hexdigest() == EXPECTED_SHA256
    pe = pefile.PE(data=data)

    magic = instructions(data, pe, 0x491AD0, 0x550)
    for address, expected in {
        0x491C62: "call 0x48f020",       # random byte
        0x491C79: "add ecx, 0xf0",       # 240..272
        0x491C94: "add eax, ebp",        # MAG + power
        0x491C96: "sub edx, edi",        # 265 - SPR
        0x491C98: "imul eax, edx",
        0x491CA1: "sar eax, 2",           # trunc /4
        0x491CA4: "imul eax, ebp",        # * power
        0x491CB0: "sar eax, 8",           # trunc /256
        0x491CB3: "imul eax, ecx",        # * random
        0x491CC1: "sar esi, 8",           # trunc /256
        0x491CC4: "cmp ebx, 3",           # monster caster
        0x491CC9: "sar esi, 1",
        0x491CEE: "sar esi, 1",           # Shell
        0x491CFC: "sar esi, 1",           # Defend
        0x491EFB: "mov ecx, 0x384",       # 900 - element defence
        0x491F07: "imul ecx, esi",
        0x491F0C: "sar edx, 5",           # signed /100 magic-number sequence
        0x491FB1: "cmp edx, 0x270f",      # cap 9,999
        0x491FB9: "mov edx, 0x270f",
    }.items():
        require_code(magic, address, expected)

    healing = instructions(data, pe, 0x493280, 0x1D0)
    for address, expected in {
        0x493398: "call 0x48f020",
        0x4933B3: "add ecx, 0xf0",
        0x4933C9: "add eax, edi",          # MAG + power
        0x4933CE: "sar eax, 1",           # trunc /2
        0x4933D0: "imul eax, ecx",        # * random
        0x4933D3: "imul eax, edi",        # * power
        0x4933DF: "sar eax, 8",           # trunc /256
        0x4933FC: "sar eax, 1",           # Shell
        0x493413: "neg eax",              # Zombie sign
        0x49343D: "call 0x491820",        # unconditional cure-status apply
    }.items():
        require_code(healing, address, expected)

    status = instructions(data, pe, 0x48F9F0, 0x1B0)
    for address, expected in {
        0x48FA15: "test ebx, edx",         # status already present
        0x48FA49: "cmp cl, 0xc8",          # resistance >= 200
        0x48FA32: "cmp edi, 0xff",         # accuracy 255
        0x48FA6B: "sar ebp, 2",            # attacker stat /4
        0x48FA6E: "sar eax, 2",            # target stat /4
        0x48FA71: "sub ebp, eax",
        0x48FA73: "sub ebp, ecx",          # resistance subtraction
        0x48FA75: "lea eax, [edi + ebp]",  # + accuracy
        0x48FA7F: "cmp edx, 0x12c",        # chance <= 0
        0x48FA87: "cmp edi, 0xfa",         # 250..254 positive guarantee
        0x48FA91: "shl ecx, 8",            # chance * 255
        0x48FAC3: "call 0x48f020",         # random byte
        0x48FAD5: "cmp edi, eax",
    }.items():
        require_code(status, address, expected)

    # Damage_DispatchByAttackType routes normal magic and curative magic through
    # the two routines documented above. These call sites also prove the four-
    # argument calling contract instead of treating a free-standing formula-like
    # instruction sequence as a complete game path.
    dispatch = instructions(data, pe, 0x4922B0, 0x310)
    for address, expected in {
        0x492379: "push 0",                # normal-magic mode
        0x492386: "call 0x491ad0",
        0x492395: "push 7",                # curative-magic mode
        0x4923A2: "call 0x493280",
    }.items():
        require_code(dispatch, address, expected)

    # The physical and magical status wrappers both call the same resistance
    # roller. Their preceding stat loads select STR/VIT or MAG/SPR before the
    # shared chance calculation executes.
    physical_status = instructions(data, pe, 0x4916B0, 0xE0)
    for address, expected in {
        0x4916BF: "mov dl, byte ptr [eax + 0x1d27bcd]",
        0x4916C7: "mov al, byte ptr [edi + 0x1d27bce]",
        0x49172F: "call 0x48f9f0",
    }.items():
        require_code(physical_status, address, expected)
    magical_status = instructions(data, pe, 0x4920C9, 0xF0)
    for address, expected in {
        0x4920E0: "mov bl, byte ptr [edx + 0x1d27bcd]",
        0x4920E8: "mov dl, byte ptr [ecx + 0x1d27bce]",
        0x492101: "mov bl, byte ptr [edx + 0x1d27bcf]",
        0x492109: "mov dl, byte ptr [ecx + 0x1d27bd0]",
        0x492147: "call 0x48f9f0",
    }.items():
        require_code(magical_status, address, expected)
    return {"sha256": EXPECTED_SHA256,
            "paths": ["0x491AD0", "0x493280", "0x48F9F0"],
            "dispatcher": "0x4922B0"}


def verify_source_and_render() -> dict:
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    formulae = editor[editor.index("function renderFormulae"):
                      editor.index("async function saveAll")]
    assert "Not yet transcribed from the game" not in formulae
    required = (
        "Damage_ComputeMagicAndGF at 0x491AD0",
        "BASE = trunc((265 − target SPR) × (spell power + caster MAG) / 4)",
        "SCALED = trunc(spell power × BASE / 256)",
        "random[240..272]", "caps the final magnitude at 9,999",
        "Battle_ApplyStatusWithResistRoll at 0x48F9F0",
        "status accuracy + trunc(attacker stat / 4) − trunc(target stat / 4) − target status resistance",
        "resistance of 200 or more", "accuracy 250..254",
        "trunc(CHANCE × 255 / 100) ≥ random[0..255]",
        "Damage_ComputeCurativeMagic at 0x493280",
        "HALF = trunc((spell power + caster MAG) / 2)",
        "HEALING = trunc(spell power × random[240..272] × HALF / 256)",
        "status accuracy is not read on this path",
        "This routine has no formula-result clamp",
    )
    for text in required:
        assert text in formulae, f"Incomplete vanilla formula description: {text}"
    # Ban the three oversimplifications that previously stood in for the real paths.
    assert "status_accuracy is a byte" not in formulae
    assert "Final HP application clamps current HP" not in formulae

    project = tempfile.TemporaryDirectory(prefix="lexeditor-formula-transcription-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('formulae')")
            wait_eval(cdp, "document.querySelectorAll('.formula-rework').length===4", 30)
            result = cdp.eval("""(()=>({vanilla:[...document.querySelectorAll('.formula-rework .formula-vanilla')].map(node=>node.textContent.trim()),overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,errors:window.__testErrors||[]}))()""")
            joined = "\n".join(result["vanilla"])
            for address in ("0x491AD0", "0x493280", "0x48F9F0"):
                assert address in joined
            assert "Not yet transcribed" not in joined and not result["overflow"] and not result["errors"]
            result["screenshot"] = str(screenshot(cdp, "goal-ff8-vanilla-formulae.png"))
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    print(json.dumps({"executable": verify_executable(),
                      "formulae": verify_source_and_render()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
