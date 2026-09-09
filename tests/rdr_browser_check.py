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
    html = (ROOT / "games/rdr/editor.html").read_text(encoding="utf-8")
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
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.route("**/*", lambda route: route.abort())
                page.set_content(document(), wait_until="domcontentloaded")
                page.wait_for_function("!state.booting")
                assert not errors, errors

                page.evaluate("state.itemSelected='base:0'; renderItems()")
                fields = page.locator(".record-detail .lex-detail-field")
                expect(fields).to_have_count(5)
                assert page.locator(".record-detail .detail-field").count() == 0
                amount = fields.filter(has_text="Amount").first
                expect(amount.locator("input[type=number]")).to_have_value("3")
                assert amount.locator(".lex-info-help").count() == 0, "storage metadata became an info bubble"
                # pagedListDetail finishes split sizing through its layout lifecycle.
                # DOM presence is not enough: measuring during that brief zero-width
                # phase makes this visual regression flaky on busy hosted runners.
                page.wait_for_function("""() => {
                  const rows=[...document.querySelectorAll('.record-detail .lex-detail-field')];
                  const field=rows.find(row=>row.textContent.includes('Amount'));
                  const label=field?.querySelector('.lex-detail-field-label');
                  return !!field && !!label && field.getBoundingClientRect().width>0 && label.getBoundingClientRect().width>0;
                }""")
                geometry = amount.evaluate("""e=>{
                  const b=e.getBoundingClientRect(), l=e.querySelector('.lex-detail-field-label').getBoundingClientRect();
                  return {field:b.width,label:l.width,ratio:l.width/b.width};
                }""")
                assert 0.075 <= geometry["ratio"] <= 0.125, (width, "RDR1 bypassed shared ~10% label lane", geometry)
                page.screenshot(path=str(output / f"rdr-items-{width}.png"), full_page=True)

                page.evaluate("state.tab='missions'; state.missionSelected=2; renderMissions()")
                expect(page.locator(".mission-detail .lex-detail-field")).to_have_count(9)
                bubbles = page.locator(".mission-detail .lex-info-help")
                expect(bubbles).to_have_count(3)
                labels = bubbles.evaluate_all("els=>els.map(e=>e.getAttribute('aria-label'))")
                assert any("cash awarded when this mission completes" in text for text in labels), labels
                assert any("completion Fame award independently" in text for text in labels), labels
                assert any("completion Honor adjustment independently" in text for text in labels), labels
                assert all("Base value" not in text and "range" not in text.lower() for text in labels), labels
                page.screenshot(path=str(output / f"rdr-missions-{width}.png"), full_page=True)
                assert not errors, errors
                page.close()
                print(f"PASS: RDR1 shared Detail + semantic info bubbles at {width}x{height}")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "artifacts/rdr-browser")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
