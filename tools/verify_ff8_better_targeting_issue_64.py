"""Static and mutation contract for FF8 Better Targeting."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import shutil
import struct
import sys
import tempfile

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import better_targeting_issue_64 as targeting, gameplay_settings  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX = ROOT / "_scratch/ffnx-upstream"
APPLICATOR = ROOT / "games/ff8/ffnx_better_targeting/apply_to_ffnx.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def relative_target(code: bytes, offset: int, address: int) -> int:
    displacement = int.from_bytes(code[offset + 1:offset + 5], "little", signed=True)
    return address + offset + 5 + displacement


def relative_calls_to(pe: pefile.PE, target: int) -> set[int]:
    section = next(
        item for item in pe.sections if item.Name.rstrip(b"\0") == b".text"
    )
    image = pe.get_memory_mapped_image()
    start = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
    data = image[section.VirtualAddress:section.VirtualAddress + section.Misc_VirtualSize]
    calls = set()
    for offset in range(len(data) - 4):
        if data[offset] != 0xE8:
            continue
        destination = start + offset + 5 + struct.unpack_from("<i", data, offset + 1)[0]
        if destination == target:
            calls.add(start + offset)
    return calls


def make_fixture(destination: Path) -> None:
    for relative in ("src/cfg.cpp", "src/cfg.h", "src/ff8_opengl.cpp", "misc/FFNx.toml"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FFNX / relative, target)


def verify_applied(root: Path) -> None:
    cfg = (root / "src/cfg.cpp").read_text(encoding="utf-8")
    opengl = (root / "src/ff8_opengl.cpp").read_text(encoding="utf-8")
    toml = (root / "misc/FFNx.toml").read_text(encoding="utf-8")
    require('enable_ff8_better_targeting = config["enable_ff8_better_targeting"].value_or(false);' in cfg,
            "Better Targeting must fail closed")
    require("enable_ff8_better_targeting = false" in toml,
            "packaged Better Targeting must be off")
    require("opaque_target_marker = 0x80000000U" in opengl,
            "FFNx marker consumer is missing")
    require("icon_id == 0" in opengl and "force_opaque" in opengl,
            "FFNx must limit opacity to the marked hand")
    require("const int descriptor_alpha = force_opaque ? 0" in opengl,
            "FFNx must suppress the descriptor ABE contribution")
    require("a6) & ~opaque_target_marker" in opengl,
            "FFNx must remove the marker before primitive construction")


def main() -> int:
    require(EXE.is_file(), "supported FF8_EN.exe is missing")
    require(sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256,
            "installed FF8_EN.exe is not the supported Steam English build")
    pe = pefile.PE(str(EXE), fast_load=True)
    require(image_bytes(pe, targeting.TARGET_ICON_HOOK, 5) == targeting.TARGET_ICON_HOOK_ORIGINAL,
            "target-label renderer call changed")
    require(image_bytes(pe, 0x004AB0D7, 2) == bytes.fromhex("6A 0F"),
            "battle target labels are no longer icon 15")
    require(image_bytes(pe, 0x004B75B0, 18) == bytes.fromhex(
        "8B 44 24 10 56 3D 80 00 00 00 7C 2D 3D 8C 00 00 00 7D"
    ), "native icon renderer dispatch changed")
    require(image_bytes(pe, 0x004B7634, 8) == bytes.fromhex("0B C3 81 C1 00 00 10 38"),
            "native final primitive-command merge changed")
    require(relative_calls_to(pe, 0x004B75B0) == {
        0x004A1485, 0x004A18BC, 0x004AB0DC, 0x004B2864,
    }, "native renderer call-site set changed")
    require(relative_calls_to(pe, 0x004A2F80) == {
        0x004B7250, 0x004B74CD, 0x004B75DD,
        0x004B76CF, 0x004B77ED, 0x004B78FD,
    }, "special battle-icon renderer call-site set changed")
    # Of all four direct 004B75B0 calls, only the battle target-chain loop
    # supplies literal icon 15. The others select icons dynamically.
    require(image_bytes(pe, 0x004AB0D7, 5) == bytes.fromhex("6A 0F 50 55 51"),
            "target-label icon argument or call layout changed")

    code = targeting.build_code_cave()
    require(targeting.build_hext(False) == "", "disabled tweak emitted a patch")
    require(len(code) == targeting.CODE_CAVE_LENGTH == 0x25,
            "selected-target wrapper length changed")
    require(code.startswith(bytes.fromhex("0F B6 05 44 68 D7 01 39 F0 75 15")),
            "selected-target gate changed")
    require(bytes.fromhex("C7 44 24 10 00 00 00 00") in code,
            "selected label is not changed to hand icon 0")
    require(bytes.fromhex("81 4C 24 1C 00 00 00 80") in code,
            "selected hand call is not marked")
    require(relative_target(code, 27, targeting.CODE_CAVE) == targeting.ICON_RENDERER,
            "selected hand does not tail-call FFNx's replaced renderer entry")
    require(code.endswith(bytes.fromhex("8B 44 24 08 C3")),
            "unselected labels are not skipped")

    ffnx_source = (FFNX / "src/ff8_opengl.cpp").read_text(encoding="utf-8")
    require("replace_function(ff8_externals.ff8_draw_icon_or_key3, ff8_draw_icon_or_key3);" in ffnx_source,
            "official FFNx no longer replaces the native renderer entry")
    require("draw_infos->field_8 = no_a6_mask ? a6 |" in ffnx_source,
            "official FFNx primitive opacity path changed")

    module_source = (ROOT / "games/ff8/better_targeting_issue_64.py").read_text(encoding="utf-8")
    require("OPACITY_HOOK" not in module_source and "0x004B7622" not in module_source,
            "disproved native-body opacity hook returned")
    require("bit 31 of a6" in module_source.lower(),
            "selected-call marker evidence is missing")

    spec = importlib.util.spec_from_file_location("apply_ffnx_targeting", APPLICATOR)
    require(spec is not None and spec.loader is not None, "cannot load FFNx applicator")
    applicator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(applicator)
    with tempfile.TemporaryDirectory() as temporary:
        fixture = Path(temporary)
        make_fixture(fixture)
        applicator.apply(fixture, check_revision=False)
        verify_applied(fixture)
        applied_opengl = (fixture / "src/ff8_opengl.cpp").read_text(encoding="utf-8")
        marker_at = applied_opengl.index("opaque_target_marker")
        require(applied_opengl.rfind("ff8_draw_icon_or_key3", 0, marker_at) >= 0 and
                applied_opengl.find("ff8_draw_icon_or_key4", marker_at) > marker_at,
                "marker consumer is not inside FFNx wrapper 3 for native 004B75B0")
        cfg = fixture / "src/cfg.cpp"
        cfg.write_text(cfg.read_text(encoding="utf-8").replace(
            'enable_ff8_better_targeting"].value_or(false)',
            'enable_ff8_better_targeting"].value_or(true)', 1), encoding="utf-8")
        try:
            verify_applied(fixture)
        except AssertionError:
            pass
        else:
            raise AssertionError("default-on mutation was accepted")

    for old, new in (("icon_id == 0", "icon_id >= 0"),
                     ("force_opaque ? 0", "force_opaque ? 1")):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            make_fixture(fixture)
            applicator.apply(fixture, check_revision=False)
            source_path = fixture / "src/ff8_opengl.cpp"
            source_path.write_text(source_path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
            try:
                verify_applied(fixture)
            except AssertionError:
                pass
            else:
                raise AssertionError(f"FFNx mutation was accepted: {old}")

    mutated = code.replace(
        bytes.fromhex("81 4C 24 1C 00 00 00 80"),
        bytes.fromhex("81 4C 24 1C 00 00 00 00"), 1,
    )
    require(bytes.fromhex("81 4C 24 1C 00 00 00 80") not in mutated,
            "marker mutation was not effective")

    patch = targeting.build_hext(True)
    require(f"{targeting.TARGET_ICON_HOOK:X} = E8" in patch, "target hook is missing")
    require("4B7622" not in patch and "Force icon 0 opaque" not in patch,
            "disproved native opacity patch was emitted")
    for invalid in (0, 1, "true", None):
        try:
            targeting.build_hext(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Better Targeting accepted {invalid!r}")

    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / "FFNx.toml"
        config.write_text("enable_devtools = false\n", encoding="utf-8")
        gameplay_settings._set_ffnx_runtime_tweaks(
            config, xp_bars=False, hp_bars=False, better_targeting=True,
        )
        require("enable_ff8_better_targeting = true" in config.read_text(encoding="utf-8"),
                "launch activation did not enable the derivative renderer path")

    print("FF8 Better Targeting renderer replacement and old-hook ban passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
