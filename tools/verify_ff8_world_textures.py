"""Identity, mutation, API, and rendered checks for FF8 texl.obj support."""

from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import paths, world_textures  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def raw_get(url: str, path: str) -> tuple[bytes, dict]:
    with urlopen(url + path, timeout=30) as response:
        return response.read(), dict(response.headers.items())


def rejects(data: bytes, edit: dict, label: str) -> None:
    try:
        world_textures.apply_edits(data, [edit])
    except ValueError:
        return
    raise AssertionError(f"texl writer accepted {label}")


def verify_binary() -> dict:
    original_roots = (paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT,
                      paths.DIRECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="lexeditor-world-texture-binary-") as name:
        root = Path(name)
        try:
            paths.DATA_ROOT = root / "data"
            paths.BASELINE_ROOT = paths.DATA_ROOT / "baseline" / "en"
            paths.PROJECT_ROOT = root / "project"
            paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
            baseline = world_textures.ensure_baseline()
            before = baseline.read_bytes()
            parsed = world_textures.parse(before)
            assert len(before) == 20 * 0x12800
            assert len(parsed["rows"]) == 20
            assert all((row["width"], row["height"], row["depth"],
                        row["paletteCount"], row["timBytes"])
                       == (256, 256, 8, 16, 0x12020)
                       for row in parsed["rows"])

            texture_id = 3
            original_tim = world_textures.tim_bytes(texture_id, "vanilla")
            identity = world_textures.apply_edits(before, [{
                "id": texture_id,
                "timBase64": base64.b64encode(original_tim).decode("ascii"),
            }])
            assert identity == before

            replacement = bytearray(original_tim)
            replacement[-1] ^= 1
            edit = {"id": texture_id,
                    "timBase64": base64.b64encode(replacement).decode("ascii")}
            after = world_textures.apply_edits(before, [edit])
            changed = [index for index, pair in enumerate(zip(before, after))
                       if pair[0] != pair[1]]
            expected = texture_id * world_textures.SLOT_SIZE + len(replacement) - 1
            assert changed == [expected], changed
            slot_start = texture_id * world_textures.SLOT_SIZE
            used_end = slot_start + len(replacement)
            slot_end = slot_start + world_textures.SLOT_SIZE
            assert after[used_end:slot_end] == before[used_end:slot_end]
            assert after[:slot_start] == before[:slot_start]
            assert after[slot_end:] == before[slot_end:]

            rejects(before, {"id": texture_id, "timBase64": "not base64"}, "invalid base64")
            rejects(before, {"id": texture_id, "timBase64": base64.b64encode(
                original_tim[:-1]).decode("ascii")}, "short TIM")
            wrong_header = bytearray(original_tim)
            wrong_header[0] ^= 1
            rejects(before, {"id": texture_id, "timBase64": base64.b64encode(
                wrong_header).decode("ascii")}, "invalid TIM header")
            rejects(before, {"id": texture_id + 20, "timBase64": edit["timBase64"]},
                    "invalid texture ID")
            try:
                world_textures.apply_edits(before, [edit, edit])
            except ValueError:
                pass
            else:
                raise AssertionError("texl writer accepted a duplicate texture edit")

            png = world_textures.png_bytes(texture_id, 15, "vanilla")
            image = Image.open(BytesIO(png))
            assert image.size == (256, 256) and image.mode == "RGBA"
            return {"textures": 20, "slotBytes": 0x12800, "timBytes": 0x12020,
                    "changedOffsets": changed, "pngBytes": len(png)}
        finally:
            paths.DATA_ROOT, paths.BASELINE_ROOT, paths.PROJECT_ROOT, paths.DIRECT_ROOT = original_roots


def verify_api_and_rendered() -> dict:
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-world-texture-api-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/world-map?dataset=vanilla")
            assert len(payload["textures"]) == 20
            png, png_headers = raw_get(
                session.url, "/assets/world-textures/0.png?dataset=vanilla&palette=15")
            assert png.startswith(b"\x89PNG\r\n\x1a\n")
            assert png_headers["Content-Type"] == "image/png"
            assert Image.open(BytesIO(png)).size == (256, 256)
            tim, tim_headers = raw_get(
                session.url, "/assets/world-textures/0.tim?dataset=vanilla")
            assert len(tim) == 0x12020 and tim.startswith(b"\x10\0\0\0")
            assert "world-texture-1.tim" in tim_headers["Content-Disposition"]

            replacement = bytearray(tim)
            replacement[-1] ^= 1
            saved = api(session.url, "/api/world-map/save", {"edits": [{
                "kind": "worldTexture", "id": 0,
                "timBase64": base64.b64encode(replacement).decode("ascii"),
            }]})
            assert saved["saved"] == 1 and saved["files"][0].endswith("texl.obj"), saved
            current, _ = raw_get(session.url, "/assets/world-textures/0.tim?dataset=current")
            assert current == replacement

            profile, browser, cdp = browser_session()
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('world')")
            wait_eval(cdp, "document.querySelectorAll('.world-map-tabs [role=tab]').length===9", 30)
            cdp.eval("[...document.querySelectorAll('.world-map-tabs [role=tab]')].find(n=>n.textContent.includes('World Textures')).click()")
            wait_eval(cdp, "document.querySelector('.world-map-detail.world-texture img')?.naturalWidth===256", 30)
            rendered = cdp.eval("""(()=>{const panel=document.querySelector('.world-map-detail.world-texture'),image=panel.querySelector('.world-texture-preview'),select=panel.querySelector('select[aria-label$="preview palette"]'),links=[...panel.querySelectorAll('.world-texture-actions a')],buttons=[...panel.querySelectorAll('.world-texture-actions button')];return{
              active:document.querySelector('.world-map-tabs [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              image:[image.naturalWidth,image.naturalHeight],
              palettes:select.options.length,
              exportTim:links.some(node=>node.download.endsWith('.tim')),
              replaceTim:buttons.some(node=>node.textContent.includes('Replace TIM')&&!node.disabled),
              fileInput:!!panel.querySelector('input[type=file][accept*=".tim"]'),
              metadata:panel.querySelector('.world-texture-metadata')?.textContent,
              overflow:document.querySelector('.world-map-view').scrollWidth>document.querySelector('.world-map-view').clientWidth+1,
            }})()""")
            assert rendered["active"] == "World Textures", rendered
            assert rendered["image"] == [256, 256] and rendered["palettes"] == 16, rendered
            assert rendered["exportTim"] and rendered["replaceTim"] and rendered["fileInput"], rendered
            assert "256 × 256" in rendered["metadata"] and "8-bit indexed" in rendered["metadata"], rendered
            assert not rendered["overflow"], rendered
            # The shared page transition keeps the old snapshot briefly after
            # the new DOM is ready. Capture the settled panel, not that frame.
            time.sleep(0.8)
            settled = cdp.eval("""(()=>{const panel=document.querySelector('.world-map-detail.world-texture'),rect=panel?.getBoundingClientRect();return{dirty:dirtyCount(),width:rect?.width||0,height:rect?.height||0,image:panel?.querySelector('.world-texture-preview')?.naturalWidth||0}})()""")
            assert settled["dirty"] == 0 and settled["width"] > 400 and settled["height"] > 300, settled
            assert settled["image"] == 256, settled
            rendered["settled"] = settled
            rendered["screenshot"] = str(screenshot(
                cdp, "goal-61-64-ff8-world-textures.png"))
            return rendered
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    print({"binary": verify_binary(), "apiRendered": verify_api_and_rendered()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
