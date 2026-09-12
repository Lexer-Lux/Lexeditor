"""Synthetic rendered acceptance for the FFX/X-2 editor composition.

Exercises the production editor plus its dynamically composed UI modules without an
installed game, proprietary assets, Fahrenheit binaries, or network access.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def _state(archive_path: str, **extra):
    return {
        "source": "installed",
        "archivePath": archive_path,
        "headerMd5": "0123456789abcdef0123456789abcdef",
        "baselineSha256": "a" * 64,
        **extra,
    }


def responses() -> dict[str, object]:
    item_slots = [0x2000, 0x2001] + [0] * 14
    gear_slots = [0x100, 0x101] + [0] * 14
    return {
        "/api/dashboard": {
            "game": {"ready": True, "root": "C:/Games/FINAL FANTASY FFX&FFX-2 HD Remaster"},
            "archives": [
                {"game": "x", "ready": True, "fileCount": 12000, "bytes": 400_000_000},
                {"game": "x2", "ready": True, "fileCount": 9000, "bytes": 300_000_000},
            ],
            "project": {"fileCount": 1, "root": "C:/Lexeditor/Projects/ffx-x2"},
            "theme": {
                "source": "fallback",
                "background": {"ready": False},
                "font": {"webReady": False, "atlasRecognized": 0, "atlasCached": 0},
                "textures": {"recognized": 0, "cached": 0},
                "sfx": {"webReady": False, "recognizedBanks": 0, "cachedBanks": 0},
            },
            "deployment": {
                "fahrenheitReady": True,
                "fahrenheitRoot": "C:/Games/FINAL FANTASY FFX&FFX-2 HD Remaster/fahrenheit",
                "projectFileCount": 1,
                "deployed": False,
                "deployedChangedExternally": False,
            },
        },
        "/api/datamap": {
            "rows": [
                {
                    "filename": "FFX_Data/new_uspc/battle/kernel/ply_save.bin",
                    "status": "integrated",
                    "controls": "Base HP/MP and eight base stats",
                    "notes": "Synthetic browser fixture",
                    "target": "ffx-player-stats",
                },
                {
                    "filename": "FFX2_Data/new_uspc/battle/kernel/accessory.bin",
                    "status": "integrated",
                    "controls": "Base abilities and price",
                    "notes": "Creature extension remains opaque",
                    "target": "ffx2-accessories",
                },
            ]
        },
        "/api/archive?game=x&q=&limit=150": {
            "game": "x",
            "total": 1,
            "headerMd5": "0123456789abcdef0123456789abcdef",
            "entries": [
                {
                    "path": "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/ply_save.bin",
                    "eflPath": "FFX_Data/new_uspc/battle/kernel/ply_save.bin",
                    "bytes": 296,
                    "staged": False,
                }
            ],
        },
        "/api/treasures": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin",
            recordSize=4,
            rows=[{"id": 0, "kind": 2, "quantity": 1, "typeId": 0x2000}],
        ),
        "/api/item-prices": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin",
            commandBase=0x2000,
            rows=[{"id": 0, "commandId": 0x2000, "gilPrice": 50}],
        ),
        "/api/auto-ability-prices": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin",
            abilityBase=0x8000,
            rows=[{"id": 0, "abilityId": 0x8000, "gilPrice": 100}],
        ),
        "/api/ctb-base": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin",
            rows=[{"id": 0, "agility": 1, "tickSpeed": 30, "icvBonus": 5, "minIcv": 85, "maxIcv": 90}],
        ),
        "/api/mix-table": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin",
            commandBase=0x2000,
            rows=[{"id": 0, "originCommandId": 0x2000, "definedResults": 1, "resultCommandIds": [0x2010, 0]}],
        ),
        "/api/item-shops": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin",
            rows=[{"id": 0, "occupiedSlots": 2, "legacyRate": 100, "itemIds": item_slots}],
        ),
        "/api/gear-shops": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin",
            rows=[{"id": 0, "occupiedSlots": 2, "legacyRate": 100, "gearIds": gear_slots}],
        ),
        "/api/ffx2-abilities": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin",
            recordSize=0x58,
            rows=[{
                "id": 0,
                "nameOffset": 1,
                "nameKey": 2,
                "descriptionOffset": 3,
                "descriptionKey": 4,
                "animation1": 10,
                "animation2": 11,
            }],
        ),
        "/api/ffx2-accessories": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/accessory.bin",
            recordSize=0x54,
            rows=[{
                "id": 0,
                "icon": 7,
                "price": 500,
                "nameOffset": 1,
                "nameKey": 2,
                "helpOffset": 3,
                "helpKey": 4,
                "abilityIds": [0x8000, 0x8001, 0, 0],
            }],
        ),
        "/api/ffx2-jobs": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/job.bin",
            recordSize=0xE4, abilityCount=16, abilityOffset=0x3C,
            rows=[{
                "id": 0, "icon": 9, "berserkAction": 0x3000,
                "nameOffset": 1, "nameKey": 2, "helpOffset": 3, "helpKey": 4,
                "abilities": [
                    {"requirementId": 0x4000 + slot, "abilityId": 0x5000 + slot}
                    for slot in range(16)
                ],
            }],
        ),
        "/api/launch": {
            "platformSupported": True,
            "stage0Ready": True,
            "stage1Ready": True,
            "games": {
                "x": {"ready": True, "launchReady": True, "reason": ""},
                "x2": {"ready": True, "launchReady": True, "reason": ""},
            },
        },
        "/api/play": {"launched": True},
        "/api/ffx-commands?table=command": _state(
            "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/command.bin",
            table="command",
            label="Commands",
            recordSize=0x60,
            rows=[{"id": 0, "animation1": 20, "animation2": 21}],
        ),
        "/api/ffx-auto-abilities": _state(
            "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/a_ability.bin",
            elementMask=0x1F,
            elements=[
                {"bit": 0x01, "label": "Fire"},
                {"bit": 0x02, "label": "Ice"},
                {"bit": 0x04, "label": "Thunder"},
                {"bit": 0x08, "label": "Water"},
                {"bit": 0x10, "label": "Holy"},
            ],
            rows=[{
                "id": 0,
                "abilityId": 0x8000,
                "strike": 0x01,
                "absorb": 0,
                "immune": 0,
                "resist": 0,
                "weak": 0x02,
                "unknownBits": {"strike": 0, "absorb": 0, "immune": 0, "resist": 0, "weak": 0},
            }],
        ),
        "/api/ffx-player-stats": _state(
            "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/ply_save.bin",
            recordSize=0x94,
            rows=[{
                "id": 0,
                "baseHp": 520,
                "baseMp": 12,
                "strength": 15,
                "defense": 10,
                "magic": 5,
                "magicDefense": 5,
                "agility": 10,
                "luck": 17,
                "evasion": 5,
                "accuracy": 10,
            }],
        ),
    }


def document() -> str:
    fixture = """
window.__requests=[];window.__responses=RESPONSES;
history.replaceState=()=>{};history.pushState=()=>{};
window.fetch=async function(url,options={}) {
  const parsed=new URL(url,'https://lexeditor.test/');
  const key=parsed.pathname+parsed.search;
  const body=options.body?JSON.parse(options.body):null;
  window.__requests.push({path:key,method:options.method||'GET',body});
  const data=Object.prototype.hasOwnProperty.call(window.__responses,key)
    ? window.__responses[key]
    : (window.__responses[parsed.pathname]||{});
  return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
};
""".replace("RESPONSES", json.dumps(responses()))
    html = (ROOT / "games/ffx_x2/editor.html").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + fixture + "</script><script>" +
        (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    return html.replace("<head>", '<head><base href="https://lexeditor.test/">', 1)


SHARED_SCRIPTS = {
    "/shared/ffx-x2-accessories.js": ROOT / "ui/ffx-x2-accessories.js",
    "/shared/ffx-x2-jobs.js": ROOT / "ui/ffx-x2-jobs.js",
    "/shared/ffx-x2-launch.js": ROOT / "ui/ffx-x2-launch.js",
    "/shared/ffx-commands.js": ROOT / "ui/ffx-commands.js",
    "/shared/ffx-auto-abilities.js": ROOT / "ui/ffx-auto-abilities.js",
    "/shared/ffx-player-stats.js": ROOT / "ui/ffx-player-stats.js",
}


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            for width, height in ((1200, 800), (760, 700)):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def serve_shared(route):
                    path = urlparse(route.request.url).path
                    target = SHARED_SCRIPTS.get(path)
                    if target:
                        route.fulfill(status=200, content_type="application/javascript", body=target.read_text(encoding="utf-8"))
                    else:
                        route.abort()

                page.route("**/*", serve_shared)
                page.set_content(document(), wait_until="domcontentloaded")

                expect(page.locator(".ffxx2-nav [data-view]")).to_have_count(17)
                expect(page.locator("#ffxx2-play-controls")).to_have_count(1)
                expect(page.locator("#ffxx2-mod-loader .lex-detail-field")).to_have_count(5)
                expect(page.locator("#ffxx2-mod-loader")).to_contain_text("MOD LOADER")
                expect(page.get_by_role("textbox", name="LOADER", exact=True)).to_have_value("Fahrenheit's External File Loader (EFL) loads this plugin's file-only overlay.")
                expect(page.locator("#ffx-command-rows [data-ffx-command]")).to_have_count(1)
                expect(page.locator("#ffx-auto-ability-fields [data-element-group]")).to_have_count(5)
                expect(page.locator("#ffx-player-fields .ffxx2-slot")).to_have_count(10)
                expect(page.locator("#x2-accessory-fields .ffxx2-slot")).to_have_count(5)
                expect(page.locator("#x2-job-fields .ffxx2-slot")).to_have_count(16)
                expect(page.locator("#error")).to_have_text("")
                assert not errors, errors

                expect(page.locator("#ffxx2-play-x")).to_be_enabled()
                expect(page.locator("#ffxx2-play-x2")).to_be_enabled()
                page.locator("#ffxx2-play-x").click()
                expect(page.locator("#ffxx2-play-status")).to_contain_text("FFX launched through Fahrenheit Stage 0")
                play_requests = page.evaluate("window.__requests.filter(r=>r.path==='/api/play')")
                assert play_requests[-1] == {"path": "/api/play", "method": "POST", "body": {"game": "x"}}, play_requests

                page.locator('[data-view="ffx-player-stats"]').click()
                expect(page.locator('[data-panel="ffx-player-stats"]')).to_be_visible()
                base_hp = page.get_by_label("Base HP for player-stat record 0")
                expect(base_hp).to_have_value("520")
                base_hp.fill("999")
                expect(page.locator("#ffx-player-save")).to_be_enabled()
                expect(page.locator("#ffx-player-summary")).to_contain_text("unsaved base-stat edit")

                page.locator('[data-view="ffx2-accessories"]').click()
                expect(page.locator('[data-panel="ffx2-accessories"]')).to_be_visible()
                expect(page.get_by_label("Accessory 0 price")).to_have_value("500")

                page.locator('[data-view="ffx2-jobs"]').click()
                expect(page.locator('[data-panel="ffx2-jobs"]')).to_be_visible()
                expect(page.get_by_label("Dressphere 0 ability 1 requirement")).to_have_value(str(0x4000))
                expect(page.get_by_label("Dressphere 0 ability 1")).to_have_value(str(0x5000))
                page.get_by_label("Dressphere 0 ability 1").fill(str(0x5ABC))
                expect(page.locator("#x2-job-save")).to_be_enabled()

                geometry = page.evaluate("""() => ({
                  viewport: innerWidth,
                  document: document.documentElement.scrollWidth,
                  workspace: document.querySelector('.ffxx2-workspace').getBoundingClientRect().width,
                  panel: document.querySelector('[data-panel="ffx2-jobs"]').getBoundingClientRect().width,
                })""")
                assert geometry["document"] <= geometry["viewport"] + 1, (width, "document overflow", geometry)
                assert geometry["workspace"] <= geometry["viewport"] + 1, (width, "workspace overflow", geometry)
                assert geometry["panel"] > 0, (width, "active panel collapsed", geometry)
                assert not errors, errors
                page.screenshot(path=str(output / f"ffx-x2-accessories-{width}.png"), full_page=True)
                page.close()
                print(f"PASS: FFX/X-2 composed editor at {width}x{height}")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "artifacts/ffx-x2-browser")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
