"""Map viewport fetches each shared texture blob once per map.

Nine fixture pieces wear the same diffuse bytes. Geometry loads
in batches, each batch sending the content ids it already holds
as known; responses omit those blobs but keep the id mapping,
and the viewport rebuilds per-model dicts from the shared store
so every model still renders textured. The urllib half pins the
server contract, the browser half watches the wire.
Synthetic fixtures only; read-only with no mod.
"""
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

PIECES = 9


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-dedupe-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        names = ['m10p%d' % index for index in range(PIECES)]
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb(
            parts=[("piece", 0, index, 1 + index, None) for index in range(PIECES)],
            models=[("c1200", 0)] + [(name, 0) for name in names]))
        piece_dir = game / 'map' / 'm10_00_00_00'
        piece_dir.mkdir(parents=True)
        red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
        for name in names:
            (piece_dir / (name + '.flver.dcx')).write_bytes(build_flver())
            (piece_dir / (name + '.tpf')).write_bytes(make_tpf([('tex0', red)]))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            base = session.url + '/api/map/geometry?map=m10_00_00_00.msb&model='
            first = fetch(base + names[0])
            assert set(first['textures']) == {'tex0'}, sorted(first['textures'])
            assert set(first['texture_ids']) == {'tex0'}, first.get('texture_ids')
            again = fetch(base + names[1] + '&known=' + first['texture_ids']['tex0'])
            assert again['textures'] == {}, sorted(again['textures'])
            assert again['texture_ids'] == first['texture_ids'], again.get('texture_ids')
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    wire = []

                    def on_response(response):
                        if '/api/map/geometry' not in response.url:
                            return
                        try:
                            wire.append((response.url, response.json()))
                        except Exception as error:
                            errors.append('wire read: %s' % error)

                    page.on('response', on_response)
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab === "maps" && !state.error',
                                           timeout=120000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]',
                                           timeout=120000)
                    assert len(wire) == PIECES, len(wire)
                    assert any('known=' in url for url, _ in wire), 'client sends no known ids'
                    assert any(data['textures'] == {} and data['texture_ids']
                               for _, data in wire), 'no response omitted a known blob'
                    seam = page.evaluate(
                        "!!document.querySelector('[data-viewport-host]')._viewportScene")
                    assert seam, 'no viewport scene seam'
                    textured = page.evaluate(
                        """() => { const scene = document.querySelector(
                            '[data-viewport-host]')._viewportScene;
                            let count = 0;
                            scene.traverse(obj => {
                              if (obj.isMesh && obj.material && obj.material.map)
                                count += 1; });
                            return count; }""")
                    assert textured == PIECES, textured
                    if output:
                        page.locator('[data-viewport-host]').screenshot(
                            path=str(output / 'map-dedupe.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 map texture dedupe passed.')


if __name__ == '__main__':
    main()
