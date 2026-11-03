"""A lightmap without its own UV set renders rig-lit, never streaked.

The diffuse UV set tiles while a lightmap is a clamped atlas, so
sampling the atlas with copied diffuse UVs smears atlas edges into
streaks across the mesh. The geometry API leaves uv1 empty when the
mesh has no second set, and the viewport then renders the mesh with
the rig-lit standard material instead of a lightmapped one.
"""
import base64
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from flver_fixture import build_flver  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from tpf_fixture import make_dds_rgba, make_tpf  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1.store import RELATIVE  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def make_game(folder):
    game = Path(folder) / 'game'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / 'map' / 'MapStudio').mkdir(parents=True)
    (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
    piece_dir = game / 'map' / 'm10_00_00_00'
    piece_dir.mkdir(parents=True)
    (piece_dir / 'm10piece.flver.dcx').write_bytes(build_flver(
        light_tex='lit0', uv_scale=4.0))
    gray = make_dds_rgba(2, 2, [(180, 180, 180, 255)] * 4)
    light = make_dds_rgba(4, 4, [
        (round(255 * x / 3), round(255 * x / 3), round(255 * x / 3), 255)
        for y in range(4) for x in range(4)])
    (piece_dir / 'm10piece.tpf').write_bytes(make_tpf([('tex0', gray),
                                                       ('lit0', light)]))
    return game


def test_no_uv_copy_fallback_in_api():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-litfb-') as folder:
        game = make_game(folder)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        try:
            session.start()
            with urllib.request.urlopen(
                    session.url + '/api/map/geometry?map=m10_00_00_00.msb&model=m10piece',
                    timeout=60) as response:
                data = json.load(response)
            mesh = data['meshes'][0]
            assert mesh['light'] == 'lit0', mesh.get('light')
            assert not base64.b64decode(mesh['uv1']), 'uv1 must stay empty'
        finally:
            session.stop()
            assert session.wait_closed()


def test_fallback_mesh_renders_rig_lit():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-litfb-') as folder:
        game = make_game(folder)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab === "maps" && !state.error',
                                           timeout=120000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]',
                                           timeout=120000)
                    page.wait_for_timeout(2000)
                    materials = page.evaluate(
                        """() => { const scene = document.querySelector(
                            '[data-viewport-host]')._viewportScene;
                            const out = [];
                            scene.traverse(obj => {
                              if (obj.isMesh && obj.material
                                  && (obj.material.isMeshStandardMaterial
                                      || obj.material.isMeshBasicMaterial)
                                  && obj.material.map)
                                out.push(obj.material.type
                                         + (obj.material.lightMap ? '+light' : '')); });
                            return out; }""")
                    assert materials, 'no textured model meshes in the scene'
                    assert all(entry == 'MeshStandardMaterial' for entry in materials), materials
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
