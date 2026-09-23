"""Rendered acceptance for the shared FFX/X-2 editor.

Loads the production markup, CSS, JavaScript and shared framework as separate
resources. Synthetic data is intentionally multi-page; no game payload is used.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://lexeditor.test"


def _state(path: str, rows: list[dict], **extra) -> dict:
    return {
        "source": "archive",
        "archivePath": path,
        "headerMd5": "0123456789abcdef0123456789abcdef",
        "baselineSha256": "a" * 64,
        "rows": rows,
        **extra,
    }


def _rows(count: int, factory):
    return [factory(index) for index in range(count)]


def fixture_store() -> dict[str, object]:
    count = 36
    elements = [
        {"bit": 1, "key": "fire", "label": "Fire"},
        {"bit": 2, "key": "ice", "label": "Ice"},
        {"bit": 4, "key": "thunder", "label": "Thunder"},
        {"bit": 8, "key": "water", "label": "Water"},
        {"bit": 16, "key": "holy", "label": "Holy"},
    ]
    store: dict[str, object] = {
        "/api/dashboard": {
            "game": {
                "ready": True,
                "root": "C:/Games/FINAL FANTASY FFX&FFX-2 HD Remaster",
                "steamAppId": "359870",
            },
            "project": {"root": "C:/Lexeditor/Projects/ffx-x2", "fileCount": 4},
            "deployment": {
                "fahrenheitReady": True,
                "projectFileCount": 4,
                "deployed": False,
            },
            "launch": {
                "ready": True,
                "stage0Ready": True,
                "stage1Ready": True,
                "games": {
                    "x": {"ready": True, "launchReady": True},
                    "x2": {"ready": True, "launchReady": True},
                },
            },
            "theme": {},
            "problems": [],
        },
        "/api/datamap": {
            "rows": [
                {
                    "filename": "FFX_Data/new_uspc/battle/kernel/ply_save.bin",
                    "controls": "Base HP/MP and eight base stats",
                    "notes": "Synthetic browser fixture",
                    "status": "integrated",
                    "coverage": "structured",
                    "target": "ffx-player-stats",
                },
                {
                    "filename": "FFX2_Data/new_uspc/battle/kernel/job.bin",
                    "controls": "Dressphere ability trees",
                    "notes": "Sixteen requirement / learned-ability pairs",
                    "status": "integrated",
                    "coverage": "structured",
                    "target": "ffx2-jobs",
                },
                {
                    "filename": "data/FFX_Data.vbf",
                    "controls": "Read-only archive browser",
                    "notes": "Byte-exact project extraction",
                    "status": "integrated",
                    "coverage": "view",
                    "target": "archive-x",
                },
            ],
        },
        "/api/treasures": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/takara.bin",
            _rows(count, lambda i: {
                "id": i, "kind": [0, 2, 5, 10][i % 4], "kindName": "Fixture",
                "quantity": (i % 9) + 1, "typeId": 0x2000 + i, "summary": f"Reward {i}",
            }),
            minIndex=0, maxIndex=count - 1, recordSize=4,
        ),
        "/api/item-prices": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_rate.bin",
            _rows(count, lambda i: {"id": i, "ordinal": i, "commandId": 0x2000 + i, "gilPrice": 100 + i * 25}),
            minIndex=0, maxIndex=count - 1, recordSize=4, commandBase=0x2000,
        ),
        "/api/auto-ability-prices": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_rate.bin",
            _rows(count, lambda i: {"id": i, "ordinal": i, "abilityId": 0x8000 + i, "gilPrice": 500 + i * 50}),
            minIndex=0, maxIndex=count - 1, recordSize=4, abilityBase=0x8000,
        ),
        "/api/ffx-player-stats": _state(
            "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/ply_save.bin",
            _rows(count, lambda i: {
                "id": i, "baseHp": 520 + i * 10, "baseMp": 12 + i,
                "strength": 15 + i % 20, "defense": 10 + i % 20, "magic": 5 + i % 20,
                "magicDefense": 5 + i % 20, "agility": 10 + i % 20, "luck": 17 + i % 10,
                "evasion": 5 + i % 20, "accuracy": 10 + i % 20,
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x94,
        ),
        "/api/ffx-auto-abilities": _state(
            "FFX_Data/ffx_ps2/ffx/master/new_uspc/battle/kernel/a_ability.bin",
            _rows(count, lambda i: {
                "id": i, "abilityId": 0x8000 + i,
                "strike": i % 32, "absorb": (i + 1) % 32, "immune": (i + 2) % 32,
                "resist": (i + 3) % 32, "weak": (i + 4) % 32,
                "unknownBits": {"strike": 0, "absorb": 0, "immune": 0, "resist": 0, "weak": 0},
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x6C, elementMask=31, elements=elements,
        ),
        "/api/ctb-base": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/ctb_base.bin",
            _rows(count, lambda i: {
                "id": i, "agility": i, "tickSpeed": 70 - i % 30, "icvBonus": i % 16,
                "minIcv": 10 + i, "maxIcv": 20 + i,
            }),
            minIndex=0, maxIndex=count - 1, recordSize=2,
        ),
        "/api/mix-table": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/prepare.bin",
            _rows(count, lambda i: {
                "id": i, "ordinal": i, "originCommandId": 0x2000 + i,
                "definedResults": 112,
                "resultCommandIds": [0x3000 + ((i * 112 + slot) % 0x0FFF) for slot in range(112)],
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0xE0, partnerCount=112, commandBase=0x2000,
        ),
        "/api/item-shops": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/item_shop.bin",
            _rows(count, lambda i: {
                "id": i, "legacyRate": 100 + i, "occupiedSlots": 16,
                "itemIds": [0x2000 + ((i + slot) % 100) for slot in range(16)],
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x22, slotCount=16,
        ),
        "/api/gear-shops": _state(
            "FFX_Data/ffx_ps2/ffx/master/jppc/battle/kernel/arms_shop.bin",
            _rows(count, lambda i: {
                "id": i, "legacyRate": 100 + i, "occupiedSlots": 16,
                "gearIds": [0x0100 + ((i + slot) % 100) for slot in range(16)],
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x22, slotCount=16,
        ),
        "/api/ffx2-abilities": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/command.bin",
            _rows(count, lambda i: {
                "id": i, "nameOffset": i * 4, "nameKey": 0x1000 + i,
                "descriptionOffset": i * 4 + 2, "descriptionKey": 0x2000 + i,
                "animation1": 100 + i, "animation2": 200 + i,
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x8C,
        ),
        "/api/ffx2-accessories": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/accessory.bin",
            _rows(count, lambda i: {
                "id": i, "nameOffset": i * 4, "nameKey": 0x1000 + i,
                "helpOffset": i * 4 + 2, "helpKey": 0x2000 + i, "icon": i % 64,
                "abilityIds": [0x4000 + i * 4 + slot for slot in range(4)],
                "price": 500 + i * 100,
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0x54, abilityCount=4,
        ),
        "/api/ffx2-jobs": _state(
            "FFX2_Data/ffx_ps2/ffx2/master/new_uspc/battle/kernel/job.bin",
            _rows(count, lambda i: {
                "id": i, "nameOffset": i * 4, "nameKey": 0x1000 + i,
                "helpOffset": i * 4 + 2, "helpKey": 0x2000 + i, "icon": i % 64,
                "berserkAction": 0x3000 + i,
                "abilities": [
                    {"requirementId": 0x4000 + i * 16 + slot, "abilityId": 0x5000 + i * 16 + slot}
                    for slot in range(16)
                ],
            }),
            minIndex=0, maxIndex=count - 1, recordSize=0xE4, abilityCount=16, abilityOffset=0x3C,
        ),
    }
    for table, label in [
        ("command", "Commands"), ("item", "Items"),
        ("monmagic1", "Monster Magic 1"), ("monmagic2", "Monster Magic 2"),
    ]:
        store[f"/api/ffx-commands?table={table}"] = _state(
            f"FFX_Data/new_uspc/battle/kernel/{table}.bin",
            _rows(count, lambda i, table=table: {"id": i, "animation1": 1000 + i, "animation2": 2000 + i}),
            table=table, label=label, minIndex=0, maxIndex=count - 1,
            recordSize=0x60 if table in {"command", "item"} else 0x5C,
        )
    return store


SAVE_TO_GET = {
    "/api/treasures/save": "/api/treasures",
    "/api/item-prices/save": "/api/item-prices",
    "/api/auto-ability-prices/save": "/api/auto-ability-prices",
    "/api/ffx-auto-abilities/save": "/api/ffx-auto-abilities",
    "/api/ffx-player-stats/save": "/api/ffx-player-stats",
    "/api/ctb-base/save": "/api/ctb-base",
    "/api/mix-table/save": "/api/mix-table",
    "/api/item-shops/save": "/api/item-shops",
    "/api/gear-shops/save": "/api/gear-shops",
    "/api/ffx2-abilities/save": "/api/ffx2-abilities",
    "/api/ffx2-accessories/save": "/api/ffx2-accessories",
    "/api/ffx2-jobs/save": "/api/ffx2-jobs",
}


def _apply_save(store: dict[str, object], path: str, request: dict) -> dict:
    if path == "/api/ffx-commands/save":
        source = f"/api/ffx-commands?table={request['table']}"
    else:
        source = SAVE_TO_GET[path]
    result = copy.deepcopy(store[source])
    by_id = {row["id"]: row for row in result["rows"]}
    for edit in request["edits"]:
        row = by_id[edit["id"]]
        if path == "/api/mix-table/save":
            for change in edit["results"]:
                row["resultCommandIds"][change["partner"]] = change["resultCommandId"]
        elif path in {"/api/item-shops/save", "/api/gear-shops/save"}:
            key = "itemIds" if path == "/api/item-shops/save" else "gearIds"
            value_key = "itemId" if path == "/api/item-shops/save" else "gearId"
            for change in edit["slots"]:
                row[key][change["slot"]] = change[value_key]
            row["occupiedSlots"] = sum(value != 0 for value in row[key])
        elif path == "/api/ffx2-accessories/save":
            if "price" in edit:
                row["price"] = edit["price"]
            for change in edit.get("abilities", []):
                row["abilityIds"][change["slot"]] = change["abilityId"]
        elif path == "/api/ffx2-jobs/save":
            for change in edit["abilities"]:
                row["abilities"][change["slot"]] = {
                    "requirementId": change["requirementId"],
                    "abilityId": change["abilityId"],
                }
        else:
            for key, value in edit.items():
                if key != "id":
                    row[key] = value
    result["baselineSha256"] = "b" * 64
    result["source"] = "project"
    result["staged"] = True
    result["saved"] = len(request["edits"])
    store[source] = copy.deepcopy(result)
    return result


def _archive_entries(game: str) -> list[dict]:
    prefix = "FFX_Data" if game == "x" else "FFX2_Data"
    return [
        {
            "path": f"{game}_ps2/{game}/master/new_uspc/battle/kernel/fixture_{i:04d}.bin",
            "eflPath": f"{prefix}/{game}_ps2/{game}/master/new_uspc/battle/kernel/fixture_{i:04d}.bin",
            "bytes": 256 + i,
            "blocks": 1 + i % 4,
            "staged": i % 11 == 0,
        }
        for i in range(520)
    ]


def _serve(page, store: dict[str, object]):
    assets = {
        "/": ("text/html", ROOT / "plugins/ffx_x2/editor.html"),
        "/editor.js": ("application/javascript", ROOT / "plugins/ffx_x2/editor.js"),
        "/editor.css": ("text/css", ROOT / "plugins/ffx_x2/editor.css"),
        "/shared/framework.js": ("application/javascript", ROOT / "ui/framework.js"),
        "/shared/framework.css": ("text/css", ROOT / "ui/framework.css"),
        "/shared/mod-loading.json": ("application/json", ROOT / "ui/mod-loading.json"),
        "/shared/credits.json": ("application/json", ROOT / "ui/credits.json"),
    }
    saves = set(SAVE_TO_GET) | {"/api/ffx-commands/save"}

    def handler(route):
        parsed = urlparse(route.request.url)
        path = parsed.path
        if path in assets:
            content_type, target = assets[path]
            route.fulfill(status=200, content_type=content_type, body=target.read_text(encoding="utf-8"))
            return
        if path == "/api/archive":
            query = parse_qs(parsed.query)
            game = query.get("game", ["x"])[0]
            needle = query.get("q", [""])[0].casefold()
            offset = int(query.get("offset", ["0"])[0])
            limit = int(query.get("limit", ["250"])[0])
            rows = [row for row in _archive_entries(game) if needle in row["path"].casefold()]
            payload = {
                "game": game,
                "headerMd5": "0123456789abcdef0123456789abcdef",
                "total": len(rows), "offset": offset, "limit": limit,
                "entries": rows[offset:offset + limit],
            }
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
            return
        key = path + (("?" + parsed.query) if parsed.query else "")
        if route.request.method == "POST":
            request = route.request.post_data_json or {}
            if path in saves:
                payload = _apply_save(store, path, request)
            elif path == "/api/play":
                payload = {"launched": True, "game": request.get("game")}
            elif path == "/api/project/extract":
                payload = {"created": True, "eflPath": request.get("path", "")}
            elif path.endswith("/deploy"):
                store["/api/dashboard"]["deployment"]["deployed"] = True
                payload = store["/api/dashboard"]["deployment"]
            elif path.endswith("/revert"):
                store["/api/dashboard"]["deployment"]["deployed"] = False
                payload = store["/api/dashboard"]["deployment"]
            else:
                payload = {}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
            return
        payload = store.get(key, store.get(path))
        if payload is None:
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": f"Missing fixture for {key}"}))
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/*", handler)


DATASETS = {
    "FFX Battle": [
        "Player Base Stats", "Auto-Ability Elements", "CTB Timing", "Rikku Mix Results",
        "Commands Animations", "Items Animations", "Monster Magic 1 Animations", "Monster Magic 2 Animations",
    ],
    "FFX Economy": ["Treasure Rewards", "Item / Command Prices", "Auto-Ability Prices"],
    "FFX Shops": ["Item Shops", "Gear Shops"],
    "FFX-2": ["FFX-2 Abilities", "FFX-2 Accessories", "FFX-2 Dresspheres"],
    "Archives": ["FFX Archive", "FFX-2 Archive"],
}


def _overflow(page, label: str):
    geometry = page.evaluate("""() => ({
      viewport: innerWidth,
      doc: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      main: document.querySelector('#main')?.scrollWidth || 0,
      mainClient: document.querySelector('#main')?.clientWidth || 0,
      bodyOverflowX: getComputedStyle(document.body).overflowX
    })""")
    assert geometry["doc"] <= geometry["viewport"] + 1, (label, "document overflow", geometry)
    assert (
        geometry["body"] <= geometry["viewport"] + 1
        or geometry["bodyOverflowX"] in {"hidden", "clip"}
    ), (label, "unclipped body overflow", geometry)
    assert geometry["main"] <= geometry["mainClient"] + 1, (label, "main overflow", geometry)


def _assert_detail_owns_vertical_scroll(page, label: str):
    geometry = page.evaluate("""() => {
      const shell = document.querySelector('.lex-shell-header')?.getBoundingClientRect();
      const main = document.querySelector('#main')?.getBoundingClientRect();
      const detail = document.querySelector('#main .lex-detail-panel-body');
      return {
        documentTop: document.scrollingElement?.scrollTop || 0,
        shellBottom: shell?.bottom || 0,
        mainTop: main?.top || 0,
        detailTop: detail?.scrollTop || 0,
        detailHeight: detail?.clientHeight || 0,
        detailScrollHeight: detail?.scrollHeight || 0,
      };
    }""")
    assert geometry["documentTop"] <= 1, (label, "outer document scrolled", geometry)
    assert geometry["mainTop"] + 1 >= geometry["shellBottom"], (label, "shell overlaps editor content", geometry)
    assert geometry["detailScrollHeight"] > geometry["detailHeight"], (label, "tall Detail has no inner scroll range", geometry)
    assert geometry["detailTop"] > 0, (label, "last control did not scroll the Detail body", geometry)


def _open_dataset(page, group: str, dataset: str):
    page.get_by_role("button", name=group, exact=True).click()
    tab = page.get_by_role("tab").filter(has_text=dataset)
    # Keyboard activation: at narrow widths the tab label shrinks to a sliver
    # and a center click lands on the help affordance (which stops propagation
    # instead of switching tabs).
    tab.focus()
    tab.press("Enter")
    expect(tab).to_have_attribute("aria-selected", "true")
    expect(page.locator("#main .lex-master-detail")).to_be_visible()
    # Let list auto-fit settle: it can re-render (detaching inputs) shortly
    # after the first paint on short viewports.
    page.wait_for_function(
        """() => new Promise(resolve => {
          const selector = "#main .lex-column-list-row";
          let last = document.querySelectorAll(selector).length;
          let stable = 0;
          const timer = setInterval(() => {
            const now = document.querySelectorAll(selector).length;
            if (now > 0 && now === last) {
              stable += 1;
              if (stable >= 2) { clearInterval(timer); resolve(true); }
            } else { last = now; stable = 0; }
          }, 250);
          setTimeout(() => { clearInterval(timer); resolve(true); }, 10000);
        })""")
    expect(page.locator("#main .lex-column-list")).to_be_visible()
    expect(page.locator("#main .lex-detail-panel")).to_be_visible()


def _exercise_shared_table(page):
    _open_dataset(page, "FFX Economy", "Treasure Rewards")
    pager = page.locator("#main .lex-pager")
    expect(pager.get_by_role("button", name="Next page")).to_be_enabled()
    pager.get_by_role("button", name="Next page").click()
    expect(pager.locator(".lex-page-number")).to_have_value("2")
    pager.get_by_role("button", name="Previous page").click()
    expect(pager.locator(".lex-page-number")).to_have_value("1")

    page.locator("#main .lex-column-list-head-cell[data-column-key='quantity']").click()
    rows = page.locator("#main .lex-column-list-row")
    rows.nth(1).click()
    expect(page.locator("#main .lex-detail-panel")).to_be_visible()

    search = page.locator("#main input[type='search']")
    search.fill("Reward 35")
    expect(page.locator("#main .lex-column-list-row")).to_have_count(1)
    search.fill("")
    expect(page.locator("#main .lex-column-list-row").first).to_be_visible()

    cell = page.locator("#main .lex-column-list-row").first.locator("[data-column-key='quantity']")
    cell.dblclick()
    editor = cell.locator("input")
    editor.fill("77")
    editor.press("Enter")
    expect(page.locator("#global-save")).to_be_enabled()

    page.locator("#global-save").click(button="right")
    expect(page.get_by_role("alertdialog", name="Discard unsaved changes?")).to_be_visible()
    page.get_by_role("button", name="Discard Changes").click()
    expect(page.locator("#global-save")).to_be_disabled()

    cell = page.locator("#main .lex-column-list-row").first.locator("[data-column-key='quantity']")
    cell.dblclick()
    editor = cell.locator("input")
    editor.fill("78")
    editor.press("Enter")
    page.locator("#global-save").click()
    expect(page.locator("#global-save")).to_be_disabled()


def _exercise_keyboard_help(page):
    page.keyboard.press("Control+M")
    expect(page.locator(".lex-data-map")).to_be_visible()
    expect(page.locator(".lex-column-list-row .lex-integration-status")).to_have_count(3)
    page.keyboard.press("F1")
    expect(page.locator("#main > .lex-panel-layout")).to_be_visible()
    expect(page.locator(".lex-detail-section").filter(has_text="MOD LOADER")).to_be_visible()
    page.get_by_role("button", name="FFX Battle", exact=True).click()
    page.get_by_role("tab").filter(has_text="Player Base Stats").click()
    expect(page.locator(".lex-info-help").first).to_be_visible()
    page.locator(".lex-info-help").first.focus()
    assert page.locator(".lex-info-help").first.evaluate("node => document.activeElement === node")


def _exercise_tall_panels(page):
    _open_dataset(page, "FFX-2", "FFX-2 Dresspheres")
    last = page.get_by_label("Dressphere 0 ability 16", exact=True)
    last.scroll_into_view_if_needed()
    expect(last).to_be_visible()
    _assert_detail_owns_vertical_scroll(page, "desktop:dresspheres")
    last.click()
    last.press("ControlOrMeta+A")
    last.press_sequentially(str(0x5ABC), delay=15)
    expect(last).to_be_focused()
    expect(last).to_have_value("23,228")

    _open_dataset(page, "FFX Battle", "Rikku Mix Results")
    final_mix = page.get_by_label("Partner 111 result command ID", exact=True)
    final_mix.scroll_into_view_if_needed()
    expect(final_mix).to_be_visible()
    _assert_detail_owns_vertical_scroll(page, "desktop:mix")


def _screenshot_all(page, output: Path, suffix: str):
    for group, datasets in DATASETS.items():
        for dataset in datasets:
            _open_dataset(page, group, dataset)
            _overflow(page, f"{suffix}:{dataset}")
            safe = dataset.lower().replace(" ", "-").replace("/", "-")
            page.screenshot(path=str(output / f"{safe}-{suffix}.png"))
    page.locator("#plugin-data-map").click()
    expect(page.locator(".lex-data-map")).to_be_visible()
    page.screenshot(path=str(output / f"data-map-{suffix}.png"))
    page.locator("#plugin-info").click()
    expect(page.locator("#main > .lex-panel-layout")).to_be_visible()
    page.screenshot(path=str(output / f"info-{suffix}.png"))


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    store = fixture_store()
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            _serve(page, store)
            page.goto(BASE + "/", wait_until="networkidle")
            expect(page.get_by_role("button", name="FFX Battle", exact=True)).to_be_visible()
            _exercise_shared_table(page)
            page.reload(wait_until="networkidle")
            _open_dataset(page, "FFX Economy", "Treasure Rewards")
            quantity = page.get_by_label("Quantity", exact=True)
            expect(quantity).to_have_value("78")
            _exercise_keyboard_help(page)
            _exercise_tall_panels(page)
            _screenshot_all(page, output, "desktop")
            assert not errors, errors
            page.close()

            narrow = browser.new_page(viewport={"width": 760, "height": 720})
            narrow_errors: list[str] = []
            narrow.on("pageerror", lambda error: narrow_errors.append(str(error)))
            _serve(narrow, store)
            narrow.goto(BASE + "/", wait_until="networkidle")
            _open_dataset(narrow, "FFX-2", "FFX-2 Dresspheres")
            _overflow(narrow, "narrow:dresspheres")
            last = narrow.get_by_label("Dressphere 0 ability 16", exact=True)
            last.scroll_into_view_if_needed()
            expect(last).to_be_visible()
            _assert_detail_owns_vertical_scroll(narrow, "narrow:dresspheres")
            narrow.screenshot(path=str(output / "dresspheres-narrow.png"))
            _open_dataset(narrow, "FFX Battle", "Rikku Mix Results")
            final_mix = narrow.get_by_label("Partner 111 result command ID", exact=True)
            final_mix.scroll_into_view_if_needed()
            expect(final_mix).to_be_visible()
            _assert_detail_owns_vertical_scroll(narrow, "narrow:mix")
            _overflow(narrow, "narrow:mix")
            narrow.screenshot(path=str(output / "mix-narrow.png"))
            assert not narrow_errors, narrow_errors
            narrow.close()

            scaled_context = browser.new_context(
                viewport={"width": 800, "height": 533},
                device_scale_factor=1.5,
            )
            scaled = scaled_context.new_page()
            scaled_errors: list[str] = []
            scaled.on("pageerror", lambda error: scaled_errors.append(str(error)))
            _serve(scaled, store)
            scaled.goto(BASE + "/", wait_until="networkidle")
            _open_dataset(scaled, "FFX-2", "FFX-2 Dresspheres")
            last = scaled.get_by_label("Dressphere 0 ability 16", exact=True)
            last.scroll_into_view_if_needed()
            expect(last).to_be_visible()
            _assert_detail_owns_vertical_scroll(scaled, "150pct:dresspheres")
            _overflow(scaled, "150pct:dresspheres")
            scaled.screenshot(path=str(output / "dresspheres-150pct.png"))
            _open_dataset(scaled, "FFX Battle", "Rikku Mix Results")
            final_mix = scaled.get_by_label("Partner 111 result command ID", exact=True)
            final_mix.scroll_into_view_if_needed()
            expect(final_mix).to_be_visible()
            _assert_detail_owns_vertical_scroll(scaled, "150pct:mix")
            _overflow(scaled, "150pct:mix")
            scaled.screenshot(path=str(output / "mix-150pct.png"))
            assert not scaled_errors, scaled_errors
            scaled_context.close()
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "artifacts/ffx-x2-browser")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
