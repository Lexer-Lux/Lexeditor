"""Rendered RDR1 acceptance for shared Detail rows and semantic info bubbles.

Uses the production RDR1 editor plus shared framework with synthetic API data. No
installed game, game assets, native runtime, or network access is required.
"""
from pathlib import Path
import argparse
import json
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def document() -> str:
    item = {
        "id": "base:0", "name": "ITEM_TEST", "friendlyName": "Test Item",
        "type": "Inventory", "source": "base", "sourceLabel": "Base game",
        "index": 0, "sourcePath": "game/content.rpf/items.xml",
        "project": False, "projectPath": "project/items.xml",
        "fields": [{
            "field": "Amount", "value": "3", "control": "number", "step": 1,
            "minimum": 0, "maximum": 99, "storage": "value",
        }],
    }
    items = {"rows": [item], "sources": [{"id": "base", "label": "Base game"}]}
    mission = {
        "id": 2, "name": "New Friends, Old Problems", "scriptName": "Ranch 01",
        "assetPath": "content/missions/ranch/ranch01", "localizationKey": "MISSION_RANCH_01",
        "archivePath": "game/content.rpf/ranch01.wsc",
        "rewardSource": {"file": "ranch01.wsc", "function": "completion", "case": "success"},
        "rewards": {"cash": 0, "fame": 0, "honor": 50},
        "baseRewards": {"cash": 0, "fame": 0, "honor": 50}, "project": False,
    }
    string_table = {
        "table": {"id": "tuning:tune/stringtable/global.strtbl", "source": "tuning",
                  "sourceLabel": "Tuning", "path": "tune/stringtable/global.strtbl",
                  "label": "global", "available": True, "sourcePath": "prepared/global.strtbl",
                  "projectPath": "project/global.strtbl", "project": False,
                  "rowCount": 1, "languageCount": 1, "version": 256, "identifierCount": 1},
        "rows": [{"id": "tuning:tune/stringtable/global.strtbl:0:0:12345678",
                  "tableId": "tuning:tune/stringtable/global.strtbl", "source": "tuning",
                  "sourceLabel": "Tuning", "path": "tune/stringtable/global.strtbl",
                  "sourcePath": "prepared/global.strtbl", "projectPath": "project/global.strtbl",
                  "project": False, "languageIndex": 0, "languageIndexes": [0],
                  "language": "English", "entryIndex": 0, "hash": "0x12345678",
                  "hashValue": 305419896, "identifier": "HELLO",
                  "identifierCandidates": ["HELLO"], "text": "Hello",
                  "sharedLanguageBlock": False}],
        "counts": {"records": 1, "languages": 1, "identifiers": 1},
    }
    strings = {
        "tables": [{**string_table["table"],
                    "languages": [{"id": "0", "index": 0, "label": "English"},
                                  {"id": "2", "index": 2, "label": "French"}]}],
        "languages": [{"id": "0", "index": 0, "label": "English"},
                      {"id": "2", "index": 2, "label": "French"}],
        "counts": {"tables": 1, "available": 1, "records": 1, "project": 0},
    }
    strings_payload = {
        "language": {"id": "0", "index": 0, "label": "English"},
        "languages": strings["languages"],
        "rows": string_table["rows"],
        "counts": {"records": 1, "tables": 1, "availableTables": 1},
    }
    rbf_payload = {
        "rows": [{
            "id": "tune/ai/protected.tune:24",
            "resourcePath": "tune/ai/protected.tune",
            "recordOffset": 24,
            "descriptorIndex": 2,
            "name": "Scale",
            "path": "Tuning/Scale",
            "role": "child",
            "kind": "float",
            "value": 1.0,
            "typeOffset": 25,
            "writeOffset": 26,
            "writeSize": 4,
            "rawHex": "0000803f",
            "sourcePath": "prepared/protected.tune",
            "projectPath": "project/protected.tune",
            "project": False,
        }],
        "resources": [{
            "path": "tune/ai/protected.tune", "scalarCount": 1,
            "descriptorCount": 3, "trailingBytes": 0,
            "skipped": {"strings": 1, "float3": 0, "byteBlocks": 0},
            "project": False,
        }],
        "counts": {"resources": 1, "scalars": 1, "project": 0},
    }
    missions = {
        "missions": [mission],
        "limits": {"step": 1, "rewards": {
            "cash": {"minimum": -100000, "maximum": 100000},
            "fame": {"minimum": -100000, "maximum": 100000},
            "honor": {"minimum": -100000, "maximum": 100000},
        }},
    }
    responses = {
        "/api/files": {"rows": [], "counts": {}},
        "/api/dashboard": {"redHook": {"installed": True}, "deployment": {}, "paths": {}},
        "/api/items": items,
        "/api/items?dataset=vanilla": items,
        "/api/shops": {"rows": []},
        "/api/shops?dataset=vanilla": {"rows": []},
        "/api/string-tables": strings,
        "/api/string-tables?dataset=vanilla": strings,
        "/api/string-table": string_table,
        "/api/strings?language=0": strings_payload,
        "/api/strings?language=0&dataset=vanilla": strings_payload,
        "/api/rbf-scalars": rbf_payload,
        "/api/rbf-scalars?dataset=vanilla": rbf_payload,
        "/api/missions": missions,
        "/api/missions?dataset=vanilla": missions,
        "/api/settings": {"available": False, "sections": [], "reason": "Synthetic fixture"},
        "/api/loot": {"available": False, "document": None, "reason": "Synthetic fixture"},
        "/api/redhook/configure": {},
    }
    fixture = """
window.__requests=[];window.__responses=RESPONSES;
history.replaceState=()=>{};history.pushState=()=>{};
window.fetch=async function(url,options={}) {
  const parsed=new URL(url,'https://lexeditor.test/');
  const key=parsed.pathname+parsed.search;
  const body=options.body?JSON.parse(options.body):null;
  window.__requests.push({path:key,method:options.method||'GET',body});
  const data=Object.prototype.hasOwnProperty.call(window.__responses,key)
    ? window.__responses[key] : (window.__responses[parsed.pathname]||{});
  return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
};
""".replace("RESPONSES", json.dumps(responses))
    html = (ROOT / "plugins/rdr/editor.html").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + fixture + "</script><script>" +
        (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<link rel="stylesheet" href="editor.css">',
        "<style>" + (ROOT / "plugins/rdr/editor.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="strings.js"></script>',
        "<script>" + (ROOT / "plugins/rdr/strings.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<script src="rbf.js"></script>',
        "<script>" + (ROOT / "plugins/rdr/rbf.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<script src="editor.js"></script>',
        "<script>" + (ROOT / "plugins/rdr/editor.js").read_text(encoding="utf-8") + "</script>",
    )
    return html.replace("<head>", '<head><base href="https://lexeditor.test/">', 1)


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            for width, height, zoom in ((1200, 800, 100), (900, 620, 100), (1200, 800, 150)):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.route("**/*", lambda route: route.abort())
                page.set_content(document(), wait_until="domcontentloaded")
                page.wait_for_function("!state.booting")
                if zoom != 100:
                    page.evaluate("(value) => { document.documentElement.style.zoom = value; }", zoom / 100)
                    page.wait_for_timeout(100)
                assert not errors, errors

                page.evaluate("state.itemSelected='base:0'; renderItems()")
                fields = page.locator(".record-detail .lex-detail-field")
                expect(fields).to_have_count(5)
                assert page.locator(".record-detail .detail-field").count() == 0
                amount = fields.filter(has_text="Amount").first
                expect(amount.locator("input[type=number]")).to_have_value("3")
                assert amount.locator(".lex-info-help").count() == 0, "storage metadata became an info bubble"
                # Read geometry from the current DOM in the same browser task
                # that checks readiness. A locator resolved after a separate wait
                # can refer to a detail node detached by the next fit render.
                geometry = page.wait_for_function("""() => {
                  const rows=[...document.querySelectorAll('.record-detail .lex-detail-field')];
                  const field=rows.find(row=>row.textContent.includes('Amount'));
                  const label=field?.querySelector('.lex-detail-field-label');
                  if (!field || !label) return false;
                  const b=field.getBoundingClientRect(), l=label.getBoundingClientRect();
                  if (!field.isConnected || b.width<=0 || l.width<=0) return false;
                  return {field:b.width,label:l.width,ratio:l.width/b.width};
                }""").json_value()
                assert 0.075 <= geometry["ratio"] <= 0.16, (width, "RDR1 bypassed shared adaptive label lane", geometry)
                page.screenshot(path=str(output / f"rdr-items-{width}-zoom{zoom}.png"), full_page=True)

                page.evaluate("state.tab='strings'; stringsUI.render()")
                expect(page.locator(".string-detail textarea")).to_have_value("Hello")
                expect(page.locator(".rdr-record-list .lex-column-list-row:not(.lex-filler-row)")).to_have_count(1)
                expect(page.locator(".string-detail .lex-detail-field")).to_have_count(7)
                expect(page.get_by_role("tab", name="🇺🇸 English")).to_have_count(1)
                assert page.get_by_label("Select string table").count() == 0
                resource = page.locator(".string-detail .lex-detail-field").filter(
                    has_text="Resource").first
                expect(resource.locator("input.lex-readonly-field")).to_have_value(
                    "tune/stringtable/global.strtbl")
                assert page.locator(".string-detail .lex-record-id").count() == 0
                page.screenshot(path=str(output / f"rdr-strings-{width}-zoom{zoom}.png"), full_page=True)

                page.evaluate("state.tab='rbf'; state.rbfSelected='tune/ai/protected.tune:24'; rbfUI.render()")
                expect(page.locator('nav button[data-tab="rbf"] .lex-tab-label-text')).to_have_text("Tuning")
                expect(page.locator(".rbf-detail .lex-detail-field-label").filter(has_text="File")).to_have_count(1)
                expect(page.locator(".rdr-record-list .lex-column-list-row:not(.lex-filler-row)")).to_have_count(1)
                expect(page.locator(".rbf-detail .lex-detail-field")).to_have_count(7)
                expect(page.get_by_label("Tuning/Scale", exact=True)).to_have_value("1")
                assert page.locator(".rbf-detail .lex-record-id").count() == 0
                page.screenshot(path=str(output / f"rdr-rbf-{width}-zoom{zoom}.png"), full_page=True)

                page.evaluate("state.tab='missions'; state.missionSelected=2; renderMissions()")
                expect(page.locator(".mission-detail .lex-detail-field")).to_have_count(9)
                bubbles = page.locator(".mission-detail .lex-info-help")
                expect(bubbles).to_have_count(3)
                labels = bubbles.evaluate_all("els=>els.map(e=>e.getAttribute('aria-label'))")
                assert any("cash awarded when this mission completes" in text for text in labels), labels
                assert any("completion Fame award independently" in text for text in labels), labels
                assert any("completion Honor adjustment independently" in text for text in labels), labels
                assert all("Base value" not in text and "range" not in text.lower() for text in labels), labels
                page.screenshot(path=str(output / f"rdr-missions-{width}-zoom{zoom}.png"), full_page=True)
                assert not errors, errors
                page.close()
                print(f"PASS: RDR1 shared Detail + semantic info bubbles at {width}x{height}, zoom {zoom}%")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "artifacts/rdr-browser")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
