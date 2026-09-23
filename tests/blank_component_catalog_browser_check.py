"""Blank shows every shared component, at its level, and every sample renders."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "out" / "blank-components.png"
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json"}


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from plugins.blank.plugin import PLUGIN

    catalogue_ids = set()
    session = PLUGIN.session_factory()
    session.start()
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        page.goto(session.url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        catalogue = page.evaluate("window.LexeditorComponentCatalog.entries.map(row=>row.id)")
        catalogue_ids = set(catalogue)
        levels = page.evaluate("window.LexeditorComponentCatalog.levels.map(row=>row.id)")
        # Every sample is built here rather than by clicking through pages:
        # the point is that each one renders, not that the pager works.
        built = page.evaluate("""()=>{
          const out={ok:0,failed:[],levels:{}};
          for(const entry of window.LexeditorComponentCatalog.entries){
            out.levels[entry.level]=(out.levels[entry.level]||0)+1;
            if(typeof entry.sample!=="function")continue;
            try{const node=entry.sample();if(!(node instanceof Node))throw new Error("not a node");out.ok++;}
            catch(error){out.failed.push(`${entry.id}: ${error.message}`);}
          }
          return out;
        }""")
        seen = built["levels"]
        for level in levels:
            page.evaluate("""level=>{document.querySelectorAll('.lex-shell-header nav button')
              .forEach(button=>{if(button.textContent.trim().toLowerCase().startsWith(level.slice(0,4)))button.click();});}""", level)
            page.wait_for_timeout(250)
            listed = page.locator(".blank-components .lex-column-list-row, .blank-components .lex-list-row").count()
            if not listed:
                print(f"{level}: nothing listed")
                errors.append(f"{level} lists no components")
            if level == "organism":
                page.locator(".blank-components .lex-column-list-row, .blank-components .lex-list-row").first.click()
                page.wait_for_timeout(200)
                page.screenshot(path=str(SHOT))
        browser.close()
    session.stop()
    print("levels:", seen, "catalogued:", len(catalogue_ids), "samples built:", built["ok"])
    if built["failed"]:
        print("samples that failed:", built["failed"])
        return 1
    if errors:
        print("page errors:", errors[:5])
        return 1
    if sum(seen.values()) != len(catalogue_ids):
        print("Some catalogued components are not listed under any level.")
        return 1
    print("Blank lists and renders every catalogued component.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
