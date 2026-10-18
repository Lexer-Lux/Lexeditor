"""Render the file tabs: browse, preview, add and remove, never game files."""
import io
import os
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from bhf_fixture import make_bhf
from drb_fixture import make_dcx
from ds1_fixture import make_archive, make_text_archive
from flver_fixture import build_flver, make_chrbnd
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

TPF = "chr/c0000/c0000.tpf"
PNG = "other/picture.png"
BHD = "map/m10/m10.tpfbhd"
BDT = "map/m10/m10.tpfbdt"
MODEL_CHR = "chr/c0000/c0000.chrbnd.dcx"
MODEL_OBJ = "obj/o1000.objbnd.dcx"
MODEL_PIECE = "map/m10_00_00_00/m10piece.flver.dcx"
MODEL_HKX = "map/m10_00_00_00/m10_00_00_00.hkx.dcx"
MOVIE = "movww/intro.wmv"
MUSIC = "sound/frpg_m10.fsb"
SFX = "sound/frpg_c1000.fsb"


def make_dds(width=16, height=16):
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
            pixels += bytes((255 if (row + column) % 2 else 0, 0 if (row + column) % 2 else 255, 128, 255))
    return bytes(head) + bytes(pixels)


def make_tpf(name, width=16, height=16):
    blob = make_dds(width, height)
    encoded = name.encode("shift_jis") + b"\x00"
    head = bytearray(16)
    head[0:4] = b"TPF\x00"
    struct.pack_into("<I", head, 8, 1)
    return bytes(head) + struct.pack("<5I", 16 + 20 + len(encoded), len(blob), 0, 16 + 20, 0) + encoded + blob


def make_png():
    out = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 30, 30)).save(out, format="PNG")
    return out.getvalue()


def section_titles(page):
    return page.locator("#main .lex-detail-section-title").all_text_contents()


def geometry_text(page):
    return page.locator(".lex-detail-section", has_text="GEOMETRY").first.inner_text()


def painted(page, locator):
    shot = page.locator(locator).screenshot()
    colors = Image.open(io.BytesIO(shot)).convert("RGB").getcolors(maxcolors=1 << 20)
    count = "many" if colors is None else len(colors)
    assert colors is None or len(colors) > 8, f"preview canvas blank ({count} colors)"


def loaded_images(page, selector):
    shots = page.locator(selector)
    assert shots.count() > 0, selector
    sizes = page.evaluate(
        """(query) => [...document.querySelectorAll(query)].map(
            image => [image.naturalWidth, image.naturalHeight])""",
        selector)
    assert sizes and all(width > 0 and height > 0 for width, height in sizes), sizes


def open_drawer(page):
    page.locator(".lex-detail-panel-heading .lex-model-preview-trigger").click()
    page.wait_for_selector(".lex-model-stage[data-ready='true']", timeout=30000)
    assert page.locator("canvas[data-preview]").count() == 1
    assert page.evaluate("!!window.__lexPreview"), "preview hook missing"


def close_drawer(page):
    page.locator(".lex-detail-panel-heading .lex-model-preview-trigger").click()
    page.wait_for_function("window.__lexPreview === undefined")


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    game_tpf = make_tpf("c0000_diffuse.dds")
    mod_tpf = make_tpf("c0000_custom.dds", 24, 8)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-assets-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / TPF).parent.mkdir(parents=True)
        (game / TPF).write_bytes(game_tpf)
        (game / PNG).parent.mkdir(parents=True, exist_ok=True)
        (game / PNG).write_bytes(make_png())
        (game / "map" / "m10").mkdir(parents=True, exist_ok=True)
        (game / "map" / "m10" / "m10.tpfbhd").write_bytes(make_bhf([("/tex0", 0, 8)]))
        (game / "map" / "m10" / "m10.tpfbdt").write_bytes(b"12345678")
        (game / MODEL_CHR).parent.mkdir(parents=True, exist_ok=True)
        (game / MODEL_CHR).write_bytes(make_chrbnd(
            build_flver(), stem="c0000",
            extra=[("c0000.tpf", make_tpf("c0000_diffuse.dds", 200, 200)),
                   ("c0000_1.tpf", make_tpf("c0000_snormal.dds", 200, 200))]))
        (game / MODEL_OBJ).parent.mkdir(parents=True, exist_ok=True)
        (game / MODEL_OBJ).write_bytes(make_chrbnd(
            build_flver(), stem="o1000",
            extra=[("o1001.flver", build_flver(bones=[]))]))
        (game / MODEL_PIECE).parent.mkdir(parents=True, exist_ok=True)
        (game / MODEL_PIECE).write_bytes(make_dcx(build_flver(bones=[])))
        (game / MODEL_HKX).parent.mkdir(parents=True, exist_ok=True)
        (game / MODEL_HKX).write_bytes(b"fake collision bytes")
        (game / MOVIE).parent.mkdir(parents=True, exist_ok=True)
        (game / MOVIE).write_bytes(b"fake movie bytes")
        (game / MUSIC).parent.mkdir(parents=True, exist_ok=True)
        (game / MUSIC).write_bytes(b"fake music bytes")
        (game / SFX).parent.mkdir(parents=True, exist_ok=True)
        (game / SFX).write_bytes(b"fake sfx bytes")
        upload = temp / "replacement.tpf"
        upload.write_bytes(mod_tpf)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    tabs = page.locator("[data-tab]").evaluate_all(
                        "nodes=>nodes.map(n=>n.dataset.tab)")
                    for tab in ("models", "textures", "sound", "music"):
                        assert tab in tabs, tabs
                    assert "other" not in tabs, tabs
                    assert "assets" not in tabs, tabs
                    for tab, wanted in (("models", 4), ("textures", 4), ("sound", 1),
                                        ("music", 1)):
                        page.locator(f'[data-tab="{tab}"]').click()
                        page.wait_for_function(
                            f'state.tab==="{tab}" && state.sub==="files"'
                            f" && state.rows.length==={wanted} && !state.error")
                        # Movies have no tab and list nowhere.
                        assert page.locator(".lex-list-row", has_text="intro.wmv").count() == 0
                    # One merged list: no source subtabs anywhere.
                    assert page.locator("[data-subtab]").count() == 0
                    # Files join the mod through the list's add button.
                    assert page.locator(
                        '#main .lex-table-add[aria-label="Add file to mod"]').count() == 1
                    # A character model: meshes and bones, never objects.
                    page.locator('[data-tab="models"]').click()
                    page.wait_for_function('state.tab==="models" && state.rows.length===4')
                    page.locator(".lex-list-row", has_text=MODEL_CHR).click()
                    page.wait_for_function(
                        f'state.row?.id==="{MODEL_CHR}" && state.assetDetail?.model?.previewable===true'
                        " && state.assetDetail.textures.length===2 && !state.error")
                    assert section_titles(page)[0] == "GEOMETRY"
                    geo = geometry_text(page)
                    assert "MESHES" in geo and "BONES" in geo, geo
                    assert "OBJECTS" not in geo, geo
                    assert page.evaluate("state.assetDetail.model.meshes") == 1
                    assert page.evaluate("state.assetDetail.model.bones") == 1
                    assert page.evaluate("state.assetDetail.model.objects") is None
                    assert "PREVIEW" in section_titles(page)
                    loaded_images(page, "#main .lex-detail-section-content img[alt='c0000_diffuse.dds']")
                    model_max = page.locator(
                        "#main .lex-detail-section-content img[alt='c0000_diffuse.dds']").evaluate(
                        "img=>getComputedStyle(img).maxWidth")
                    assert model_max == "160px", model_max
                    thumbs = page.locator("#main .lex-detail-section-content img.lex-asset-thumbnail").evaluate_all(
                        "nodes=>nodes.map(n=>n.getBoundingClientRect().top)")
                    assert len(thumbs) == 2, thumbs
                    assert max(thumbs) - min(thumbs) < 8, thumbs
                    captions = page.locator(".ds1-texture-strip .ds1-texture-name").evaluate_all(
                        "nodes=>nodes.map(n=>n.textContent)")
                    assert captions == ["c0000_diffuse.dds", "c0000_snormal.dds"], captions
                    stats = page.locator(".lex-detail-section", has_text="GEOMETRY").first.locator(
                        ".lex-detail-part").evaluate_all(
                        "nodes=>nodes.map(n=>n.getBoundingClientRect().top)")
                    assert len(stats) == 2 and max(stats) - min(stats) < 4, stats
                    assert page.locator(".lex-detail-field-label-text", has_text="SOURCE").count() == 0
                    assert page.locator('[data-asset-action="replace"]').count() == 0
                    assert page.locator(".lex-detail-panel-meta").inner_text().strip() != ""
                    thumb = page.locator("img.ds1-model-thumbnail")
                    thumb.wait_for(timeout=30000)
                    page.wait_for_function(
                        "document.querySelector('.lex-detail-panel-heading .lex-detail-panel-icon"
                        " img.ds1-model-thumbnail')?.dataset.modelReady==='true'")
                    if output:
                        page.screenshot(path=str(output / "models-detail.png"))
                    open_drawer(page)
                    painted(page, "canvas[data-preview]")
                    assert page.locator('button[aria-label="Model member"]').count() == 0
                    if output:
                        page.screenshot(path=str(output / "models-drawer.png"))
                    close_drawer(page)
                    assert page.locator("canvas[data-preview]").count() == 0
                    # An object binder counts its member objects and previews each.
                    page.locator(".lex-list-row", has_text=MODEL_OBJ).click()
                    page.wait_for_function(
                        f'state.row?.id==="{MODEL_OBJ}" && state.assetDetail?.model?.previewable===true'
                        " && !state.error")
                    geo = geometry_text(page)
                    assert "OBJECTS" in geo and "MESHES" in geo and "BONES" in geo, geo
                    assert page.evaluate("state.assetDetail.model.objects") == 2
                    assert page.evaluate("state.assetDetail.model.meshes") == 2
                    assert "PREVIEW" in section_titles(page)
                    no_tex = page.locator(".lex-detail-section", has_text="PREVIEW").first.locator(
                        "input").input_value()
                    assert no_tex == "None in this file", no_tex
                    open_drawer(page)
                    painted(page, "canvas[data-preview]")
                    picker = page.locator('button[aria-label="Model member"]')
                    assert picker.inner_text() == "Member: o1000.flver"
                    picker.click()
                    page.get_by_text("o1001.flver", exact=True).click()
                    page.wait_for_function(
                        "document.querySelector('button[aria-label=\"Model member\"]')"
                        "?.textContent==='Member: o1001.flver'")
                    page.wait_for_selector(".lex-model-stage[data-ready='true']", timeout=30000)
                    painted(page, "canvas[data-preview]")
                    close_drawer(page)
                    # Static geometry counts meshes only.
                    page.locator(".lex-list-row", has_text=MODEL_PIECE).click()
                    page.wait_for_function(
                        f'state.row?.id==="{MODEL_PIECE}" && state.assetDetail?.model?.previewable===true'
                        " && !state.error")
                    geo = geometry_text(page)
                    assert "MESHES" in geo, geo
                    assert "BONES" not in geo and "OBJECTS" not in geo, geo
                    # Collision has no mesh to preview and no magnifier.
                    page.locator(".lex-list-row", has_text=MODEL_HKX).click()
                    page.wait_for_function(
                        f'state.row?.id==="{MODEL_HKX}"'
                        " && state.assetDetail?.model?.previewable===false && !state.error")
                    geo = geometry_text(page)
                    assert "INFO" in geo, geo
                    info_value = page.locator(
                        ".lex-detail-section", has_text="GEOMETRY").first.locator(
                        "input").input_value()
                    assert info_value == "Collision data", info_value
                    assert page.locator(".lex-model-preview-trigger").count() == 0
                    assert page.locator(".lex-ds1-no-thumbnail").count() == 1
                    # Textures show thumbnails; the magnifier shows them full-size.
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function('state.tab==="textures" && state.rows.length===4')
                    page.locator(".lex-list-row", has_text=TPF).click()
                    page.wait_for_function(
                        'state.row?.id==="chr/c0000/c0000.tpf" && state.assetDetail?.source==="game"'
                        " && state.assetDetail.textures.length===1 && !state.error")
                    loaded_images(page, "#main .lex-detail-section-content img[alt='c0000_diffuse.dds']")
                    thumb_max = page.locator(
                        "#main .lex-detail-section-content img[alt='c0000_diffuse.dds']").evaluate(
                        "img=>getComputedStyle(img).maxWidth")
                    assert thumb_max == "160px", thumb_max
                    thumb = page.locator(".lex-detail-panel-icon img")
                    assert thumb.count() == 1
                    assert "/api/assets/preview" in thumb.get_attribute("src")
                    page.locator(".lex-detail-panel-meta", has_text="1.2 KB").wait_for()
                    assert page.locator(".lex-detail-field-label-text", has_text="SIZE").count() == 0
                    assert page.locator(".lex-detail-field-label-text", has_text="SOURCE").count() == 0
                    assert page.locator('[data-asset-action="replace"]').count() == 0
                    if output:
                        page.screenshot(path=str(output / "textures-detail.png"))
                    page.locator(".lex-detail-panel-heading .lex-model-preview-trigger").click()
                    page.wait_for_selector(
                        ".lex-model-preview-drawer:not([hidden]) img[alt='c0000_diffuse.dds']")
                    loaded_images(page, ".lex-model-preview-drawer img[alt='c0000_diffuse.dds']")
                    if output:
                        page.screenshot(path=str(output / "textures-drawer.png"))
                    page.locator(".lex-detail-panel-heading .lex-model-preview-trigger").click()
                    page.wait_for_selector(".lex-model-preview-drawer[hidden]", state="attached")
                    page.locator(".lex-list-row", has_text=PNG).click()
                    page.wait_for_function(
                        'state.row?.id==="other/picture.png"'
                        " && state.assetDetail?.textures.length===0 && !state.error")
                    assert page.locator(".lex-model-preview-trigger").count() == 0
                    # Split archives name themselves instead of failing: no modal,
                    # no stuck loader, and the Kind column tells them apart.
                    page.locator(".lex-list-row", has_text=BHD).click()
                    page.wait_for_function(
                        'state.row?.id==="map/m10/m10.tpfbhd"'
                        " && state.assetDetail?.reason==='split-archive' && !state.error")
                    assert page.locator(".lex-detail-field-label-text", has_text="ARCHIVE").count() == 1
                    note = page.locator(".lex-detail-section", has_text="PREVIEW").first.locator("input").input_value()
                    assert note == "Split archive", note
                    assert page.locator(".lex-model-preview-trigger").count() == 0
                    kinds = page.evaluate("state.rows.map(r=>r.display?.kind)")
                    assert kinds.count("Split archive") == 2 and kinds.count("Textures") == 2, kinds
                    assert page.locator("#main .lex-list-row", has_text="Split archive").count() == 2
                    # Sounds and music have no picture and no source row.
                    for tab, wanted in (("sound", SFX), ("music", MUSIC)):
                        page.locator(f'[data-tab="{tab}"]').click()
                        page.wait_for_function(
                            f'state.tab==="{tab}" && state.rows.length===1 && !state.error')
                        page.locator(".lex-list-row", has_text=wanted).click()
                        page.wait_for_function(
                            f'state.row?.id==="{wanted}" && state.assetDetail?.source==="game"'
                            " && state.assetDetail.textures.length===0 && !state.error")
                        assert page.locator("#main img").count() == 0
                        assert page.locator(
                            ".lex-detail-field-label-text", has_text="SOURCE").count() == 0
                        assert page.locator('[data-asset-action="replace"]').count() == 0
                    page.locator(".lex-detail-panel-meta", has_text="16 B").wait_for()
                    # Adding a file at a listed path replaces it through the loader.
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function('state.tab==="textures" && state.rows.length===4')
                    page.locator(".lex-list-row", has_text=TPF).click()
                    page.wait_for_function('state.row?.id==="chr/c0000/c0000.tpf" && state.assetDetail?.textures.length===1')
                    page.locator("#ds1-asset-picker").set_input_files(str(upload))
                    page.wait_for_function(
                        'state.sub==="files" && state.tab==="textures"'
                        ' && state.rows.some(r=>r.id==="chr/c0000/c0000.tpf")'
                        " && state.assetDetail?.source==='mod'"
                        ' && state.assetDetail.textures[0].name==="c0000_custom.dds" && !state.assetBusy && !state.error')
                    assert (mod / TPF).read_bytes() == mod_tpf
                    # 16 head + 20 entry + 17 name + 128 DDS head + 768 pixels.
                    page.locator(".lex-detail-panel-meta", has_text="949 B").wait_for()
                    assert page.locator(
                        ".lex-list-row.lex-record-modified", has_text=TPF).count() == 1
                    assert page.locator("#main img[alt='c0000_custom.dds']").evaluate("img=>img.naturalWidth") > 0
                    if output:
                        page.screenshot(path=str(output / "assets-added.png"))
                    # A replaced file reads modified; a file the game lacks
                    # reads new. The game side marks what the mod shadows.
                    (mod / "chr" / "c9999").mkdir(parents=True)
                    (mod / "chr" / "c9999" / "new.tpf").write_bytes(mod_tpf)
                    page.locator('[data-tab="models"]').click()
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function('state.sub==="files" && state.rows.length===5')
                    assert page.locator(
                        ".lex-list-row.lex-record-modified", has_text=TPF).count() == 1
                    nib = page.locator(".lex-list-row", has_text="new.tpf").locator(".lex-record-source")
                    assert nib.count() == 1
                    assert nib.get_attribute("aria-label") == "Created in this mod"
                    page.locator('[data-tab="models"]').click()
                    page.wait_for_function('state.tab==="models" && state.rows.length===4')
                    assert page.locator(
                        ".lex-list-row.lex-record-modified", has_text=MODEL_CHR).count() == 0
                    assert page.locator(
                        ".lex-list-row .lex-record-source", has_text=MODEL_CHR).count() == 0
                    page.locator('[data-tab="textures"]').click()
                    page.wait_for_function("state.rows.length===5")
                    page.locator(".lex-list-row", has_text="new.tpf").click()
                    page.wait_for_function('state.row?.id==="chr/c9999/new.tpf"')
                    page.locator('[data-asset-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function("state.rows.length===4 && !state.assetBusy && !state.error")
                    page.locator(".lex-list-row", has_text=TPF).click()
                    page.wait_for_function('state.row?.id==="chr/c0000/c0000.tpf"')
                    page.locator('[data-asset-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove").click()
                    page.wait_for_function("state.rows.length===4 && !state.assetBusy && !state.error")
                    page.wait_for_function("state.assetDetail?.source==='game'"
                        " && state.assetDetail.textures.length===1 && !state.error")
                    assert page.locator(".lex-list-row.lex-record-modified").count() == 0
                    assert not (mod / TPF).exists()
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / TPF).read_bytes() == game_tpf
            assert (game / RELATIVE).read_bytes() == make_archive()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 file tabs browse, preview, add and remove passed.")


if __name__ == "__main__":
    main()
