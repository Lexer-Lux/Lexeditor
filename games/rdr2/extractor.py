"""Prepare every RDR2 vanilla reference used by the active editor pages."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import PRIVATE_DATA_ROOT


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
TOOL_ROOT = LEXEDITOR_ROOT / "tools" / "rpf-cli" / "bin"
TOOL = TOOL_ROOT / "RpfCli.exe"
TOOL_FILES = (
    "RpfCli.exe",
    "RpfCli.dll",
    "RpfCli.deps.json",
    "RpfCli.runtimeconfig.json",
    "names.txt",
    "oo2core_5_win64.dll",
    "pso-names/FileNames.txt",
    "pso-names/PsoCollisions.txt",
    "pso-names/PsoCommon.txt",
    "pso-names/PsoEnumValues.txt",
    "pso-names/PsoFieldNames.txt",
    "pso-names/PsoTypeNames.txt",
)


@dataclass(frozen=True)
class ExtractEntry:
    archive: str
    entry: str
    output: str
    kind: str = "xml"
    chain: tuple[str, ...] = ()
    expected_root: str = ""
    minimum_size: int = 1
    source_sha256: str = ""


def _xml(archive: str, entry: str, output: str, root: str, minimum: int) -> ExtractEntry:
    return ExtractEntry(archive, entry, output, expected_root=root, minimum_size=minimum)


def _pso(
    entry: str,
    output: str,
    source_sha256: str,
    *,
    root: str = "CWeaponInfoBlob",
    minimum: int = 30_000,
    chain: tuple[str, ...] = (),
) -> ExtractEntry:
    return ExtractEntry(
        "update_4.rpf", entry, output, kind="pso-xml", chain=chain,
        expected_root=root, minimum_size=minimum, source_sha256=source_sha256,
    )


ENTRIES = (
    _xml("common_0.rpf", "data/pedperception.meta",
         "common_0_data/pedperception.meta", "CPedPerceptionInfoManager", 25_000),
    _xml("update_1.rpf", "common/data/ai/combatbehaviour.meta",
         "update_1_common/common/data/ai/combatbehaviour.meta", "CCombatInfoMgr", 100_000),
    _xml("update_1.rpf", "common/data/pedhealth.meta",
         "update_1_common/common/data/pedhealth.meta", "CEnergyConfigInfos", 60_000),
    _xml(
        "update_1.rpf", "common/data/dispatchresponses/wilderness/bountyhunters.meta",
        "dispatchresponses/wilderness/bountyhunters.meta", "CDispatchData", 8_000,
    ),
    ExtractEntry(
        "update_3.rpf", "x64/data/lang/american_rel.rpf",
        "localization/american_global.json", kind="text-json",
        chain=("global.yldb",), minimum_size=100_000,
    ),
    _xml("common_0.rpf", "data/loot_tables/loot_table_ped.meta",
         "loot_table_ped.meta", "CLootTableCollection", 70_000),
    _xml("common_0.rpf", "data/loot_tables/loot_table_itemgroups.meta",
         "loot_table_itemgroups.meta", "CLootTableCollection", 60_000),
    _xml("common_0.rpf", "data/loot_tables/loot_table_reward.meta",
         "loot_table_reward.meta", "CLootTableCollection", 25_000),
    _xml("common_0.rpf", "data/loot_tables/loot_table_container.meta",
         "loot_table_container.meta", "CLootTableCollection", 34_000),
    _xml("common_0.rpf", "data/loot_tables/loot_table_herb.meta",
         "loot_table_herb.meta", "CLootTableCollection", 15_000),
    _xml("update_1.rpf", "common/data/loot_tables/loot_items_matrix.meta",
         "loot_items_matrix.meta", "CLootMatrixDefMap", 1_000_000),
    _xml("update_1.rpf", "common/data/ai/crimeinformation.meta",
         "crimeinformation.meta", "CCrimeInformations", 280_000),
    _xml("update_1.rpf", "common/data/dispatch.meta",
         "dispatch.meta", "CDispatchData", 80_000),
    _xml("update_1.rpf", "common/data/stats_and_challenges/goals_sp.meta",
         "goals_sp.meta", "Goals", 250_000),
    _xml("update_1.rpf", "common/data/stats_and_challenges/challenges_sp.meta",
         "challenges_sp.meta", "Challenges", 120_000),
    ExtractEntry(
        "update_4.rpf", "x64/packs/base/data/ai/quickselectitems.ymt",
        "quickselectitems.ymt", kind="rbf-xml",
        expected_root="uiQuickSelectEntryInfoCollection", minimum_size=400_000,
    ),
    _pso(
        "x64/data/itemdatabase/catalog_sp.rpf", "catalog_sp.ymt",
        "F386CA2F6C35A99BD4F736AA2CC1151D81B181ADE8BDFD07749A5A3A1B6C1FB5",
        root="ItemDatabaseParser", minimum=16_000_000, chain=("catalog_sp.ymt",),
    ),
    _pso(
        "x64/packs/base/data/ai/weapons.ymt", "weapons.ymt",
        "29A0E681A8802FBBD8C8798DE2322AEC0929E0CC852D3A09552FD1E4916F1415",
        minimum=4_200_000,
    ),
    _pso(
        "x64/pack_patch/dlc_content_extra/data/ai/weapon_pistol_m1899.ymt",
        "weapon_pistol_m1899.ymt",
        "56AAA733F2B5EB0E392691981086B7E4D965E5C0E9EAAEBFD6E274A7D4C43F61",
    ),
    _pso(
        "x64/pack_patch/dlc_content_extra/data/ai/weapon_repeater_evans.ymt",
        "weapon_repeater_evans.ymt",
        "22F9C339C913A2545E34E60F3AC5D64D67B2BAA444CB745CACC550143C38685A",
    ),
    _pso(
        "x64/pack_patch/dlc_content_extra/data/ai/weapon_revolver_doubleaction_gambler.ymt",
        "weapon_revolver_doubleaction_gambler.ymt",
        "8742BD47E7CBC18FFDDEB70DE161A17B9DFEB6B4BEE2581B1A389D6F85CB6CDB",
    ),
    _pso(
        "x64/pack_patch/dlc_content_extra/data/ai/weapon_revolver_lemat.ymt",
        "weapon_revolver_lemat.ymt",
        "766EF4D19930B4C1B966E89C0D25AABA5ABA4FBFA35DDD7A20E1795DDDB5A850",
    ),
    _pso(
        "x64/pack_patch/mp006/data/ai/weapon_revolver_navy.ymt",
        "weapon_revolver_navy.ymt",
        "7D513CCA4D50E1D3EE923773B464BBE518B9A6C25723B76074AEBA50D4849C0B",
    ),
    _pso(
        "x64/pack_patch/mp007/data/ai/weapon_rifle_elephant.ymt",
        "weapon_rifle_elephant.ymt",
        "8F0C6800CC3A3A5D54FBFE0F656FAE041ABF0A59300159100EF6B581EC32B077",
    ),
    _xml("update_1.rpf", "common/packs/base/data/ai/weaponcomponents.meta",
         "weaponcomponents.meta", "CWeaponComponentInfoBlob", 300_000),
    _xml(
        "update_1.rpf",
        "pack_patch/dlc_content_extra/common/data/ai/weaponcomponents.meta",
        "patch_weaponcomponents.meta", "CWeaponComponentInfoBlob", 10_000,
    ),
    _xml(
        "update_1.rpf",
        "pack_patch/dlc_content_extra/common/data/ai/003_weaponcomponents.meta",
        "003_weaponcomponents.meta", "CWeaponComponentInfoBlob", 12_000,
    ),
    _xml(
        "update_1.rpf",
        "pack_patch/dlc_content_extra/common/data/ai/004_weaponcomponents.meta",
        "004_weaponcomponents.meta", "CWeaponComponentInfoBlob", 12_000,
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _stamp(path: Path) -> dict[str, int | str]:
    stat = path.stat()
    return {
        "size": stat.st_size,
        "mtimeNs": stat.st_mtime_ns,
        "sha256": _sha256(path),
    }


def _sample_sha256(path: Path, *, sample_size: int = 64 * 1024,
                   sample_count: int = 16) -> str:
    """Fingerprint a large archive without hashing several gigabytes at startup."""
    size = path.stat().st_size
    digest = hashlib.sha256()
    digest.update(size.to_bytes(8, "big"))
    if size <= sample_size * sample_count:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest().upper()
    maximum = size - sample_size
    offsets = {
        (maximum * index) // (sample_count - 1)
        for index in range(sample_count)
    }
    with path.open("rb") as handle:
        for offset in sorted(offsets):
            handle.seek(offset)
            digest.update(offset.to_bytes(8, "big"))
            digest.update(handle.read(sample_size))
    return digest.hexdigest().upper()


def _archive_stamp(path: Path) -> dict[str, int | str]:
    """Identify one installed archive without reading its multi-gigabyte body."""
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtimeNs": stat.st_mtime_ns,
        "sampleSha256": _sample_sha256(path),
    }


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _valid_xml(entry: ExtractEntry, path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < entry.minimum_size:
        return False
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return False
    return not entry.expected_root or root.tag == entry.expected_root


def _valid_text_json(path: Path) -> bool:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (
        isinstance(values, dict) and len(values) > 10_000
        and values.get("0x5DE85D64") == "Irish Whiskey Bottle"
        and all(isinstance(key, str) and isinstance(value, str)
                for key, value in values.items())
    )


def _valid_output(entry: ExtractEntry, path: Path) -> bool:
    return _valid_text_json(path) if entry.kind == "text-json" else _valid_xml(entry, path)


def _read_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _write_manifest(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message.rstrip()}\n")


def _run(command: list[str], log_file: Path, label: str) -> None:
    try:
        result = subprocess.run(
            command, cwd=TOOL_ROOT, capture_output=True, text=True, timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as error:
        _log(log_file, f"FAILED {label}: {error}")
        raise RuntimeError(f"RDR2 preparation failed for {label}. See {log_file}") from error
    if result.stdout:
        _log(log_file, result.stdout)
    if result.stderr:
        _log(log_file, "stderr: " + result.stderr)
    if result.returncode != 0:
        _log(log_file, f"FAILED {label}: exit={result.returncode}")
        raise RuntimeError(f"RDR2 preparation failed for {label}. See {log_file}")


def _extract_command(entry: ExtractEntry, archive: Path, output: Path) -> list[str]:
    if entry.kind == "text-json":
        return [str(TOOL), str(archive), "--extract-chain-text-json",
                entry.entry, *entry.chain, str(output)]
    if entry.kind == "rbf-xml":
        return [str(TOOL), str(archive), "--extract-chain-xml",
                entry.entry, *entry.chain, str(output)]
    if entry.chain:
        return [str(TOOL), str(archive), "--extract-chain",
                entry.entry, *entry.chain, str(output)]
    return [str(TOOL), str(archive), entry.entry, str(output)]


def _prepare_entry(entry: ExtractEntry, archive: Path, temporary: Path,
                   log_file: Path) -> None:
    if entry.kind != "pso-xml":
        _run(_extract_command(entry, archive, temporary), log_file, entry.output)
        return
    raw = temporary.with_suffix(temporary.suffix + ".raw")
    try:
        _run(_extract_command(entry, archive, raw), log_file, entry.output + " source")
        actual_source = _sha256(raw)
        if actual_source != entry.source_sha256:
            raise RuntimeError(
                f"RDR2 {entry.output} is from an unsupported game build "
                f"({actual_source}). Lexeditor did not guess a conversion."
            )
        _run(
            [str(TOOL), "--pso-to-xml", str(raw), str(temporary)],
            log_file, entry.output,
        )
    finally:
        raw.unlink(missing_ok=True)


def ensure_rdr2_data(game_root: Path, data_root: Path, progress) -> dict:
    """Prepare every missing or stale editor dependency from read-only RPFs."""
    missing_tool = [name for name in TOOL_FILES if not (TOOL_ROOT / name).is_file()]
    if missing_tool:
        raise RuntimeError(
            "The bundled RDR2 extractor is incomplete: " + ", ".join(missing_tool)
        )
    game_root = Path(game_root).resolve()
    data_root = Path(data_root).resolve()
    private_root = PRIVATE_DATA_ROOT.resolve()
    if not _inside(data_root, private_root):
        raise RuntimeError(
            f"RDR2 prepared data must stay inside Lexeditor's private cache: {private_root}"
        )
    data_root.mkdir(parents=True, exist_ok=True)
    log_file = data_root / "extraction.log"
    manifest_file = data_root / "extraction-manifest.json"
    archives = {entry.archive: game_root / entry.archive for entry in ENTRIES}
    missing_archives = [name for name, path in archives.items() if not path.is_file()]
    if missing_archives:
        raise RuntimeError("Missing required RDR2 archive(s): " + ", ".join(missing_archives))

    archive_stamps = {name: _archive_stamp(path) for name, path in archives.items()}
    tool_stamps = {name: _stamp(TOOL_ROOT / name) for name in TOOL_FILES}
    previous = _read_manifest(manifest_file)
    previous_outputs = previous.get("outputs", {})
    needed = []
    for entry in ENTRIES:
        output = data_root / entry.output
        previous_output = previous_outputs.get(entry.output, {})
        expected_hash = previous_output.get("sha256")
        dependency = {
            "archive": archive_stamps[entry.archive],
            "tools": tool_stamps,
        }
        if (previous.get("version") != 6
                or previous_output.get("dependency") != dependency
                or not _valid_output(entry, output)
                or not expected_hash or _sha256(output) != expected_hash):
            needed.append(entry)
    if not needed:
        progress(len(ENTRIES), len(ENTRIES), "RDR2 game data is ready")
        return {"extracted": 0, "total": len(ENTRIES), "log": str(log_file)}

    _log(log_file, f"Preparing {len(needed)} of {len(ENTRIES)} required files from {game_root}")
    for index, entry in enumerate(needed, 1):
        progress(index - 1, len(needed), f"Preparing {Path(entry.output).name}…")
        output = data_root / entry.output
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".lexeditor-part")
        temporary.unlink(missing_ok=True)
        try:
            _prepare_entry(entry, archives[entry.archive], temporary, log_file)
            if not _valid_output(entry, temporary):
                raise RuntimeError(f"RDR2 {entry.output} did not pass its validation.")
            temporary.replace(output)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            _log(log_file, f"FAILED {entry.entry}: {error}")
            if isinstance(error, RuntimeError):
                raise
            raise RuntimeError(
                f"RDR2 preparation failed for {entry.output}. See {log_file}"
            ) from error
        progress(index, len(needed), f"Prepared {Path(entry.output).name}")

    outputs = {
        entry.output: {
            "sha256": _sha256(data_root / entry.output), "archive": entry.archive,
            "entry": entry.entry, "chain": list(entry.chain), "method": entry.kind,
            "sourceSha256": entry.source_sha256 or None,
            "dependency": {
                "archive": archive_stamps[entry.archive],
                "tools": tool_stamps,
            },
        }
        for entry in ENTRIES
    }
    _write_manifest(manifest_file, {
        "version": 6, "gameRoot": str(game_root), "archives": archive_stamps,
        "tools": tool_stamps, "outputs": outputs,
    })
    _log(log_file, f"READY {len(ENTRIES)} required files")
    progress(len(needed), len(needed), "RDR2 game data is ready")
    return {"extracted": len(needed), "total": len(ENTRIES), "log": str(log_file)}
