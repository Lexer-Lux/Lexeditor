"""Verify safe IROJ input and Lexeditor-owned ordered composition."""

from __future__ import annotations

import json
import lzma
from pathlib import Path
import struct
import sys
import tempfile
import threading
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import iroj_archive, paths, runtime_layout, server
def _archive(path: Path, members: list[tuple[str, bytes, int]]) -> None:
    encoded = []
    for name, plain, compression in members:
        if compression == iroj_archive.FLAG_LZS:
            # A literal-only stream is valid for this eight-token LZS format.
            chunks = []
            for start in range(0, len(plain), 8):
                block = plain[start:start + 8]
                chunks.append(bytes([(1 << len(block)) - 1]) + block)
            stored = b"".join(chunks)
        elif compression == iroj_archive.FLAG_LZMA:
            lc, lp, pb, dictionary = 3, 0, 2, 1 << 20
            props = bytes([(pb * 5 + lp) * 9 + lc]) + struct.pack("<I", dictionary)
            compressed = lzma.compress(
                plain, format=lzma.FORMAT_RAW,
                filters=[{"id": lzma.FILTER_LZMA1, "dict_size": dictionary,
                          "lc": lc, "lp": lp, "pb": pb}],
            )
            stored = struct.pack("<II", len(plain), len(props)) + props + compressed
        else:
            stored = plain
        encoded_name = name.encode("utf-16-le")
        encoded.append((name, encoded_name, plain, compression, stored))
    directory_size = 4 + sum(20 + len(row[1]) for row in encoded)
    offset = 16 + directory_size
    records = []
    payload = bytearray()
    for _name, encoded_name, _plain, compression, stored in encoded:
        record_size = 20 + len(encoded_name)
        records.append(
            struct.pack("<HH", record_size, len(encoded_name)) + encoded_name
            + struct.pack("<IqI", compression, offset, len(stored))
        )
        payload.extend(stored)
        offset += len(stored)
    path.write_bytes(
        struct.pack("<IIIIi", iroj_archive.SIGNATURE, 0x10002, 0, 16, len(records))
        + b"".join(records) + payload
    )


def _folder_mod(root: Path) -> None:
    (root / "direct").mkdir(parents=True)
    (root / "direct" / "shared.bin").write_bytes(b"folder winner")
    hext = root / "hext" / "ff8" / "en_nv"
    hext.mkdir(parents=True)
    (hext / "aaa.txt").write_bytes(b"higher patch with earlier source name")
    (hext / "packed.txt").write_bytes(b"higher same-name patch")
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "folder", "name": "Folder", "order": 20, "enabled": True,
    }), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-iroj-") as name:
        root = Path(name)
        project, mods, active = root / "project", root / "mods", root / "active"
        _folder_mod(project)
        mods.mkdir()
        archive_path = mods / "packed.iroj"
        metadata = b"<ModInfo><ID>packed</ID><Name>Packed Mod</Name></ModInfo>"
        _archive(archive_path, [
            ("mod.xml", metadata, 0),
            ("direct\\shared.bin", b"archive loses", iroj_archive.FLAG_LZS),
            ("hext\\ff8\\en_nv\\packed.txt", b"patch", iroj_archive.FLAG_LZMA),
            ("sfx\\123.ogg", b"sound", 0),
            ("textures\\battle\\spell.png", b"texture", 0),
        ])

        archive = iroj_archive.Archive(archive_path)
        assert archive.names() == (
            "mod.xml", "direct/shared.bin", "hext/ff8/en_nv/packed.txt",
            "sfx/123.ogg", "textures/battle/spell.png")
        assert archive.read("DIRECT/shared.bin") == b"archive loses"
        assert archive.read("hext/ff8/en_nv/packed.txt") == b"patch"

        rows = runtime_layout.catalog(project, mods)
        packed = next(row for row in rows if row["id"] == "packed")
        assert packed["name"] == "Packed Mod" and packed["container"] == "iroj"
        materialized = runtime_layout.root_for_mod(project, mods, "packed")
        assert materialized != archive_path
        assert (materialized / "direct" / "shared.bin").read_bytes() == b"archive loses"
        assert (materialized / "hext" / "ff8" / "en_nv" / "packed.txt").read_bytes() == b"patch"
        assert (materialized / "sfx" / "123.ogg").read_bytes() == b"sound"
        assert (materialized / "textures" / "battle" / "spell.png").read_bytes() == b"texture"
        assert (materialized / ".complete").read_text(encoding="ascii") == runtime_layout._sha256(archive_path)
        rows = runtime_layout.configure(
            project, mods, ["packed", "folder"], {"packed": True, "folder": True})
        sidecar = archive_path.with_name(archive_path.name + runtime_layout.IROJ_STATE_SUFFIX)
        assert json.loads(sidecar.read_text(encoding="utf-8"))["order"] == 0

        result = runtime_layout.compose(project, active, rows)
        assert (active / "direct" / "shared.bin").read_bytes() == b"folder winner"
        hext_files = sorted((active / "hext" / "ff8" / "en_nv").iterdir())
        assert [path.name for path in hext_files] == [
            "000000__packed__packed.txt",
            "000001__folder__aaa.txt",
            "000001__folder__packed.txt",
        ]
        assert [path.read_bytes() for path in hext_files] == [
            b"patch", b"higher patch with earlier source name", b"higher same-name patch"]
        assert (active / "sfx" / "123.ogg").read_bytes() == b"sound"
        assert (active / "textures" / "battle" / "spell.png").read_bytes() == b"texture"
        assert next(row for row in result["conflicts"]
                    if row["path"] == "direct/shared.bin")["winner"] == "folder"
        hext_conflict = next(row for row in result["conflicts"]
                             if row["path"] == "hext/ff8/en_nv/packed.txt")
        assert hext_conflict["winner"] == "ordered runtime patches"
        assert hext_conflict["mode"] == "low-to-high patch stream"
        hext_manifest = [row for row in json.loads(
            Path(result["manifest"]).read_text(encoding="utf-8"))["files"]
                         if row.get("sourcePath", "").startswith("hext/")]
        assert [row["loadOrder"] for row in hext_manifest] == [0, 1, 1]

        unsafe = mods / "unsafe.iroj"
        _archive(unsafe, [("../escape.bin", b"no", 0)])
        try:
            iroj_archive.Archive(unsafe)
        except iroj_archive.IrojError as error:
            assert "Unsafe" in str(error)
        else:
            raise AssertionError("IROJ traversal member was accepted")
        assert not (root / "escape.bin").exists()
        broken = next(row for row in runtime_layout.catalog(project, mods)
                      if row["id"] == "unsafe")
        assert broken["enabled"] is False and "Unsafe" in broken["error"]

        import_source = root / "new-mod.iroj"
        _archive(import_source, [
            ("mod.xml", b"<ModInfo><ID>new-mod</ID><Name>New Mod</Name></ModInfo>", 0),
            ("direct/new.bin", b"new", 0),
        ])
        installed = runtime_layout.install_iroj(import_source, project, mods)
        assert installed["id"] == "new-mod" and installed["enabled"] is False
        assert Path(installed["path"]).parent == mods.resolve()
        assert Path(installed["path"]).read_bytes() == import_source.read_bytes()
        try:
            runtime_layout.install_iroj(import_source, project, mods)
        except ValueError as error:
            assert "already uses id" in str(error)
        else:
            raise AssertionError("duplicate IROJ id was installed")

        unnamed_source = root / "private-upload-name.iroj"
        _archive(unnamed_source, [("direct/unnamed.bin", b"unnamed", 0)])
        unnamed = runtime_layout.install_iroj(
            unnamed_source, project, mods, "Original Friendly Name.iroj")
        assert unnamed["id"] == "Original Friendly Name"
        assert unnamed["name"] == "Original Friendly Name"

        api_source = root / "api-mod.iroj"
        _archive(api_source, [
            ("mod.xml", b"<ModInfo><ID>api-mod</ID><Name>API Mod</Name></ModInfo>", 0),
            ("hext/ff8/en_nv/api.txt", b"api", 0),
        ])
        paths.PROJECT_ROOT, paths.MODS_ROOT, paths.RUNTIME_ROOT = project, mods, active
        service = server.create_server(0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{service.server_address[1]}/api/mods/import?filename=Browser%20Name.iroj",
                data=api_source.read_bytes(), method="POST",
                headers={"Content-Type": "application/octet-stream"},
            )
            with urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["imported"]["id"] == "api-mod"
            assert any(row["id"] == "api-mod" for row in payload["rows"])
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=5)

    print("FF8 IROJ validation, decompression, metadata, order, and composition passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
