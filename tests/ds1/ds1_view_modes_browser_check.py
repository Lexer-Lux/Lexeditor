"""DS1 map viewport shows the shared Regular/Fullbright/Wireframe modes.

Corner buttons with icons sit top-left of the map view, retint the live
render when clicked, and Regular restores the lit picture. Read-only with
no mod, on synthetic map data, never game files.
"""
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bhf_fixture import make_bhf, make_edge
from ds1_fixture import make_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

LABELS = ["Regular", "Fullbright", "Wireframe"]


def make_game(temp):
    game = temp / "game"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / "m10_01_00_00.msb").write_bytes(build_msb())
    (game / "map" / "m10_01_00_00").mkdir(parents=True)
    (game / "map" / "m10_01_00_00" / "m10piece.flver").write_bytes(build_flver())
    red = make_dds_rgba(4, 4, [(220, 30, 30, 255)] * 16)
    blob = make_edge(make_tpf([("tex0", red)]))
    area = game / "map" / "m10"
    area.mkdir(parents=True)
    (area / "m10_0000.tpfbdt").write_bytes(bytes(16) + blob)
    (area / "m10_0000.tpfbhd").write_bytes(
        make_bhf([(r"\m10\tex0.tpf.dcx", 16, len(blob))]))
    return game


def shot(page):
    raw = page.locator("canvas[data-viewport]").screenshot()
    return Image.open(io.BytesIO(raw)).convert("RGB")


def fraction_different(first, second):
    assert first.size == second.size, (first.size, second.size)
    left, right = first.tobytes(), second.tobytes()
    changed = sum(1 for index in range(0, len(left), 3)
                  if abs(left[index] - right[index]) > 8
                  or abs(left[index + 1] - right[index + 1]) > 8
                  or abs(left[index + 2] - right[index + 2]) > 8)
    return changed / (len(left) / 3)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-view-modes-") as folder:
        game = make_game(Path(folder))
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_NO_MOD": "1",
                              "LEXEDITOR_MOD_READ_ONLY": "1"})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('button[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView && state.rows.length>0 && !state.error',
                                           timeout=60000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                    modes = page.locator("[data-viewport-host] .lex-model-view-modes button")
                    assert modes.count() == 3
                    assert [modes.nth(index).get_attribute("aria-label")
                            for index in range(3)] == LABELS
                    for index in range(3):
                        assert modes.nth(index).locator("svg").count() == 1, LABELS[index]
                    assert modes.nth(0).get_attribute("aria-pressed") == "true"
                    host = page.locator("[data-viewport-host]").bounding_box()
                    bar = page.locator("[data-viewport-host] .lex-model-view-modes").bounding_box()
                    assert bar["x"] - host["x"] < 16, (host, bar)
                    assert host["y"] + host["height"] - (bar["y"] + bar["height"]) < 16, (host, bar)
                    assert bar["x"] + bar["width"] < host["x"] + host["width"] / 2, (host, bar)
                    page.wait_for_timeout(500)
                    regular = shot(page)
                    raw = regular.tobytes()
                    red = sum(1 for i in range(0, len(raw), 3)
                              if raw[i] > raw[i + 1] + 30 and raw[i] > raw[i + 2] + 30)
                    assert red > 100, f"map renders gray ({red} red pixels)"
                    if output:
                        page.locator("[data-viewport-host]").screenshot(
                            path=str(output / "ds1-viewport-regular.png"))
                    modes.nth(1).click()
                    assert modes.nth(1).get_attribute("aria-pressed") == "true"
                    page.wait_for_timeout(600)
                    lit = shot(page)
                    if output:
                        page.locator("[data-viewport-host]").screenshot(
                            path=str(output / "ds1-viewport-fullbright.png"))
                    changed = fraction_different(regular, lit)
                    assert changed > 0.02, f"fullbright left the render alone ({changed:.4f})"
                    modes.nth(2).click()
                    assert modes.nth(2).get_attribute("aria-pressed") == "true"
                    page.wait_for_timeout(600)
                    wired = shot(page)
                    if output:
                        page.locator("[data-viewport-host]").screenshot(
                            path=str(output / "ds1-viewport-wireframe.png"))
                    changed = fraction_different(regular, wired)
                    assert changed > 0.02, f"wireframe left the render alone ({changed:.4f})"
                    modes.nth(0).click()
                    assert modes.nth(0).get_attribute("aria-pressed") == "true"
                    page.wait_for_timeout(600)
                    restored = shot(page)
                    changed = fraction_different(regular, restored)
                    assert changed < 0.01, f"regular did not restore the render ({changed:.4f})"
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print("DS1 viewer modes passed.")


if __name__ == "__main__":
    main()
