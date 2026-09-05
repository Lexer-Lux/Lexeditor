"""Verify Lexeditor-owned option and safe pre-launch conditional layers."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import iroj_archive, runtime_layout


def write_archive(path: Path, members: list[tuple[str, bytes]]) -> None:
    encoded = [(name.encode("utf-16-le"), data) for name, data in members]
    directory_size = 4 + sum(20 + len(name) for name, _data in encoded)
    offset = 16 + directory_size
    records = []
    payload = bytearray()
    for name, data in encoded:
        records.append(
            struct.pack("<HH", 20 + len(name), len(name)) + name
            + struct.pack("<IqI", 0, offset, len(data))
        )
        payload.extend(data)
        offset += len(data)
    path.write_bytes(
        struct.pack("<IIIIi", iroj_archive.SIGNATURE, 0x10002, 0, 16, len(records))
        + b"".join(records) + payload
    )


MOD_XML = b"""<ModInfo>
  <ID>layered</ID><Name>Layered</Name>
  <ConfigOption><Type>List</Type><Default>0</Default><Name>Colors</Name><ID>Color</ID>
    <Option Value="0" Name="Plain"/><Option Value="1" Name="Blue"/>
  </ConfigOption>
  <ConfigOption><Type>Bool</Type><Default>1</Default><Name>Details</Name><ID>Details</ID></ConfigOption>
  <ModFolder Folder="blue" ActiveWhen="Color = 1"/>
  <ModFolder Folder="detail">
    <ActiveWhen><And><Option>Details = 1</Option><Not><Option>Color = 0</Option></Not></And></ActiveWhen>
  </ModFolder>
  <ModFolder Folder="ffnx" ActiveWhen="ffnx_test_mode = 2"/>
  <Conditional Folder="clock">
    <RuntimeVar ApplyTo="direct/clock.bin" Var="CurrentHour" Values="7"/>
    <RuntimeVar ApplyTo="" Var="CurrentMonth" Values="1..12"/>
  </Conditional>
  <Conditional Folder="memory">
    <RuntimeVar ApplyTo="" Var="Byte:0x00DC08EB" Values="1"/>
  </Conditional>
  <Conditional Folder="notmemory">
    <Not ApplyTo=""><RuntimeVar Var="Byte:0x00DC08EB" Values="1"/></Not>
  </Conditional>
  <Variable Name="CurrentHour">Sys:Hour</Variable>
  <Variable Name="CurrentMonth">Sys:Month</Variable>
</ModInfo>"""


def folder_package(root: Path) -> None:
    (root / "direct").mkdir(parents=True)
    (root / "direct" / "shared.bin").write_bytes(b"base")
    (root / "direct" / "Case.BIN").write_bytes(b"case low")
    (root / "blue" / "direct").mkdir(parents=True)
    (root / "blue" / "direct" / "shared.bin").write_bytes(b"blue")
    (root / "detail" / "sfx").mkdir(parents=True)
    (root / "detail" / "sfx" / "option.ogg").write_bytes(b"option")
    (root / "ffnx" / "override").mkdir(parents=True)
    (root / "ffnx" / "override" / "setting.bin").write_bytes(b"ffnx option")
    (root / "clock" / "direct").mkdir(parents=True)
    (root / "clock" / "direct" / "clock.bin").write_bytes(b"seven")
    (root / "clock" / "direct" / "month.bin").write_bytes(b"month")
    (root / "memory" / "direct").mkdir(parents=True)
    (root / "memory" / "direct" / "unsafe.bin").write_bytes(b"must stay off")
    (root / "notmemory" / "direct").mkdir(parents=True)
    (root / "notmemory" / "direct" / "also-unsafe.bin").write_bytes(b"must stay off")
    (root / "mod.xml").write_bytes(MOD_XML)
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "layered", "name": "Layered", "enabled": True, "order": 0,
    }), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-folders-") as name:
        root = Path(name)
        project, mods, active = root / "project", root / "mods", root / "active"
        folder_package(project)
        (mods / "higher" / "direct").mkdir(parents=True)
        (mods / "higher" / "direct" / "shared.bin").write_bytes(b"global high")
        (mods / "higher" / "direct" / "case.bin").write_bytes(b"case high")
        (mods / "higher" / runtime_layout.MOD_FILE).write_text(json.dumps({
            "id": "higher", "name": "Higher", "enabled": True, "order": 1,
        }), encoding="utf-8")

        rows = runtime_layout.catalog(project, mods)
        layered = next(row for row in rows if row["id"] == "layered")
        assert [item["id"] for item in layered["folderConfig"]] == ["Color", "Details"]
        assert layered["folderOptions"] == {"Color": 0, "Details": 1}
        rows = runtime_layout.configure(
            project, mods, ["layered", "higher"],
            {"layered": True, "higher": True},
            {"layered": {"Color": 1, "Details": 1}, "higher": {}},
        )
        assert json.loads((project / runtime_layout.MOD_FILE).read_text())["folderOptions"] == {
            "Color": 1, "Details": 1,
        }
        result = runtime_layout.compose(
            project, active, rows,
            condition_state={"system": {
                "Day": 4, "Month": 9, "Year": 2026,
                "Hour": 7, "Minute": 30, "Second": 0,
            }, "ffnx": {"test_mode": 2}},
        )
        assert (active / "direct" / "shared.bin").read_bytes() == b"global high"
        assert (active / "direct" / "case.bin").read_bytes() == b"case high"
        assert (active / "direct" / "clock.bin").read_bytes() == b"seven"
        assert (active / "direct" / "month.bin").read_bytes() == b"month"
        assert (active / "sfx" / "option.ogg").read_bytes() == b"option"
        assert (active / "override" / "setting.bin").read_bytes() == b"ffnx option"
        assert not (active / "direct" / "unsafe.bin").exists()
        assert not (active / "direct" / "also-unsafe.bin").exists()
        manifest = json.loads((active / runtime_layout.COMPOSITION_FILE).read_text())
        assert next(item for item in manifest["conflicts"]
                    if item["path"] == "direct/case.bin")["winner"] == "higher"
        report = next(item for item in manifest["folderSelection"] if item["mod"] == "layered")
        assert report["options"] == {"Color": 1, "Details": 1}
        memory = next(item for item in report["layers"] if item["folder"] == "memory")
        assert memory["active"] is False and "live process state" in memory["reason"]
        not_memory = next(item for item in report["layers"] if item["folder"] == "notmemory")
        assert not_memory["active"] is False and "live process state" in not_memory["reason"]
        assert report["liveMemoryConditions"] == (
            "preserved for managed FFNx final-variant evaluation"
        )
        routes = {row["logicalPath"]: row for row in manifest["liveConditionalRoutes"]}
        assert set(routes) >= {"direct/unsafe.bin", "direct/also-unsafe.bin"}
        unsafe = routes["direct/unsafe.bin"]
        assert unsafe["status"] == "ready: final variants precomposed"
        assert unsafe["conditions"][0]["program"] == [
            {"op": "var", "spec": "Byte:0x00DC08EB", "values": "1"},
        ]
        assert unsafe["variants"][0]["passThrough"] is True
        assert (active / "direct" / unsafe["variants"][1]["asset"]).read_bytes() == b"must stay off"
        negated = routes["direct/also-unsafe.bin"]["conditions"][0]["program"]
        assert negated == [
            {"op": "var", "spec": "Byte:0x00DC08EB", "values": "1"},
            {"op": "not", "arity": 1},
        ]
        for route in routes.values():
            assert "candidates" not in route
            for variant in route["variants"]:
                if "asset" in variant:
                    asset = active / "direct" / variant["asset"]
                    assert asset.is_file() and asset.resolve().is_relative_to(active.resolve())

        config = root / "FFNx.toml"
        config.write_text('test_mode = 2\nenabled = true\nname = "ignored"\n', encoding="utf-8")
        frozen = runtime_layout.prelaunch_condition_state(config)
        assert frozen["ffnx"] == {"test_mode": 2, "enabled": 1}

        # The same metadata and stripped folder layers work inside IROJ input.
        archive_root = root / "archive-project"
        archive_root.mkdir()
        archive_path = mods / "packed.iroj"
        write_archive(archive_path, [
            ("mod.xml", MOD_XML.replace(b"layered", b"packed", 1)),
            ("direct/base.bin", b"base"),
            ("blue/direct/base.bin", b"blue archive"),
        ])
        sidecar = archive_path.with_name(archive_path.name + runtime_layout.IROJ_STATE_SUFFIX)
        sidecar.write_text(json.dumps({
            "id": "packed", "name": "Packed", "enabled": True, "order": 0,
            "folderOptions": {"Color": 1, "Details": 0},
        }), encoding="utf-8")
        (archive_root / runtime_layout.MOD_FILE).write_text(json.dumps({
            "id": "archive-project", "name": "Archive Project", "enabled": False,
        }), encoding="utf-8")
        archive_rows = runtime_layout.catalog(archive_root, mods)
        # Isolate this archive from the unrelated folder fixtures.
        for row in archive_rows:
            row["enabled"] = row["id"] == "packed"
        archive_active = root / "archive-active"
        runtime_layout.compose(
            archive_root, archive_active, archive_rows,
            condition_state={"system": {
                "Day": 4, "Month": 9, "Year": 2026,
                "Hour": 0, "Minute": 0, "Second": 0,
            }},
        )
        assert (archive_active / "direct" / "base.bin").read_bytes() == b"blue archive"

        try:
            runtime_layout.configure(
                project, mods, [row["id"] for row in runtime_layout.catalog(project, mods)],
                {row["id"]: row["enabled"] for row in runtime_layout.catalog(project, mods)},
                {"layered": {"Color": 99, "Details": 1}},
            )
        except ValueError as error:
            assert "invalid value" in str(error)
        else:
            raise AssertionError("An invalid folder option was accepted")

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    server = (ROOT / "games" / "ff8" / "server.py").read_text(encoding="utf-8")
    assert "ff8-mod-folder-options" in editor
    assert "folderOptions:Object.fromEntries" in editor
    assert 'body.get("folderOptions", {})' in server
    print("FF8 option folders and fail-closed pre-launch conditions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
