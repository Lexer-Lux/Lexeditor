"""Verify issue #51's lossless core and fail-closed integration boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = ROOT / "games" / "ff8" / "shared_magic_issue_51.py"
CORE_ROOT = ROOT / "games" / "ff8" / "ffnx_issue_51"
AUDIT_PATH = CORE_ROOT / "audit_magic_accesses.py"
INSTALLED_EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("shared_magic_issue_51", MODULE_PATH)
    require(spec is not None and spec.loader is not None, "cannot load shared magic build gate")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PHASE_GUARDS = {
    "verify_live_mirror": "state.phase != RuntimePhase::shared_mirror",
    "mirror_canonical": "state.phase != RuntimePhase::shared_mirror",
    "restore_canonical_mirror": "state.phase != RuntimePhase::shared_mirror",
    "reconcile_from_inventory": "state.phase != RuntimePhase::shared_mirror",
    "suspend_for_private_scenario": "state.phase != RuntimePhase::shared_mirror",
    "resume_after_private_scenario": "state.phase != RuntimePhase::scenario_private",
    "begin_canonical_save": "state.phase != RuntimePhase::shared_mirror",
    "finish_canonical_save": "state.phase != RuntimePhase::save_canonical",
}


def function_body(source: str, name: str) -> str:
    marker = f" {name}("
    position = source.find(marker)
    require(position >= 0, f"missing runtime function: {name}")
    opening = source.find("{", position)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening:index + 1]
    raise AssertionError(f"unterminated runtime function: {name}")


def verify_cpp_contract() -> None:
    header = (CORE_ROOT / "shared_magic_core.h").read_text(encoding="utf-8")
    source = (CORE_ROOT / "shared_magic_core.cpp").read_text(encoding="utf-8")
    test = (CORE_ROOT / "shared_magic_core_test.cpp").read_text(encoding="utf-8")
    cmake = (CORE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

    for token in (
        "kCharacterCount = 8",
        "kSlotCount = 32",
        "kDefaultStockLimit = 100",
        "try_merge",
        "migrate_to_canonical",
        "ActivationResult",
        "request_activation",
        "migration_warning_template",
        "add_stock",
        "consume_stock",
    ):
        require(token in header, f"missing C++ contract token: {token}")

    require("totals[slot.id] > stock_limit" in source, "configured stock overflow is not rejected")
    require("state.stock_limit" in source, "runtime state does not own the configured stock limit")
    require("std::to_string(static_cast<unsigned int>(stock_limit))" in source,
            "stock-overflow warning does not report the configured limit")
    require("distinct >= kSlotCount" in source, "33rd distinct spell is not rejected")
    require("source[0] = result.inventory" in source, "canonical migration is missing")
    require("if (!result)" in source, "migration does not gate writes on a successful merge")
    require("assert(overstock == overstock_before)" in test, "failure atomicity is not tested")
    require("assert(too_many == too_many_before)" in test, "slot overflow atomicity is not tested")
    require("assert(!blocked.shared_pool_active)" in test, "blocked activation state is not tested")
    require("assert(retry.shared_pool_active)" in test, "later lossless activation is not tested")
    require("No Magic was changed." in source, "migration warning does not promise atomicity")
    require("add_test(NAME shared_magic_core" in cmake, "the C++ core has no reproducible CTest")

    for name, guard in PHASE_GUARDS.items():
        body = function_body(source, name)
        require(guard in body, f"missing runtime phase guard: {name}")
        mutated_body = body.replace(guard, "", 1)
        mutant = source.replace(body, mutated_body, 1)
        try:
            for checked_name, checked_guard in PHASE_GUARDS.items():
                require(checked_guard in function_body(mutant, checked_name),
                        f"missing runtime phase guard: {checked_name}")
        except AssertionError:
            pass
        else:
            raise AssertionError(f"runtime phase-guard mutation survived: {name}")
    for clause in (
        "PrivateInventories candidate = source;",
        "source = candidate;",
        "state.phase = RuntimePhase::scenario_private;",
        "write_mirror(source, state.canonical_snapshot);",
        "source[0] = canonical;",
        "state.phase = RuntimePhase::save_canonical;",
        "source[0] != state.canonical_snapshot",
        "return inventory == state.canonical_snapshot;",
    ):
        require(clause in source, f"missing runtime transition clause: {clause}")
    for clause in (
        "assert(!begin_canonical_save(runtime, live));",
        "assert(!reconcile_from_character(runtime, live, 0));",
        "assert(blocked_live == blocked_live_before);",
        "assert(!verify_live_mirror(runtime, live));",
        "assert(restore_canonical_mirror(runtime, live));",
    ):
        require(clause in test, f"missing runtime phase/atomicity test: {clause}")


def verify_executable_access_audit() -> None:
    if not INSTALLED_EXE.is_file():
        return
    spec = importlib.util.spec_from_file_location("audit_magic_accesses", AUDIT_PATH)
    require(spec is not None and spec.loader is not None, "cannot load access audit")
    audit = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = audit
    spec.loader.exec_module(audit)
    references = audit.find_direct_references(INSTALLED_EXE, magic_only=True)
    require(len(references) == 271, "verified executable direct-reference count changed")
    writes = [reference for reference in references if reference.writes_magic]
    require(len(writes) == 50, "verified direct magic-write count changed")
    addresses = {reference.address for reference in references}
    for address in (0x004BE7C6, 0x004F006D, 0x0054F1E1, 0x0056DB55):
        require(address in addresses, f"known direct magic reference disappeared: 0x{address:08X}")

    # The former same-block contract was false: it found four constructors and
    # cleared provenance before the real cross-block writes. Pin every proved
    # derived, callback, constructor, normalizer, and bulk writer family.
    expected_families = {
        "battle_to_saved_commit",
        "saved_inventory_swap",
        "battle_callback_transaction",
        "initial_inventory_constructor",
        "script_inventory_constructor",
        "battle_actor_clear",
        "saved_stock_normalizer",
        "transfer_zero_cleanup",
        "field_magic_reorder",
        "field_controller_snapshot_restore",
        "field_add_inner",
        "battle_magic_prepare",
        "battle_magic_clear_actor",
        "stock_add_core",
        "stock_remove_core",
        "magic_menu_remove_inner",
        "magic_menu_transfer_source_inner",
        "magic_menu_transfer_target_inner",
        "magic_menu_swap_inner",
        "transfer_clear_inner",
        "transfer_move",
        "transfer_swap_inner",
        "transfer_restore_inner",
        "draw_commit_inner",
        "redistribution_sum",
    }
    require(
        {family.name for family in audit.PROVED_WRITER_FAMILIES} == expected_families,
        "proved writer-family contract changed",
    )
    require(
        not audit.missing_proved_writer_families(INSTALLED_EXE),
        "a proved writer-family instruction guard changed",
    )
    image = bytearray(INSTALLED_EXE.read_bytes())
    import pefile
    pe = pefile.PE(data=bytes(image), fast_load=True)
    for family in audit.PROVED_WRITER_FAMILIES:
        mutated = bytearray(image)
        for address, guard in family.writer_guards:
            offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
            mutated[offset:offset + len(guard)] = b"\x90" * len(guard)
        missing = audit.missing_proved_writer_families(
            INSTALLED_EXE, image_override=bytes(mutated)
        )
        require(family.name in missing, f"mutation did not fail family {family.name}")
    require(
        sum(len(family.writer_guards) for family in audit.PROVED_WRITER_FAMILIES) == 78,
        "proved affine writer instruction count changed",
    )
    for family in audit.PROVED_BULK_WRITER_FAMILIES:
        mutated = bytearray(image)
        for address, guard in family.writer_guards:
            offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
            mutated[offset:offset + len(guard)] = b"\x90" * len(guard)
        for address, guard in family.writer_guards:
            offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
            require(mutated[offset:offset + len(guard)] != guard,
                    f"bulk mutation did not fail family {family.name}")
    pe.close()

    require(
        not audit.verify_copy_helper_stock_roles(INSTALLED_EXE),
        "0x0049A7B0 saved/battle stock role audit changed",
    )
    for target, expected_callers in audit.PROVED_TRANSACTION_CALLERS.items():
        require(
            set(audit.direct_call_sites(INSTALLED_EXE, target)) == set(expected_callers),
            f"caller set changed for transaction 0x{target:08X}",
        )
    require(len(audit.AFFINE_WRITER_FAMILY_CALLERS) == 25,
            "affine writer caller-family count changed")
    for target, expected_callers in audit.AFFINE_WRITER_FAMILY_CALLERS.items():
        require(
            audit.direct_call_sites(INSTALLED_EXE, target) == expected_callers,
            f"affine caller set changed for 0x{target:08X}",
        )

    executable_image = INSTALLED_EXE.read_bytes()
    pe = pefile.PE(data=executable_image, fast_load=True)
    exact_guards = {
        # Tail calls into the generic list controller.
        0x004C7CF0: bytes.fromhex("e9 9b 60 03 00"),
        0x004C7EEE: bytes.fromhex("e9 9d 5e 03 00"),
        0x004C8590: bytes.fromhex("e9 fb 57 03 00"),
        0x004C880F: bytes.fromhex("e9 7c 55 03 00"),
        0x004C88A5: bytes.fromhex("e9 e6 54 03 00"),
        # Controller pointer registrations and battle Magic callback.
        0x004C82A8: bytes.fromhex("68 90 dd 4f 00"),
        0x004C8577: bytes.fromhex("68 90 dd 4f 00"),
        0x004C87C7: bytes.fromhex("68 90 dd 4f 00"),
        0x004C8867: bytes.fromhex("68 90 dd 4f 00"),
        0x004BC8F8: bytes.fromhex("68 20 88 4c 00"),
        0x004FE6E3: bytes.fromhex("ff 15 d0 68 d7 01"),
    }
    for address, guard in exact_guards.items():
        offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
        require(
            executable_image[offset:offset + len(guard)] == guard,
            f"generic controller/callback guard changed at 0x{address:08X}",
        )
    pe.close()


def verify_runtime_package_contract() -> None:
    module = load_module()
    require(module.build_hext(False, INSTALLED_EXE) == "", "disabled mode must emit no patch")
    report = module.inspect_runtime(INSTALLED_EXE)
    try:
        package = module.runtime_package.verify()
    except module.runtime_package.RuntimePackageError as error:
        # See the editor verifier: a non-Steam build must be refused.
        require("steam_api" in str(error), f"unexpected package refusal: {error}")
        print("SKIP: staged runtime package is refused -", error)
        return
    if INSTALLED_EXE.is_file():
        require(report["supportedExecutable"], "installed FF8_EN.exe hash changed")
        image = INSTALLED_EXE.read_bytes()
        magic_base = (
            module.SAVEMAP_CHARACTER_BASE + module.CHARACTER_MAGIC_OFFSET
        ).to_bytes(4, "little")
        character_base = module.SAVEMAP_CHARACTER_BASE.to_bytes(4, "little")
        require(image.count(magic_base) >= 100, "expected scattered direct magic-array references")
        require(image.count(character_base) >= 100, "expected scattered character-base references")

        require(report["ready"], "verified runtime package was not marked ready")
        require(module.build_hext(True, INSTALLED_EXE) == "",
                "runtime-backed enabled mode emitted Hext")
    require(package["runtimeEnabled"] is True, "packaged runtime is disabled")
    require(package["hookCount"] == 28, "packaged function-hook count changed")
    require(all(boundary["covered"] for boundary in report["boundaries"]),
            "a reviewed runtime boundary is still reported missing")

    gate_source = MODULE_PATH.read_text(encoding="utf-8")
    require("CODE_CAVE" not in gate_source, "build gate contains an unverified code cave")
    require(not re.search(r"^\s*[0-9A-Fa-f]{6,8}\s*=", gate_source, re.MULTILINE),
            "build gate contains a Hext write")
    for obsolete in (
        "intentionally not registered in FFNx yet",
        "ready\": all(boundary.covered",
        "No Hext patch was written",
        "covered: bool = False",
    ):
        require(obsolete not in gate_source, f"obsolete disabled contract survived: {obsolete}")

    # The reviewed package must reject changes to its binary, manifest, and
    # source provenance. This tests the guarantee, not one implementation line.
    package_root = module.runtime_package.PACKAGE_ROOT
    with tempfile.TemporaryDirectory(prefix="lexeditor-issue51-package-", ignore_cleanup_errors=True) as name:
        copy = Path(name) / "package"
        shutil.copytree(package_root, copy)
        driver = copy / module.runtime_package.DRIVER_NAME
        changed = bytearray(driver.read_bytes())
        changed[-1] ^= 1
        driver.write_bytes(changed)
        try:
            module.runtime_package.verify(copy)
        except module.runtime_package.RuntimePackageError:
            pass
        else:
            raise AssertionError("binary mutation survived the package lock")

        shutil.rmtree(copy)
        shutil.copytree(package_root, copy)
        manifest = copy / module.runtime_package.MANIFEST_NAME
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["hookCount"] = 27
        manifest.write_text(json.dumps(data), encoding="utf-8")
        try:
            module.runtime_package.verify(copy)
        except module.runtime_package.RuntimePackageError:
            pass
        else:
            raise AssertionError("hook-count mutation survived the package contract")

        shutil.rmtree(copy)
        shutil.copytree(package_root, copy)
        patch = copy / "ISSUE51_DERIVATIVE_SOURCE.patch"
        patch.write_text(
            patch.read_text(encoding="utf-8").replace(
                "FFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME", "REMOVED_RUNTIME_GATE", 1,
            ),
            encoding="utf-8",
        )
        try:
            module.runtime_package.verify(copy)
        except module.runtime_package.RuntimePackageError:
            pass
        else:
            raise AssertionError("source-provenance mutation survived the package contract")


def main() -> int:
    verify_cpp_contract()
    verify_executable_access_audit()
    verify_runtime_package_contract()
    print("FF8 shared magic issue #51: core, access, and runtime package contracts verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
