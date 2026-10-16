"""DS1 asset replacement: overrides, chunked uploads, previews, deployment.

Everything here runs against synthetic tmp_path game/project directories and
synthetic texture bytes; nothing touches an installed game.
"""
import base64
import json
from pathlib import Path
import struct
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1 import assets, deployment
from plugins.ds1.assets import AssetError
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.tae_store import CHR_DIR
from plugins.ds1 import texts

TPF = Path("chr/c0000/c0000.tpf")
SOUND = Path("sound/bank.dcx")


def make_dds(width=4, height=4, tag=b"DXT1", pixels=None):
    head = bytearray(128)
    head[0:4] = b"DDS "
    struct.pack_into("<I", head, 4, 124)
    struct.pack_into("<2I", head, 12, height, width)
    head[76:80] = struct.pack("<I", 32)
    head[84:88] = tag
    if pixels is None:
        pixels = bytes(width * height * 4)
    return bytes(head) + pixels


def make_uncompressed_dds(width=4, height=4):
    head = bytearray(128)
    head[0:4] = b"DDS "
    struct.pack_into("<I", head, 4, 124)
    struct.pack_into("<I", head, 8, 0x1 | 0x2 | 0x4 | 0x1000)
    struct.pack_into("<2I", head, 12, height, width)
    struct.pack_into("<I", head, 20, width * 4)
    struct.pack_into("<I", head, 28, 1)
    struct.pack_into("<I", head, 76, 32)
    struct.pack_into("<I", head, 80, 0x41)
    struct.pack_into("<I", head, 88, 32)
    struct.pack_into("<4I", head, 92, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    struct.pack_into("<I", head, 108, 0x1000)
    pixels = bytearray()
    for row in range(height):
        for column in range(width):
            pixels += bytes((255 if row < height // 2 else 0, 0 if row < height // 2 else 255, 128, 255))
            _ = column
    return bytes(head) + bytes(pixels)


def make_tpf(entries):
    """entries: [(name, dds bytes)]."""
    names = [name.encode("shift_jis") + b"\x00" for name, _ in entries]
    table_end = 16 + len(entries) * 20
    name_base = table_end
    blob_base = name_base + sum(map(len, names))
    head = bytearray(16)
    head[0:4] = b"TPF\x00"
    struct.pack_into("<I", head, 8, len(entries))
    out = bytes(head)
    name_off, blob_off = name_base, blob_base
    records = []
    for (_, blob), encoded in zip(entries, names):
        records.append(struct.pack("<5I", blob_off, len(blob), 0, name_off, 0))
        name_off += len(encoded)
        blob_off += len(blob)
    out += b"".join(records) + b"".join(names)
    out += b"".join(blob for _, blob in entries)
    return out


def project(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_check_relative_accepts_assets_and_rejects_the_rest():
    assert assets.check_relative("chr/c0000/c0000.tpf") == TPF
    assert assets.check_relative("sound/bank.dcx") == SOUND
    with pytest.raises(AssetError):
        assets.check_relative("/abs/chr/x.tpf")
    with pytest.raises(AssetError):
        assets.check_relative("chr/../../x.tpf")
    with pytest.raises(AssetError):
        assets.check_relative("paramdef/x.xml")
    with pytest.raises(AssetError):
        assets.check_relative(RELATIVE.as_posix())
    with pytest.raises(AssetError):
        assets.check_relative(texts.RELATIVE.as_posix())
    with pytest.raises(AssetError):
        assets.check_relative((MAP_DIR / "m10_00_00_00.msb").as_posix())
    with pytest.raises(AssetError):
        assets.check_relative((CHR_DIR / "c0000.anibnd.dcx").as_posix())
    with pytest.raises(AssetError):
        assets.check_relative("chr/.lexeditor-upload-x.part")


def test_store_remove_and_scan_roundtrip(tmp_path):
    _, mod = project(tmp_path)
    blob = make_tpf([("a.dds", make_dds())])
    assert assets.store_bytes(mod, TPF.as_posix(), blob)["size"] == len(blob)
    assert (mod / TPF).read_bytes() == blob
    found = assets.scan_project(mod)
    assert [(row["relative"], row["size"]) for row in found] == [(TPF.as_posix(), len(blob))]
    assert assets.remove_override(mod, TPF.as_posix())["relative"] == TPF.as_posix()
    assert not (mod / TPF).exists()
    assert assets.scan_project(mod) == []
    with pytest.raises(AssetError):
        assets.remove_override(mod, TPF.as_posix())


def test_scan_project_skips_owned_and_partials(tmp_path):
    _, mod = project(tmp_path)
    (mod / RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    (mod / RELATIVE).write_bytes(b"params live here")
    (mod / "chr").mkdir(exist_ok=True)
    (mod / "chr" / ".lexeditor-upload-abc.part").write_bytes(b"partial")
    assets.store_bytes(mod, TPF.as_posix(), b"pixels")
    assert [row["relative"] for row in assets.scan_project(mod)] == [TPF.as_posix()]


def test_a_tweak_mods_script_folder_is_not_an_asset(tmp_path):
    """script/ is a game folder and a tweak mod's own code folder at once."""
    import json
    _, mod = project(tmp_path)
    (mod / "script" / "__pycache__").mkdir(parents=True)
    (mod / "script" / "m10_00_00_00.luabnd.dcx").write_bytes(b"a game script override")
    # A data mod's script/ holds game files and deploys.
    assert [row["relative"] for row in assets.scan_project(mod)] == ["script/m10_00_00_00.luabnd.dcx"]
    # A tweak mod's script/ is its build script, sources and caches.
    (mod / "mod.json").write_text(json.dumps({"name": "Tweak", "script": {"version": 1}}), encoding="utf-8")
    (mod / "script" / "tweak.py").write_text("def build(values, root): return {}\n", encoding="utf-8")
    (mod / "script" / "island.S").write_text("ret\n", encoding="utf-8")
    (mod / "script" / "__pycache__" / "tweak.cpython-312.pyc").write_bytes(b"cache")
    assets.store_bytes(mod, TPF.as_posix(), b"pixels")
    assert [row["relative"] for row in assets.scan_project(mod)] == [TPF.as_posix()]


def test_scan_game_lists_assets_not_owned(tmp_path):
    game, _ = project(tmp_path)
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(b"game texture")
    (game / MAP_DIR / "m10_00_00_00.msb").parent.mkdir(parents=True, exist_ok=True)
    (game / MAP_DIR / "m10_00_00_00.msb").write_bytes(b"map")
    rows = assets.scan_game(game)
    assert TPF.as_posix() in [row["relative"] for row in rows]
    assert not [row for row in rows if row["relative"].endswith(".msb")]


def test_receive_chunk_assembles_byte_exact_and_restarts(tmp_path):
    _, mod = project(tmp_path)
    blob = bytes(range(256)) * 40
    first = assets.receive_chunk(mod, "up-1", TPF.as_posix(), len(blob), 0, blob[:5000], False)
    assert first["received"] == 5000
    assert not (mod / TPF).exists()
    done = assets.receive_chunk(mod, "up-1", TPF.as_posix(), len(blob), 5000, blob[5000:], True)
    assert done["size"] == len(blob)
    assert (mod / TPF).read_bytes() == blob
    # A first piece restarts its upload.
    assets.receive_chunk(mod, "up-1", TPF.as_posix(), 3, 0, b"abc", True)
    assert (mod / TPF).read_bytes() == b"abc"


def test_receive_chunk_rejects_bad_transfers(tmp_path):
    _, mod = project(tmp_path)
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "nope/../x", TPF.as_posix(), 10, 0, b"x" * 10, True)
    assets.receive_chunk(mod, "up-2", TPF.as_posix(), 10, 0, b"x" * 5, False)
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "up-2", TPF.as_posix(), 10, 3, b"x" * 5, False)
    assets.receive_chunk(mod, "up-3", TPF.as_posix(), 10, 0, b"x" * 5, False)
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "up-3", TPF.as_posix(), 10, 7, b"x" * 5, False)
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "up-4", TPF.as_posix(), 10, 0, b"x" * 5, True)
    assert not (mod / TPF).exists()
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "up-5", TPF.as_posix(), assets.MAX_ASSET_BYTES + 1, 0, b"x", False)
    with pytest.raises(AssetError):
        assets.receive_chunk(mod, "up-6", TPF.as_posix(), assets.MAX_ASSET_BYTES,
                             0, b"x" * (assets.MAX_UPLOAD_CHUNK + 1), False)


def test_tpf_listing_and_png_preview():
    blob = make_tpf([("a_diffuse.dds", make_uncompressed_dds(8, 4)),
                     ("b_normal.dds", make_uncompressed_dds(4, 8))])
    found = assets.list_textures(blob, "c0000.tpf")
    assert [(row["name"], row["width"], row["height"], row["format"]) for row in found] == [
        ("a_diffuse.dds", 8, 4, "uncompressed"), ("b_normal.dds", 4, 8, "uncompressed")]
    png = assets.texture_png(blob, "c0000.tpf", "", 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert assets.texture_png(make_uncompressed_dds(), "loose.dds")[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(AssetError):
        assets.list_textures(b"not a container", "c0000.tpf")
    with pytest.raises(AssetError):
        assets.texture_png(blob, "c0000.tpf", "", 9)


def test_split_archives_replace_whole_but_never_preview(tmp_path):
    _, mod = project(tmp_path)
    with pytest.raises(AssetError, match="replace as whole files"):
        assets.list_textures(b"BHF3" + bytes(200), "x.tpfbhd")
    assets.store_bytes(mod, "chr/c0000/x.tpfbhd", b"BHF3" + bytes(200))
    assert assets.scan_project(mod)[0]["relative"] == "chr/c0000/x.tpfbhd"


def test_deployment_asset_apply_disable_roundtrip(tmp_path):
    game, mod = project(tmp_path)
    vanilla = make_tpf([("a.dds", make_dds())])
    override = make_tpf([("a.dds", make_dds(tag=b"DXT5"))])
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(vanilla)
    assets.store_bytes(mod, TPF.as_posix(), override)
    assert deployment.status(game, mod)["assets"]["present"] == [TPF.as_posix()]
    assert deployment.status(game, mod)["assets"]["applied"] == []
    assert deployment.apply(game, mod)["assets"]["applied"] == [TPF.as_posix()]
    assert (game / TPF).read_bytes() == override
    assert deployment.disable(game)["assets"]["applied"] == []
    assert (game / TPF).read_bytes() == vanilla


def test_deployment_asset_override_of_a_binder_must_open(tmp_path):
    game, mod = project(tmp_path)
    (game / SOUND).parent.mkdir(parents=True)
    (game / SOUND).write_bytes(make_archive())
    assets.store_bytes(mod, SOUND.as_posix(), b"not a binder")
    with pytest.raises(ValueError, match="does not open as the binder"):
        deployment.apply(game, mod)
    assert (game / SOUND).read_bytes() == make_archive()
    assets.store_bytes(mod, SOUND.as_posix(), make_archive())
    assert deployment.apply(game, mod)["assets"]["applied"] == [SOUND.as_posix()]


def request_json(session, path, payload=None, raw=False):
    req = Request(session.url.rstrip("/") + path,
                  data=None if payload is None else json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    with urlopen(req) as reply:
        body = reply.read()
        if raw:
            return reply.headers.get_content_type(), body
        return json.loads(body)


def service_project(tmp_path):
    game, mod = project(tmp_path)
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(make_tpf([("a_diffuse.dds", make_uncompressed_dds())]))
    return game, mod


def test_service_assets_list_upload_preview_remove(tmp_path):
    game, mod = service_project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                          "LEXEDITOR_MOD_READ_ONLY": "0", "LEXEDITOR_NO_MOD": "0"})
    try:
        session.start()
        assert "asset-replacement" in request_json(session, "/api/plugin")["capabilities"]
        assert request_json(session, "/api/assets?scope=overrides")["files"] == []
        assert TPF.as_posix() in [row["relative"] for row in request_json(session, "/api/assets?scope=game")["files"]]
        blob = make_tpf([("b_diffuse.dds", make_uncompressed_dds(6, 2))])
        encoded = base64.b64encode(blob).decode("ascii")
        half = (len(encoded) // 2 // 4) * 4
        first = request_json(session, "/api/assets/upload",
                             {"id": "up-1", "relative": TPF.as_posix(), "total": len(blob),
                              "offset": 0, "data": encoded[:half], "final": False})["upload"]
        assert first["received"] < len(blob)
        done = request_json(session, "/api/assets/upload",
                            {"id": "up-1", "relative": TPF.as_posix(), "total": len(blob),
                             "offset": first["received"], "data": encoded[half:], "final": True})
        assert done["files"] == [{"relative": TPF.as_posix(), "size": len(blob), "kind": "textures",
                                    "status": "modified"}]
        detail = request_json(session, f"/api/assets?scope=textures&file={TPF.as_posix()}")
        assert detail["source"] == "mod"
        assert [(row["name"], row["width"], row["height"]) for row in detail["textures"]] == [("b_diffuse.dds", 6, 2)]
        content_type, png = request_json(
            session, f"/api/assets/preview?file={TPF.as_posix()}&index=0", raw=True)
        assert content_type == "image/png"
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        removed = request_json(session, "/api/assets/remove", {"relative": TPF.as_posix()})
        assert removed["files"] == [{"relative": TPF.as_posix(),
                                      "size": (game / TPF).stat().st_size,
                                      "kind": "textures", "status": None}]
        detail = request_json(session, f"/api/assets?scope=textures&file={TPF.as_posix()}")
        assert detail["source"] == "game"
        assert [row["name"] for row in detail["textures"]] == ["a_diffuse.dds"]
        with pytest.raises(HTTPError):
            request_json(session, "/api/assets/upload", {"id": "up-2"})
    finally:
        session.stop()


def test_service_assets_vanilla_is_read_only(tmp_path):
    game, _ = service_project(tmp_path)
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1"})
    try:
        session.start()
        overrides = request_json(session, "/api/assets?scope=overrides")
        assert overrides["files"] == [] and overrides["hasProject"] is False
        with pytest.raises(HTTPError) as error:
            request_json(session, "/api/assets/upload",
                         {"id": "up-1", "relative": TPF.as_posix(), "total": 1,
                          "offset": 0, "data": "eA==", "final": True})
        assert error.value.code == 403
        with pytest.raises(HTTPError) as error:
            request_json(session, "/api/assets/remove", {"relative": TPF.as_posix()})
        assert error.value.code == 403
    finally:
        session.stop()


def test_kind_of_sorts_assets_into_models_textures_sound_music_other():
    assert assets.kind_of("chr/c0000/c0000.chrbnd.dcx") == "models"
    assert assets.kind_of("obj/o10_00_00_00.objbnd.dcx") == "models"
    assert assets.kind_of("parts/p10_00_00_00.partsbnd.dcx") == "models"
    assert assets.kind_of("map/m10_00_00_00.m10_00_00_00.flver.dcx") == "models"
    assert assets.kind_of("map/m10_00_00_00.m10_00_00_00.hkxbdt.dcx") == "models"
    assert assets.kind_of("facegen/female.fgbnd.dcx") == "models"
    assert assets.kind_of("chr/c0000/c0000.tpf") == "textures"
    assert assets.kind_of("chr/c0000/c0000.tpf.dcx") == "textures"
    assert assets.kind_of("map/m10/m10.tpfbdt.dcx") == "textures"
    assert assets.kind_of("other/picture.PNG") == "textures"
    assert assets.kind_of("font/font16.tpf") == "textures"
    assert assets.kind_of("sound/frpg_c1000.fsb") == "sound"
    assert assets.kind_of("sound/frpg_p101000.fev") == "sound"
    assert assets.kind_of("sound/bank.dcx") == "sound"
    assert assets.kind_of("sound/frpg_m10.fsb") == "music"
    assert assets.kind_of("sound/frpg_sm12.itl") == "music"
    assert assets.kind_of("sound/frpg_mixer.fev") == "music"
    assert assets.kind_of("sound/frpg_qmain.fsb") == "music"
    assert assets.kind_of("movww/intro.wmv") == "other"
    assert assets.kind_of("movie/intro.bik") == "other"
    assert assets.kind_of("script/m10_00_00_00.luabnd.dcx") == "other"
    assert assets.kind_of("shader/abs.sdr") == "other"
    assert assets.kind_of("sfx/sfx999.ffxbnd.dcx") == "other"
    assert assets.kind_of("mtd/m10.mtdbnd.dcx") == "other"
    assert assets.kind_of("menu/menu.tpf") == "textures"
    assert assets.kind_of("menu/layout.drb") == "other"


def test_scans_label_every_entry_with_its_kind(tmp_path):
    game, mod = project(tmp_path)
    assets.store_bytes(mod, "chr/c0000/c0000.chrbnd.dcx", b"model")
    assets.store_bytes(mod, TPF.as_posix(), b"pixels")
    assets.store_bytes(mod, "sound/frpg_m10.fsb", b"music")
    assets.store_bytes(mod, "sound/frpg_c1000.fsb", b"noise")
    assets.store_bytes(mod, "movww/intro.wmv", b"movie")
    assert {row["relative"]: row["kind"] for row in assets.scan_project(mod)} == {
        "chr/c0000/c0000.chrbnd.dcx": "models", TPF.as_posix(): "textures",
        "sound/frpg_m10.fsb": "music", "sound/frpg_c1000.fsb": "sound",
        "movww/intro.wmv": "other"}
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(b"pixels")
    rows = assets.scan_game(game)
    assert [row for row in rows if row["relative"] == TPF.as_posix()][0]["kind"] == "textures"


def test_scan_project_marks_modified_and_new_against_the_game(tmp_path):
    game, mod = project(tmp_path)
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(b"game pixels")
    assets.store_bytes(mod, TPF.as_posix(), b"mod pixels")
    assets.store_bytes(mod, "chr/c9999/new.tpf", b"brand new")
    statuses = {row["relative"]: row["status"]
                for row in assets.scan_project(mod, game_root=game)}
    assert statuses == {TPF.as_posix(): "modified", "chr/c9999/new.tpf": "new"}
    assert all(row["status"] is None for row in assets.scan_project(mod))


def test_scan_game_marks_shadowed_files(tmp_path):
    game, mod = project(tmp_path)
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(b"game pixels")
    (game / "chr" / "c0001").mkdir(parents=True)
    (game / "chr" / "c0001" / "other.tpf").write_bytes(b"untouched")
    assets.store_bytes(mod, TPF.as_posix(), b"mod pixels")
    statuses = {row["relative"]: row["status"] for row in assets.scan_game(game, mod)}
    assert statuses[TPF.as_posix()] == "modified"
    assert statuses["chr/c0001/other.tpf"] is None
    assert all(row["status"] is None for row in assets.scan_game(game))


def test_scan_merged_marks_shadowed_new_and_wears_mod_sizes(tmp_path):
    game, mod = project(tmp_path)
    (game / TPF).parent.mkdir(parents=True)
    (game / TPF).write_bytes(b"game pixels")
    (game / "chr" / "c0001").mkdir(parents=True)
    (game / "chr" / "c0001" / "other.tpf").write_bytes(b"untouched")
    assets.store_bytes(mod, TPF.as_posix(), b"mod pixels!")
    assets.store_bytes(mod, "chr/c9999/new.tpf", b"brand new")
    rows = {row["relative"]: row for row in assets.scan_merged(game, mod)}
    assert set(rows) == {TPF.as_posix(), "chr/c0001/other.tpf", "chr/c9999/new.tpf"}
    assert rows[TPF.as_posix()]["status"] == "modified"
    assert rows[TPF.as_posix()]["size"] == len(b"mod pixels!")
    assert rows["chr/c0001/other.tpf"]["status"] is None
    assert rows["chr/c9999/new.tpf"]["status"] == "new"
    assert [row["relative"] for row in assets.scan_merged(game, mod)] == sorted(rows)


def test_scan_merged_without_the_game_lists_mod_files_unmarked(tmp_path):
    _game, mod = project(tmp_path)
    assets.store_bytes(mod, TPF.as_posix(), b"mod pixels")
    rows = assets.scan_merged(None, mod)
    assert [row["relative"] for row in rows] == [TPF.as_posix()]
    assert all(row["status"] is None for row in rows)
    assert assets.scan_merged(None, None) == []
