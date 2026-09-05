"""Verify issue #16 against the installed RDR2 archives without launching the game."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr2 import extractor  # noqa: E402
from games.rdr2 import server as rdr2_server  # noqa: E402
from games.rdr2.plugin import PLUGIN, Rdr2Session  # noqa: E402
from game_installation import GameInstallationManager  # noqa: E402


DEFAULT_GAME = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"
)
LOOT_FILES = (
    "loot_table_ped.meta", "loot_table_itemgroups.meta", "loot_table_reward.meta",
    "loot_table_container.meta", "loot_table_herb.meta",
)


def verify_self_contained_extractor_source() -> None:
    source = Path(extractor.__file__).read_text(encoding="utf-8")
    folded = source.casefold()
    forbidden = (
        r"c:\rdr2mod".casefold(),
        "project_root",
        "snapshot_root",
        "verified-snapshot",
    )
    found = [token for token in forbidden if token in folded]
    assert not found, (
        "RDR2 preparation still depends on a developer checkout or XML snapshot",
        found,
    )
    assert all(entry.kind != "verified-snapshot" for entry in extractor.ENTRIES)
    converted = {
        entry.output: entry.kind
        for entry in extractor.ENTRIES
        if entry.output == "catalog_sp.ymt" or entry.output.endswith(".ymt")
        and "weapon" in Path(entry.output).stem
    }
    assert converted.get("catalog_sp.ymt") not in {None, "xml", "rbf-xml", "text-json"}
    assert converted.get("weapons.ymt") == converted["catalog_sp.ymt"], converted
    weapon_kinds = {
        entry.kind for entry in extractor.ENTRIES
        if entry.output == "weapons.ymt" or entry.output.startswith("weapon_")
    }
    assert weapon_kinds == {converted["catalog_sp.ymt"]}, weapon_kinds


def verify_copied_clean_install() -> None:
    """Run preparation from an isolated minimum Lexeditor installation."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-clean-install-", ignore_cleanup_errors=True) as name:
        copied_root = Path(name) / "Lexeditor"
        copied_plugin = copied_root / "games" / "rdr2"
        copied_tools = copied_root / "tools" / "rpf-cli" / "bin"
        copied_plugin.mkdir(parents=True)
        copied_tools.mkdir(parents=True)

        for relative in ("plugin_api.py", "service_session.py", "game_installation.py"):
            shutil.copy2(ROOT / relative, copied_root / relative)
        (copied_root / "games").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "games" / "__init__.py", copied_root / "games" / "__init__.py")
        for relative in ("__init__.py", "extractor.py", "paths.py", "plugin.py"):
            shutil.copy2(ROOT / "games" / "rdr2" / relative, copied_plugin / relative)
        for name in extractor.TOOL_FILES:
            target = copied_tools / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extractor.TOOL_ROOT / name, target)

        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(copied_root / "local-data")
        environment["LEXEDITOR_RDR2_PROJECT"] = str(copied_root / "fixture-project")
        environment["LEXEDITOR_MOD_ROOT"] = str(copied_root / "fixture-project" / "mod")
        command = [
            sys.executable,
            str(ROOT / "tools" / "issue16_clean_install_probe.py"),
            str(copied_root),
        ]
        result = subprocess.run(
            command,
            cwd=copied_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "Controlled copied-install" in result.stdout, result.stdout


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=90) as response:
        return json.loads(response.read())


def _present(value) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def require_rows(endpoint: str, payload: dict, key: str,
                 required_fields: tuple[str, ...]) -> list[dict]:
    assert not payload.get("error"), (endpoint, payload)
    rows = payload.get(key)
    assert isinstance(rows, list) and rows, (endpoint, key, payload)
    representative = next((
        row for row in rows
        if isinstance(row, dict)
        and all(field in row and _present(row[field]) for field in required_fields)
    ), None)
    assert representative is not None, (endpoint, key, required_fields, rows[:3])
    return rows


def require_mapping(endpoint: str, payload: dict, key: str,
                    required_fields: tuple[str, ...]) -> dict:
    assert not payload.get("error"), (endpoint, payload)
    values = payload.get(key)
    assert isinstance(values, dict) and values, (endpoint, key, payload)
    representative = next((
        value for value in values.values()
        if isinstance(value, dict)
        and all(field in value and _present(value[field]) for field in required_fields)
    ), None)
    assert representative is not None, (endpoint, key, required_fields)
    return values


def wait_for_scan(manager: GameInstallationManager, plugin_id: str,
                  timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.snapshot(plugin_id)
        if not state["scanInProgress"]:
            return state
        time.sleep(0.01)
    raise AssertionError(("installation scan did not finish", manager.snapshot(plugin_id)))


def verify_prepare_on_scan_lifecycle(game_root: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_prepare(_game_root: Path, _data_root: Path, _progress) -> None:
        started.set()
        if not release.wait(10):
            raise AssertionError("prepare-on-scan lifecycle test timed out")

    installation = replace(
        PLUGIN.installation, prepare=blocking_prepare, prepare_on_scan=True,
    )
    plugin = replace(PLUGIN, check=lambda: [], installation=installation)
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-install-state-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        manager = GameInstallationManager(
            {plugin.plugin_id: plugin}, config_path=root / "installations.json",
            data_root=root / "data", auto_scan=False,
        )
        manager.configure_directory(plugin.plugin_id, game_root)
        assert started.wait(10), "prepare-on-scan did not start"
        preparing = manager.snapshot(plugin.plugin_id)
        assert preparing["status"] == "warning", preparing
        assert preparing["scanInProgress"] is True, preparing
        assert preparing["scanStatus"] == "preparing", preparing
        assert preparing["statusText"] != "Ready", preparing
        assert preparing["canOpen"] is False, preparing
        release.set()
        ready = wait_for_scan(manager, plugin.plugin_id)
        assert ready["status"] == "added" and ready["statusText"] == "Ready", ready
        assert ready["canOpen"] is True and not ready["problems"], ready

    failure_message = "issue #16 preparation failure sentinel"

    def failed_prepare(_game_root: Path, _data_root: Path, _progress) -> None:
        raise RuntimeError(failure_message)

    failed_installation = replace(
        PLUGIN.installation, prepare=failed_prepare, prepare_on_scan=True,
    )
    failed_plugin = replace(
        PLUGIN, check=lambda: [], installation=failed_installation,
    )
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-install-failure-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        manager = GameInstallationManager(
            {failed_plugin.plugin_id: failed_plugin},
            config_path=root / "installations.json", data_root=root / "data",
            auto_scan=False,
        )
        manager.configure_directory(failed_plugin.plugin_id, game_root)
        failed = wait_for_scan(manager, failed_plugin.plugin_id)
        assert failed["status"] == "warning", failed
        assert failed["statusText"] == "Game data preparation failed.", failed
        assert failed["canOpen"] is False, failed
        assert failed["problems"] == [failure_message], failed


def verify_content_sensitive_stamps(root: Path) -> None:
    small = root / "small-dependency.bin"
    small.write_bytes(b"AAAA")
    before_stat = small.stat()
    before = extractor._stamp(small)
    small.write_bytes(b"BBBB")
    os.utime(small, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    after = extractor._stamp(small)
    assert before["size"] == after["size"]
    assert before["mtimeNs"] == after["mtimeNs"]
    assert before.get("sha256") and before["sha256"] != after.get("sha256"), (before, after)
    assert before != after, (before, after)

    archive = root / "small-archive.rpf"
    archive.write_bytes(b"archive-one")
    before_stat = archive.stat()
    before = extractor._archive_stamp(archive)
    archive.write_bytes(b"archive-two")
    os.utime(archive, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    after = extractor._archive_stamp(archive)
    assert before["size"] == after["size"]
    assert before["mtimeNs"] == after["mtimeNs"]
    assert (before.get("sampleSha256")
            and before["sampleSha256"] != after.get("sampleSha256")), (before, after)
    assert before != after, (before, after)


def verify_strict_xml_contracts(root: Path) -> None:
    expected = {
        "common_0_data/pedperception.meta": "CPedPerceptionInfoManager",
        "update_1_common/common/data/ai/combatbehaviour.meta": "CCombatInfoMgr",
        "update_1_common/common/data/pedhealth.meta": "CEnergyConfigInfos",
        "dispatchresponses/wilderness/bountyhunters.meta": "CDispatchData",
    }
    entries = {entry.output: entry for entry in extractor.ENTRIES}
    wrong = root / "wrong-root.xml"
    wrong.write_bytes(b"<wrong/>" + b" " * 150_000)
    for output, expected_root in expected.items():
        entry = entries[output]
        assert entry.expected_root == expected_root, (output, entry.expected_root)
        assert entry.minimum_size > 1, (output, entry.minimum_size)
        assert extractor._valid_output(entry, wrong) is False, output


def main() -> int:
    verify_self_contained_extractor_source()
    verify_copied_clean_install()

    game_root = Path(os.environ.get("RDR2_GAME_ROOT", DEFAULT_GAME)).resolve()
    required = PLUGIN.installation.required_paths
    assert "update_4.rpf" in required
    assert all((game_root / relative).exists() for relative in required), game_root
    outputs = {entry.output for entry in extractor.ENTRIES}
    expected = {
        "catalog_sp.ymt", "quickselectitems.ymt", "weapons.ymt",
        "loot_items_matrix.meta", "crimeinformation.meta", "dispatch.meta",
        "goals_sp.meta", "challenges_sp.meta", *LOOT_FILES,
        "weaponcomponents.meta", "patch_weaponcomponents.meta",
        "003_weaponcomponents.meta", "004_weaponcomponents.meta",
    }
    assert expected <= outputs, sorted(expected - outputs)

    verify_prepare_on_scan_lifecycle(game_root)

    extractor.PRIVATE_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="lexeditor-rdr2-issue16-", dir=str(extractor.PRIVATE_DATA_ROOT),
    ) as name:
        cache = Path(name)
        verify_content_sensitive_stamps(cache)
        verify_strict_xml_contracts(cache)
        first = extractor.ensure_rdr2_data(game_root, cache, lambda *_: None)
        assert first == {
            "extracted": len(extractor.ENTRIES),
            "total": len(extractor.ENTRIES),
            "log": str(cache / "extraction.log"),
        }
        manifest = json.loads((cache / "extraction-manifest.json").read_text("utf-8"))
        assert manifest["version"] >= 6, manifest["version"]
        assert set(manifest["outputs"]) == outputs
        assert all("dependency" in record for record in manifest["outputs"].values())
        serialized_manifest = json.dumps(manifest).casefold()
        assert "snapshot" not in serialized_manifest, "snapshot state remained in manifest"
        assert r"c:\rdr2mod".casefold() not in serialized_manifest
        assert not list(cache.rglob("*.lexeditor-part*"))
        for entry in extractor.ENTRIES:
            assert extractor._valid_output(entry, cache / entry.output), entry.output

        second = extractor.ensure_rdr2_data(game_root, cache, lambda *_: None)
        assert second["extracted"] == 0

        # A stale stamp for one source archive must rebuild only outputs that
        # depend on that archive. The old global dependency flag rebuilt all
        # prepared data after any one archive changed.
        before_dependency_test = json.loads(
            (cache / "extraction-manifest.json").read_text("utf-8")
        )
        changed_archive = "common_0.rpf"
        affected = {
            entry.output for entry in extractor.ENTRIES
            if entry.archive == changed_archive
        }
        for output in affected:
            dependency = before_dependency_test["outputs"][output]["dependency"]["archive"]
            dependency["mtimeNs"] += 1
        (cache / "extraction-manifest.json").write_text(
            json.dumps(before_dependency_test, indent=2) + "\n", encoding="utf-8",
        )
        rebuilt = extractor.ensure_rdr2_data(game_root, cache, lambda *_: None)
        assert rebuilt["extracted"] == len(affected), (rebuilt, affected)
        after_dependency_test = json.loads(
            (cache / "extraction-manifest.json").read_text("utf-8")
        )
        for output in outputs - affected:
            assert (after_dependency_test["outputs"][output]
                    == before_dependency_test["outputs"][output]), output
        assert extractor.ensure_rdr2_data(
            game_root, cache, lambda *_: None,
        )["extracted"] == 0

        weapon = next(entry for entry in extractor.ENTRIES if entry.output == "weapons.ymt")
        rejected = cache / "failed-conversion.lexeditor-part"
        original_run = extractor._run

        def failed_conversion(command: list[str], log_file: Path, label: str) -> None:
            if label == weapon.output:
                raise RuntimeError(f"controlled converter failure: {label}")
            original_run(command, log_file, label)

        extractor._run = failed_conversion
        try:
            extractor._prepare_entry(
                weapon, game_root / weapon.archive, rejected,
                cache / "fail-closed.log",
            )
        except RuntimeError as error:
            assert str(error) == "controlled converter failure: weapons.ymt", error
        else:
            raise AssertionError("A PSIN converter failure was accepted")
        finally:
            extractor._run = original_run
        assert not rejected.exists()

        with Rdr2Session({"LEXEDITOR_RDR2_EXTRACT_ROOT": str(cache)}) as session:
            config = read_json(session.url + "api/config")["datasets"]["vanilla"]
            assert Path(config["dir"]).resolve() == cache
            assert all(config[key] for key in (
                "catalog", "quickSelect", "matrix", "crime", "dispatch", "challenges",
            ))
            assert config["lootFiles"] == list(LOOT_FILES)
            catalog_endpoint = "api/catalog?ds=vanilla"
            catalog = read_json(session.url + catalog_endpoint)
            require_rows(
                catalog_endpoint, catalog, "items", ("key", "category", "group", "tags"),
            )
            require_rows(
                catalog_endpoint, catalog, "effects",
                ("key", "id", "value", "percent", "time"),
            )

            quick_endpoint = "api/quick-select?ds=vanilla"
            quick = read_json(session.url + quick_endpoint)
            assert quick.get("available") is True, (quick_endpoint, quick)
            require_mapping(quick_endpoint, quick, "items", ("group", "slots"))
            assert isinstance(quick.get("slotsByGroup"), dict) and quick["slotsByGroup"], (
                quick_endpoint, quick,
            )

            for item in LOOT_FILES:
                endpoint = f"api/loot/{item}?ds=vanilla"
                require_rows(
                    endpoint, read_json(session.url + endpoint), "tables", ("key", "entries"),
                )
            matrix_endpoint = "api/matrix?ds=vanilla"
            require_rows(
                matrix_endpoint, read_json(session.url + matrix_endpoint),
                "animals", ("key", "rows"),
            )

            challenge_endpoint = "api/challenges?ds=vanilla"
            challenges = read_json(session.url + challenge_endpoint)
            require_rows(
                challenge_endpoint, challenges, "goals", ("name", "requirements"),
            )
            require_rows(
                challenge_endpoint, challenges, "strands", ("key", "ranks"),
            )

            crime_endpoint = "api/crime?ds=vanilla"
            require_rows(
                crime_endpoint, read_json(session.url + crime_endpoint),
                "crimes", ("key", "severity"),
            )
            dispatch_endpoint = "api/dispatch?ds=vanilla"
            require_rows(
                dispatch_endpoint, read_json(session.url + dispatch_endpoint),
                "rows", ("group", "field", "value"),
            )

            bounty_endpoint = "api/bounty-hunters?ds=vanilla"
            bounty = read_json(session.url + bounty_endpoint)
            assert bounty.get("available") is True, (bounty_endpoint, bounty)
            require_rows(bounty_endpoint, bounty, "settings", ("id", "field", "value"))
            require_rows(
                bounty_endpoint, bounty, "cooldowns", ("ids", "min", "max"),
            )
            require_rows(
                bounty_endpoint, bounty, "phases", ("name", "groups", "multiplier"),
            )
            require_rows(
                bounty_endpoint, bounty, "presets",
                ("preset", "loadouts", "chaseProfile"),
            )

            weapon_endpoint = "api/weapons?ds=vanilla"
            weapons = read_json(session.url + weapon_endpoint)
            expected_weapon_layers = [
                relative for _, relative in rdr2_server.WEAPON_STACK
                if relative.endswith(".ymt")
            ]
            assert len(expected_weapon_layers) == 7, expected_weapon_layers
            assert weapons.get("available") is True, (weapon_endpoint, weapons)
            assert weapons.get("files") == expected_weapon_layers, weapons.get("files")
            require_rows(
                weapon_endpoint, weapons, "weapons", ("name", "fields", "sourceFile"),
            )
            require_rows(
                weapon_endpoint, weapons, "ammo", ("name", "fields", "sourceFile"),
            )

            perception_endpoint = "api/ai/ai/pedperception.meta?ds=vanilla"
            perception = read_json(session.url + perception_endpoint)
            assert perception.get("available") is True, (perception_endpoint, perception)
            require_rows(
                perception_endpoint, perception, "fields", ("path", "field", "value"),
            )

            mobs_endpoint = "api/mobs?ds=vanilla"
            mobs = read_json(session.url + mobs_endpoint)
            assert not mobs.get("error"), (mobs_endpoint, mobs)
            for key in ("combat", "health"):
                section = mobs.get(key, {})
                assert section.get("available") is True, (mobs_endpoint, key, section)
                require_rows(
                    f"{mobs_endpoint}:{key}", section, "records", ("name", "fields"),
                )

    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-outside-", ignore_cleanup_errors=True) as outside_name:
        outside = Path(outside_name)
        try:
            extractor.ensure_rdr2_data(game_root, outside, lambda *_: None)
        except RuntimeError as error:
            assert "private cache" in str(error), error
        else:
            raise AssertionError("RDR2 preparation accepted a cache outside PRIVATE_DATA_ROOT")

    print("Issue #16 first-start preparation verified against the installed archives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
