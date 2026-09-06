"""Verify the packaged and installed FFNx derivative for issue 51."""

from __future__ import annotations

import hashlib
import json
from xml.etree import ElementTree
from pathlib import Path
import re
import struct


SCHEMA_VERSION = 2
DISTRIBUTION = "lexeditor-ffnx-derivative"
SOURCE_COMMIT = "c056db2783f376a340fcefa6a48cc33618998876"
SUPPORTED_GAME_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
EXPECTED_HOOK_COUNT = 28
# The integration lane fills these from the final reviewed runtime-on package.
# Empty values keep the package unavailable; a manifest cannot authorize itself.
PINNED_ARTIFACT_SHA256 = {
    "driver": "cf237e90a3c0a099c5182e58561e6469951bf2a493bc8a346938aceff2ab0e77",
    "license": "230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809",
    "sourcePatch": "9516488302f5eb352ec5e4162bffc6f540fac6150645eb6f040597332219cf79",
    "buildReport": "71130241329dfa8a74bdb67e126e0fac8da8060d316495a5034f1ea0cb1fbb4a",
    # Steamworks redistributable, shipped verbatim under the name FFNx loads
    # it by. FFNx refuses to run unless this file is signed or matches its
    # own pinned SHA-1 03bd9f3e352553a0af41f5fe006f6249a168c243.
    "steamApi": "abfedd473b3f4a9597bbdc90d20f4b6f696bb2ebb937a03177461df695430ad6",
}
DRIVER_NAME = "AF3DN.P"
# FFNx loads Steamworks dynamically from this exact filename (src/steam.cpp)
# and forces achievements on for the Steam edition, so the game cannot start
# without it. Shipping it is what makes the derivative work on a Steam copy.
STEAM_API_NAME = "FFNx_steam_api.dll"
STEAM_API_SHA1 = "03bd9f3e352553a0af41f5fe006f6249a168c243"
# The driver and the shader set are two halves of ONE FFNx version. Installing
# our derivative over another version's shaders makes it ask for shaders that
# set does not contain (yuvmovie, post.ntscj) and the game dies at renderer
# init with "shader not found". They must ship and install together.
SHADER_DIR_NAME = "shaders"
PACKAGE_ROOT = Path(__file__).resolve().parent / "package"
MANIFEST_NAME = "runtime-manifest.json"
FEATURE = "sharedMagicInventory"
MACHINE_I386 = 0x014C
OPTIONAL_MAGIC_PE32 = 0x010B
REQUIRED_EXPORTS = frozenset({
    "new_dll_graphics_driver",
    "lexeditor_issue_51_identity",
    "lexeditor_issue_51_hook_count",
    "lexeditor_issue_51_runtime_requested",
    "lexeditor_issue_51_compile_gate_enabled",
    "lexeditor_issue_51_config_contract",
    "lexeditor_issue_51_config_version",
    "lexeditor_issue_51_core_linked",
})
CONFIG_CONTRACT_IDENTITY = (
    "Lexeditor issue 51 config: "
    "<basedir>/<direct_mode_path>/lexeditor/gameplay.toml; "
    "schemaVersion=1; sharedMagicInventory=bool; magicStockLimit=int[1,255]; "
    "missing=false; invalid=false; unknown=false"
)
_KEYS = {
    "schemaVersion", "distribution", "sourceCommit", "driver",
    "driverSha256", "architecture", "runtimeEnabled", "hookCount",
    "identity", "exports", "provenance",
}
_PROVENANCE_KEYS = {
    "license", "licenseSha256", "sourcePatch", "sourcePatchSha256",
    "buildReport", "buildReportSha256",
}
_PROVENANCE_FILES = {
    "license": "COPYING.TXT",
    "sourcePatch": "ISSUE51_DERIVATIVE_SOURCE.patch",
    "buildReport": "ISSUE51_BUILD_REPORT.md",
}


class RuntimePackageError(ValueError):
    """Raised when a derivative package does not prove its identity."""


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hex_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value, re.I):
        raise RuntimePackageError(f"The Lexeditor FFNx {label} hash is invalid")
    return value.casefold()


def _read_u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise RuntimePackageError("The packaged FFNx driver has a truncated PE header")
    return struct.unpack_from("<H", data, offset)[0]


def _read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise RuntimePackageError("The packaged FFNx driver has a truncated PE header")
    return struct.unpack_from("<I", data, offset)[0]


def _pe_exports(driver: Path) -> tuple[bytes, dict[str, int]]:
    """Return file offsets for named exports after proving PE32 x86."""
    data = driver.read_bytes()
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise RuntimePackageError("The packaged FFNx driver is not a PE file")
    pe = _read_u32(data, 0x3C)
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise RuntimePackageError("The packaged FFNx driver has no valid PE header")
    machine = _read_u16(data, pe + 4)
    section_count = _read_u16(data, pe + 6)
    optional_size = _read_u16(data, pe + 20)
    characteristics = _read_u16(data, pe + 22)
    optional = pe + 24
    if machine != MACHINE_I386 or _read_u16(data, optional) != OPTIONAL_MAGIC_PE32:
        raise RuntimePackageError("The packaged FFNx driver is not a PE32 x86 binary")
    if not characteristics & 0x2000:
        raise RuntimePackageError("The packaged FFNx driver is not marked as a DLL")
    if optional_size < 104 or optional + optional_size > len(data):
        raise RuntimePackageError("The packaged FFNx driver has an invalid optional header")
    export_rva = _read_u32(data, optional + 96)
    export_size = _read_u32(data, optional + 100)
    sections = optional + optional_size
    if not export_rva or not export_size or not 1 <= section_count <= 96:
        raise RuntimePackageError("The packaged FFNx driver has no usable export table")

    def rva_offset(rva: int, size: int = 1) -> int:
        for index in range(section_count):
            base = sections + index * 40
            if base + 40 > len(data):
                break
            virtual_size = _read_u32(data, base + 8)
            virtual_address = _read_u32(data, base + 12)
            raw_size = _read_u32(data, base + 16)
            raw_offset = _read_u32(data, base + 20)
            span = max(virtual_size, raw_size)
            if virtual_address <= rva and rva + size <= virtual_address + span:
                offset = raw_offset + (rva - virtual_address)
                if offset + size <= len(data):
                    return offset
        raise RuntimePackageError("The packaged FFNx export table points outside the PE image")

    # An earlier version of this guard checked the IMPORT DIRECTORY for
    # steam_api.dll and rejected the driver when it was absent, on the theory
    # that a "non-Steam variant" had been built. That was wrong, and it was
    # rejecting a perfectly good driver. FFNx never links the Steamworks SDK
    # statically: src/steam.cpp resolves every entry point at runtime with
    # LoadLibraryA("FFNx_steam_api.dll") plus GetProcAddress, so NO FFNx build
    # has ever carried a steam_api import - the official ones included. There
    # is no build-time Steam variant to select; Steam handling is runtime code
    # and the CMake build has no such switch.
    # What actually matters is that the dynamic loader path is present, so
    # that is what we check.
    if b"FFNx_steam_api.dll" not in data:
        raise RuntimePackageError(
            "The packaged FFNx driver has no Steam loader path, so it cannot "
            "run this Steam copy of Final Fantasy VIII")

    export = rva_offset(export_rva, 40)
    name_count = _read_u32(data, export + 24)
    functions_rva = _read_u32(data, export + 28)
    names_rva = _read_u32(data, export + 32)
    ordinals_rva = _read_u32(data, export + 36)
    if not 1 <= name_count <= 16384:
        raise RuntimePackageError("The packaged FFNx driver has an invalid named-export count")
    names = rva_offset(names_rva, name_count * 4)
    ordinals = rva_offset(ordinals_rva, name_count * 2)
    function_count = _read_u32(data, export + 20)
    if not 1 <= function_count <= 16384:
        raise RuntimePackageError("The packaged FFNx driver has an invalid export count")
    functions = rva_offset(functions_rva, function_count * 4)
    result: dict[str, int] = {}
    for index in range(name_count):
        name_rva = _read_u32(data, names + index * 4)
        start = rva_offset(name_rva)
        end = data.find(b"\0", start, min(len(data), start + 512))
        if end < 0:
            raise RuntimePackageError("The packaged FFNx driver has an invalid export name")
        try:
            name = data[start:end].decode("ascii", errors="strict")
        except UnicodeError as error:
            raise RuntimePackageError("The packaged FFNx driver has a non-ASCII export") from error
        ordinal = _read_u16(data, ordinals + index * 2)
        if ordinal >= function_count:
            raise RuntimePackageError("The packaged FFNx driver has an invalid export ordinal")
        function_rva = _read_u32(data, functions + ordinal * 4)
        if export_rva <= function_rva < export_rva + export_size:
            raise RuntimePackageError("The packaged FFNx runtime contract uses a forwarded export")
        result[name] = rva_offset(function_rva)
    return data, result


def _constant_export(data: bytes, offset: int, *, boolean: bool = False) -> int | None:
    """Read a small optimized constant-return export without loading the DLL."""
    cursor = offset
    for _ in range(4):
        while cursor < len(data) and data[cursor] in {0x90, 0xCC}:
            cursor += 1
        if cursor + 5 <= len(data) and data[cursor] == 0xE9:
            relative = struct.unpack_from("<i", data, cursor + 1)[0]
            cursor = cursor + 5 + relative
            continue
        if cursor + 2 <= len(data) and data[cursor] == 0xEB:
            relative = struct.unpack_from("<b", data, cursor + 1)[0]
            cursor = cursor + 2 + relative
            continue
        break
    if boolean and data[cursor:cursor + 3] == b"\xB0\x01\xC3":
        return 1
    if data[cursor:cursor + 2] == b"\x33\xC0" and data[cursor + 2:cursor + 3] == b"\xC3":
        return 0
    if data[cursor:cursor + 6].startswith(b"\xB8") and data[cursor + 5:cursor + 6] == b"\xC3":
        return _read_u32(data, cursor + 1)
    return None


def _file_offset_va(data: bytes, offset: int) -> int:
    """Translate one raw PE file offset to its loaded virtual address."""
    pe = _read_u32(data, 0x3C)
    section_count = _read_u16(data, pe + 6)
    optional_size = _read_u16(data, pe + 20)
    optional = pe + 24
    image_base = _read_u32(data, optional + 28)
    sections = optional + optional_size
    for index in range(section_count):
        section = sections + index * 40
        virtual_address = _read_u32(data, section + 12)
        raw_size = _read_u32(data, section + 16)
        raw_offset = _read_u32(data, section + 20)
        if raw_offset <= offset < raw_offset + raw_size:
            return image_base + virtual_address + (offset - raw_offset)
    raise RuntimePackageError("The packaged FFNx identity string is outside its PE sections")


def _pointer_export_string(data: bytes, offset: int, expected: str) -> bool:
    """Prove that an export returns the exact embedded NUL-terminated string."""
    encoded = expected.encode("ascii") + b"\0"
    positions = []
    cursor = 0
    while True:
        cursor = data.find(encoded, cursor)
        if cursor < 0:
            break
        positions.append(cursor)
        cursor += len(encoded)
    if len(positions) != 1:
        return False
    cursor = offset
    for _ in range(4):
        while cursor < len(data) and data[cursor] in {0x90, 0xCC}:
            cursor += 1
        if cursor + 5 <= len(data) and data[cursor] == 0xE9:
            cursor = cursor + 5 + struct.unpack_from("<i", data, cursor + 1)[0]
            continue
        if cursor + 2 <= len(data) and data[cursor] == 0xEB:
            cursor = cursor + 2 + struct.unpack_from("<b", data, cursor + 1)[0]
            continue
        break
    if data[cursor:cursor + 1] != b"\xB8" or data[cursor + 5:cursor + 6] != b"\xC3":
        return False
    returned = _read_u32(data, cursor + 1)
    return returned == _file_offset_va(data, positions[0])


def _pinned_hash(name: str) -> str:
    value = PINNED_ARTIFACT_SHA256.get(name, "")
    if not re.fullmatch(r"[0-9a-f]{64}", value, re.I):
        raise RuntimePackageError("The reviewed Lexeditor FFNx artifact lock is not populated")
    return value.casefold()


def verify_game_installation(game_root: Path) -> Path:
    """Return the supported executable or reject the target installation."""
    executable = Path(game_root).resolve() / "FF8_EN.exe"
    if not executable.is_file():
        raise RuntimePackageError(f"FF8_EN.exe is missing from {executable.parent}")
    if _sha256(executable) != SUPPORTED_GAME_SHA256:
        raise RuntimePackageError(
            "The installed FF8_EN.exe build is not supported by the shared-Magic runtime"
        )
    return executable


def _verify_provenance(root: Path, data: dict, driver_hash: str,
                       identity: str) -> dict:
    provenance = data.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_KEYS:
        raise RuntimePackageError("The Lexeditor FFNx provenance manifest is incomplete")
    verified: dict[str, str] = {}
    for key, expected_name in _PROVENANCE_FILES.items():
        if provenance.get(key) != expected_name:
            raise RuntimePackageError(f"The Lexeditor FFNx {key} artifact name is invalid")
        target = root / expected_name
        if not target.is_file():
            raise RuntimePackageError(f"The Lexeditor FFNx {key} artifact is missing")
        expected_hash = _hex_digest(provenance.get(f"{key}Sha256"), key)
        if expected_hash != _pinned_hash(key) or _sha256(target) != expected_hash:
            raise RuntimePackageError(f"The Lexeditor FFNx {key} artifact does not match its hash")
        verified[f"{key}Path"] = str(target)
        verified[f"{key}Sha256"] = expected_hash

    try:
        license_text = (root / _PROVENANCE_FILES["license"]).read_text(
            encoding="utf-8", errors="strict",
        )
        patch_text = (root / _PROVENANCE_FILES["sourcePatch"]).read_text(
            encoding="utf-8", errors="strict",
        )
        report_text = (root / _PROVENANCE_FILES["buildReport"]).read_text(
            encoding="utf-8", errors="strict",
        )
    except (OSError, UnicodeError) as error:
        raise RuntimePackageError("The Lexeditor FFNx provenance text is unreadable") from error
    if "GNU GENERAL PUBLIC LICENSE" not in license_text or len(license_text) < 10_000:
        raise RuntimePackageError("The Lexeditor FFNx package does not include the GPL license")
    required_patch_markers = (
        SOURCE_COMMIT, "lexeditor_shared_magic", "shared_magic_runtime",
        "FFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME", "lexeditor_ff8_bars",
        "enable_ff8_better_targeting", "version_suffix",
        "std::sort(entries.begin(), entries.end()",
        "filename().generic_string()",
        "lexeditor_live_conditions", "FFNX_LEXEDITOR_LIVE_CONDITIONS",
        "VirtualQuery", "ReadProcessMemory",
        "lexeditor/conditional-variants/",
    )
    if not patch_text.startswith("diff --git ") or any(
        marker not in patch_text for marker in required_patch_markers
    ):
        raise RuntimePackageError("The Lexeditor FFNx source patch does not prove the runtime changes")
    required_report_markers = (SOURCE_COMMIT, identity, driver_hash, "runtime=on")
    if any(marker not in report_text for marker in required_report_markers):
        raise RuntimePackageError("The Lexeditor FFNx build report does not match the packaged driver")
    return verified


def _embedded_manifest(driver_data: bytes) -> str | None:
    """Return the driver's embedded Win32 assembly manifest, if it has one."""
    start = driver_data.find(b"<assembly")
    if start < 0:
        return None
    end = driver_data.find(b"</assembly>", start)
    if end < 0:
        return None
    try:
        return driver_data[start:end + len(b"</assembly>")].decode("utf-8", "strict")
    except UnicodeError:
        return ""


def _reject_unloadable_manifest(driver_data: bytes) -> None:
    """Refuse a driver whose embedded manifest Windows cannot parse.

    This is the check that was missing when a rebuilt derivative shipped a
    manifest reading `<assemblyIdentity "type='win32'` - one stray quote. Every
    hash, export and identity check passed, because none of them ask the
    question the OS asks: SideBySide parses this XML before the DLL loads, and
    on a syntax error it refuses to load it at all. FF8 then exits before it
    draws a frame and the launcher simply reappears, with nothing in FFNx.log
    because FFNx never ran.
    """
    manifest = _embedded_manifest(driver_data)
    if manifest is None:
        return
    try:
        ElementTree.fromstring(manifest)
    except ElementTree.ParseError as error:
        raise RuntimePackageError(
            "The packaged Lexeditor FFNx driver has a malformed embedded manifest, "
            f"which Windows refuses to load: {error}"
        ) from error


def verify(package_root: Path = PACKAGE_ROOT) -> dict:
    """Return a verified package manifest or reject the package."""
    root = Path(package_root).resolve()
    manifest_path = root / MANIFEST_NAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise RuntimePackageError("The Lexeditor FFNx runtime manifest is missing or invalid") from error
    if not isinstance(data, dict) or set(data) != _KEYS:
        raise RuntimePackageError("The Lexeditor FFNx runtime manifest has unknown or missing keys")
    if data["schemaVersion"] != SCHEMA_VERSION or isinstance(data["schemaVersion"], bool):
        raise RuntimePackageError("The Lexeditor FFNx runtime manifest schema is not supported")
    if data["distribution"] != DISTRIBUTION:
        raise RuntimePackageError("The FFNx package is not the Lexeditor derivative")
    if data["sourceCommit"] != SOURCE_COMMIT:
        raise RuntimePackageError("The Lexeditor FFNx source commit is not the supported pinned commit")
    if data["driver"] != DRIVER_NAME:
        raise RuntimePackageError("The Lexeditor FFNx package names an unsupported driver")
    if data["architecture"] != "x86" or data["runtimeEnabled"] is not True:
        raise RuntimePackageError("The Lexeditor FFNx package is not a runtime-enabled x86 build")
    hook_count = data["hookCount"]
    if isinstance(hook_count, bool) or hook_count != EXPECTED_HOOK_COUNT:
        raise RuntimePackageError("The Lexeditor FFNx hook count is invalid")
    identity = (
        f"Lexeditor issue 51 shared magic core; base={SOURCE_COMMIT}; "
        f"runtime=on; hooks={hook_count}"
    )
    if data["identity"] != identity:
        raise RuntimePackageError("The Lexeditor FFNx runtime identity is invalid")
    exports = data["exports"]
    if not isinstance(exports, list) or len(exports) != len(set(exports)) or set(exports) != REQUIRED_EXPORTS:
        raise RuntimePackageError("The Lexeditor FFNx export manifest is invalid")
    expected_hash = _hex_digest(data["driverSha256"], "driver")
    driver = root / DRIVER_NAME
    if expected_hash != _pinned_hash("driver"):
        raise RuntimePackageError("The Lexeditor FFNx driver is not the reviewed pinned artifact")
    if not driver.is_file() or _sha256(driver) != expected_hash:
        raise RuntimePackageError("The packaged Lexeditor FFNx driver does not match its manifest")
    driver_data, actual_exports = _pe_exports(driver)
    _reject_unloadable_manifest(driver_data)
    required_driver_markers = (
        b"enable_ff8_better_targeting",
        b"enable_ff8_xp_bars",
        b"enable_ff8_hp_bars",
        b"lexeditor/live-conditions.json",
        b"lexeditor/conditional-variants/",
        b"ready: final variants precomposed",
    )
    if any(marker not in driver_data for marker in required_driver_markers):
        raise RuntimePackageError(
            "The packaged Lexeditor FFNx driver is missing a registered managed module"
        )
    missing_exports = sorted(REQUIRED_EXPORTS - set(actual_exports))
    if missing_exports:
        raise RuntimePackageError(
            "The packaged Lexeditor FFNx driver is missing exports: " + ", ".join(missing_exports)
        )
    if not _pointer_export_string(
        driver_data, actual_exports["lexeditor_issue_51_identity"], identity,
    ):
        raise RuntimePackageError("The packaged Lexeditor FFNx identity export returns the wrong value")
    if not _pointer_export_string(
        driver_data,
        actual_exports["lexeditor_issue_51_config_contract"],
        CONFIG_CONTRACT_IDENTITY,
    ):
        raise RuntimePackageError("The packaged Lexeditor FFNx config export returns the wrong value")
    if _constant_export(
        driver_data, actual_exports["lexeditor_issue_51_hook_count"],
    ) != EXPECTED_HOOK_COUNT:
        raise RuntimePackageError("The packaged Lexeditor FFNx hook-count export is not 28")
    if _constant_export(
        driver_data, actual_exports["lexeditor_issue_51_compile_gate_enabled"], boolean=True,
    ) != 1:
        raise RuntimePackageError("The packaged Lexeditor FFNx compile gate is not enabled")
    if _constant_export(
        driver_data, actual_exports["lexeditor_issue_51_core_linked"], boolean=True,
    ) != 1:
        raise RuntimePackageError("The packaged Lexeditor FFNx core-linked export is not enabled")
    if _constant_export(
        driver_data, actual_exports["lexeditor_issue_51_config_version"],
    ) != 1:
        raise RuntimePackageError("The packaged Lexeditor FFNx config version is not 1")
    steam_api = root / STEAM_API_NAME
    steam_api_hash = _pinned_hash("steamApi")
    if not steam_api.is_file() or _sha256(steam_api) != steam_api_hash:
        raise RuntimePackageError(
            "The packaged Steamworks library is missing or altered. FFNx will "
            "not start on a Steam copy of FF8 without it.")
    if _sha1(steam_api) != STEAM_API_SHA1:
        # FFNx checks this SHA-1 itself and shows a fatal error dialog on a
        # mismatch, so a wrong file here breaks the game rather than a feature.
        raise RuntimePackageError(
            "The packaged Steamworks library is not the build FFNx accepts")
    shader_root = root / SHADER_DIR_NAME
    shaders = sorted(f for f in shader_root.glob("*") if f.is_file()) if shader_root.is_dir() else []
    if len(shaders) < 160:
        raise RuntimePackageError(
            "The Lexeditor FFNx package is missing the shader set built with "
            "its driver, without which the game cannot start")
    provenance = _verify_provenance(root, data, expected_hash, identity)
    return {
        **data,
        "packagedSteamApi": str(steam_api),
        "packagedShaderRoot": str(shader_root),
        "shaderDirName": SHADER_DIR_NAME,
        "shaderCount": len(shaders),
        "steamApiName": STEAM_API_NAME,
        "steamApiSha256": steam_api_hash,
        "driverSha256": expected_hash,
        "manifest": str(manifest_path),
        "manifestSha256": _sha256(manifest_path),
        "packagedDriver": str(driver),
        "verifiedExports": sorted(actual_exports),
        **provenance,
    }


def status(game_root: Path, package_root: Path = PACKAGE_ROOT) -> dict:
    """Prove that the target and installed driver match the verified package."""
    try:
        package = verify(package_root)
    except RuntimePackageError as error:
        return {
            "packageAvailable": False,
            "available": False,
            "pinned": False,
            "message": str(error),
        }
    try:
        verify_game_installation(game_root)
    except RuntimePackageError as error:
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": str(error),
        }
    root = Path(game_root).resolve()
    if not (root / "FFNx.toml").is_file():
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": "FFNx.toml is missing from the target FF8 installation.",
        }
    installed = root / DRIVER_NAME
    if not installed.is_file():
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": "The packaged Lexeditor FFNx derivative is not installed.",
        }
    installed_steam_api = root / STEAM_API_NAME
    if not installed_steam_api.is_file() or _sha1(installed_steam_api) != STEAM_API_SHA1:
        # Reporting the runtime healthy without this file would put a green
        # light on a game that shows a fatal FFNx dialog on launch.
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": (
                f"{STEAM_API_NAME} is missing or not the build FFNx accepts. "
                "Reinstall the Lexeditor FFNx runtime."
            ),
        }
    if _sha256(installed) != package["driverSha256"]:
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": "The installed FFNx driver is not the verified Lexeditor derivative.",
        }
    try:
        _installed_data, installed_exports = _pe_exports(installed)
    except RuntimePackageError as error:
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": str(error),
        }
    if not REQUIRED_EXPORTS.issubset(set(installed_exports)):
        return {
            "packageAvailable": True,
            "available": False,
            "pinned": False,
            "message": "The installed FFNx derivative does not expose the required runtime contract.",
        }
    return {
        "packageAvailable": True,
        "available": True,
        "pinned": True,
        "message": "The complete Lexeditor shared-Magic runtime is installed.",
        "driverSha256": package["driverSha256"],
        "sourceCommit": package["sourceCommit"],
        "manifest": package["manifest"],
        "manifestSha256": package["manifestSha256"],
        "hookCount": package["hookCount"],
    }
