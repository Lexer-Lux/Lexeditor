"""Fixture-only rendered acceptance for the fresh Chrono Trigger Steam editor."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

DASHBOARD = {
    "game": {"root": r"C:\\Games\\Chrono Trigger", "archive": r"C:\\Games\\Chrono Trigger\\resources.bin", "resourceCount": 7421},
    "project": {"root": r"C:\\Mods\\ChronoFresh", "changeCount": 0},
    "languages": ["en"], "defaultLanguage": "en",
}
TEXT_PATH = "Localize/en/msg/cmes0.txt"
TEXT_FILES = {"language": "en", "rows": [TEXT_PATH, "Localize/en/msg/item.txt"]}
MESSAGES = {
    "path": TEXT_PATH, "source": "vanilla", "sha256": "text-sha-1",
    "rows": [
        {"token": "0:FLD_001", "key": "FLD_001", "text": "Welcome to the fair.", "line": 0},
        {"token": "1:FLD_002", "key": "FLD_002", "text": "The gate is open.", "line": 1},
        {"token": "2:FLD_003", "key": "FLD_003", "text": "Need anything?", "line": 2},
    ],
}
SCENES = {
    "language": "en", "source": "mine",
    "rows": [
        {"token": "1", "id": 1, "name": "Millennial Fair", "path": "Game/field/Mapinfo/mapinfo_1.dat",
         "source": "vanilla", "sha256": "scene-sha-1", "musicIndex": 10,
         "layer12TilesetIndex": 1, "layer12AssemblyIndex": 2, "layer3TilesetIndex": 3,
         "paletteIndex": 4, "paletteAnimationIndex": 5, "mapIndex": 6, "chipAnimationIndex": 7,
         "scriptIndex": 8, "unknownWord": 48879, "cameraUnbounded": False,
         "scrollLeft": 0, "scrollTop": 1, "scrollRight": 14, "scrollBottom": 15, "trailingBytes": 2},
        {"token": "2", "id": 2, "name": "Guardia Forest", "path": "Game/field/Mapinfo/mapinfo_2.dat",
         "source": "vanilla", "sha256": "scene-sha-2", "musicIndex": 12,
         "layer12TilesetIndex": 4, "layer12AssemblyIndex": 5, "layer3TilesetIndex": 6,
         "paletteIndex": 7, "paletteAnimationIndex": 8, "mapIndex": 9, "chipAnimationIndex": 10,
         "scriptIndex": 11, "unknownWord": 4660, "cameraUnbounded": True,
         "scrollLeft": 128, "scrollTop": 0, "scrollRight": 0, "scrollBottom": 0, "trailingBytes": 0},
    ],
}
EXITS = {
    "source": "vanilla", "dataSha256": "exit-data-1", "offsetSha256": "exit-offset-1",
    "rows": [
        {"token": "12:0", "sceneId": 12, "exitId": 0, "xTile": 4, "yTile": 7, "lengthTiles": 2,
         "orientation": "horizontal", "destinationId": 18, "destinationKind": "scene", "facing": 1,
         "halfTileLeft": False, "halfTileUp": True, "targetX": 9, "targetY": 11,
         "unknownFacingBits": 160, "byteOffset": 4},
        {"token": "12:1", "sceneId": 12, "exitId": 1, "xTile": 14, "yTile": 2, "lengthTiles": 1,
         "orientation": "vertical", "destinationId": 496, "destinationKind": "world", "facing": 2,
         "halfTileLeft": True, "halfTileUp": False, "targetX": 18, "targetY": 20,
         "unknownFacingBits": 64, "byteOffset": 12},
    ],
}
TREASURE = {
    "source": "vanilla", "dataSha256": "treasure-data-1", "offsetSha256": "treasure-offset-1",
    "kinds": ["weapon", "armor", "helmet", "accessory", "consumable", "item", "gold"],
    "rows": [
        {"token": "12:0", "sceneId": 12, "treasureId": 0, "xTile": 5, "yTile": 8, "alias": False,
         "aliasScene": None, "kind": "armor", "gold": None, "localIndex": 2, "globalItemId": 113,
         "itemName": "Ruby Vest", "trailingWord": 51966, "editable": True, "byteOffset": 4},
        {"token": "13:0", "sceneId": 13, "treasureId": 0, "xTile": 0, "yTile": 0, "alias": True,
         "aliasScene": 12, "kind": "weapon", "gold": None, "localIndex": 12, "globalItemId": 12,
         "itemName": "", "trailingWord": 48879, "editable": False, "byteOffset": 10},
    ],
}
PALETTE_FILES = {"rows": [{"path": "Game/field/palette_bin/plt4.bin", "id": 4, "kind": "Area", "label": "Area palette 4"}]}
PALETTE = {
    "path": "Game/field/palette_bin/plt4.bin", "source": "vanilla", "sha256": "palette-sha-1",
    "prefixHex": "1234", "trailingBytes": 1,
    "rows": [
        {"token": str(index), "index": index, "hex": "#FF0000" if index == 0 else "#000000",
         "red5": 31 if index == 0 else 0, "green5": 0, "blue5": 0,
         "preservedBit15": index == 0}
        for index in range(256)
    ],
}
WORLD_ROW = {
    "token": "0", "id": 0, "name": "World 0", "source": "vanilla", "byteOffset": 0xFD10,
    "paletteIndex": 10, "paletteAnimationIndex": 11,
    "layer12AssemblyIndex": 16, "mapIndex": 17, "mapPropertiesIndex": 18,
    "musicPropertiesIndex": 19, "layer3AssemblyIndex": 20, "exitsIndex": 21, "scriptIndex": 22,
}
WORLD_ROW.update({f"layer12Graphics{index}": index for index in range(8)})
WORLD_ROW.update({f"layer3Graphics{index}": 8 + index for index in range(2)})
WORLD_ROW.update({f"spriteGraphics{index}": 12 + index for index in range(4)})
WORLDS = {"path": "Game/common/bankc6.bin", "source": "vanilla", "sha256": "world-sha-1", "rows": [WORLD_ROW]}
DATA_MAP = {"rows": [
    {"filename": "resources.bin", "controls": "Steam resource archive", "notes": "Read-only ARC1 source.", "coverage": "source", "status": "partial", "openable": False, "target": "info"},
    {"filename": "Localize/<lang>/msg/*.txt", "controls": "Dialogue, menu and item text", "notes": "Keyed text editor.", "coverage": "structured", "status": "integrated", "openable": True, "target": "text"},
    {"filename": "Game/common/MapJumpOffsetTbl.dat + MapJumpDataTbl.dat", "controls": "Area exits", "notes": "Existing fixed-size exits.", "coverage": "structured", "status": "integrated", "openable": True, "target": "exits"},
    {"filename": "Game/common/TakaraOffsetTbl.dat + TakaraDataTbl.dat", "controls": "Treasure chests", "notes": "Existing fixed-size treasure.", "coverage": "structured", "status": "integrated", "openable": True, "target": "treasure"},
    {"filename": "Game/field/Mapinfo/mapinfo_*.dat", "controls": "Area settings", "notes": "Fixed Steam area headers.", "coverage": "structured", "status": "integrated", "openable": True, "target": "scenes"},
    {"filename": "Game/field/palette_bin/plt*.bin + Game/world/plt_bin/plt*.bin", "controls": "Area and world palettes", "notes": "Fixed 256-color RGB555 palettes.", "coverage": "structured", "status": "integrated", "openable": True, "target": "palettes"},
    {"filename": "Game/common/bankc6.bin @ 0xFD10", "controls": "World settings", "notes": "Seven fixed 23-byte Steam world headers.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worlds"},
    {"filename": "Game/world/Map + Id + EventTable + esl + colanim_bin", "controls": "World maps, exits, triggers and scripts", "notes": "Remaining world formats.", "coverage": "unavailable", "status": "not-integrated", "openable": False, "target": None},
]}
CHANGES = {"rows": []}


def editor_html() -> str:
    html = (ROOT / "games/chrono_trigger/editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<link rel="stylesheet" href="/editor.css">',
        "<style>" + (ROOT / "games/chrono_trigger/editor.css").read_text(encoding="utf-8") + "</style>",
    )
    fixtures = {
        "dashboard": DASHBOARD, "textFiles": TEXT_FILES, "messages": MESSAGES, "scenes": SCENES,
        "exits": EXITS, "treasure": TREASURE, "paletteFiles": PALETTE_FILES, "palette": PALETTE, "worlds": WORLDS, "dataMap": DATA_MAP, "changes": CHANGES,
    }
    stub = r"""
    window.__posts=[];
    window.__fixtures=FIXTURES;
    window.fetch=async function(input,options={}){
      const u=new URL(String(input),"http://fixture/");
      const path=u.pathname, f=window.__fixtures;
      let result=null, status=200;
      if((options.method||"GET").toUpperCase()==="POST"){
        const body=JSON.parse(options.body||"{}");window.__posts.push({path,body});
        if(path==="/api/messages/save"){
          for(const edit of body.edits||[]){
            const row=f.messages.rows.find(value=>value.line===edit.line&&value.key===edit.key);
            if(row)row.text=edit.text;
          }
          f.messages.sha256="text-sha-2";f.messages.source="project";
          f.changes.rows=[{path:f.messages.path,size:123,status:"modified",sha256:"fixture"}];
          result=f.messages;
        }else if(path==="/api/export"){
          result={path:"C:/Mods/ChronoFresh/build/ChronoFresh.ctp",fileCount:f.changes.rows.length,files:f.changes.rows.map(x=>x.path)};
        }else if(path==="/api/scenes/save"){
          const row=f.scenes.rows.find(value=>value.id===body.id);
          if(row){Object.assign(row,body.values||{});row.sha256="scene-sha-saved";row.source="project";}
          result=row;
        }else if(path==="/api/palette/save"){
          for(const edit of body.edits||[]){const row=f.palette.rows.find(value=>value.token===edit.token);if(row)row.hex=edit.hex;}
          f.palette.sha256="palette-sha-saved";f.palette.source="project";result=f.palette;
        }else if(path==="/api/worlds/save"){
          for(const edit of body.edits||[]){
            const row=f.worlds.rows.find(value=>value.token===edit.token);
            if(row)Object.assign(row,edit.values||{});
          }
          f.worlds.sha256="world-sha-saved";f.worlds.source="project";result=f.worlds;
        }else if(path==="/api/exits/save")result=f.exits;
        else if(path==="/api/treasure/save")result=f.treasure;
        else result={};
      }else if(path==="/api/dashboard")result=f.dashboard;
      else if(path==="/api/datamap")result=f.dataMap;
      else if(path==="/api/changes")result=f.changes;
      else if(path==="/api/text-files")result=f.textFiles;
      else if(path==="/api/messages")result=f.messages;
      else if(path==="/api/scenes")result=f.scenes;
      else if(path==="/api/palette-files")result=f.paletteFiles;
      else if(path==="/api/palette")result=f.palette;
      else if(path==="/api/worlds")result=f.worlds;
      else if(path==="/api/exits")result=f.exits;
      else if(path==="/api/treasure")result=f.treasure;
      else {status=404;result={error:"Unknown fixture request "+path};}
      return new Response(JSON.stringify(result),{status,headers:{"Content-Type":"application/json"}});
    };
    """.replace("FIXTURES", json.dumps(fixtures))
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + stub + "</script><script>" + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<script src="/editor.js"></script>',
        "<script>" + (ROOT / "games/chrono_trigger/editor.js").read_text(encoding="utf-8") + "</script>",
    )
    return html


def metrics(page):
    return page.evaluate("""() => {
      const main=document.querySelector('#main')?.getBoundingClientRect();
      return {bodyHeight:document.body.scrollHeight, viewportHeight:innerHeight,
              bodyWidth:document.body.scrollWidth, viewportWidth:innerWidth,
              mainBottom:main?.bottom||0};
    }""")


def main():
    errors=[]; results=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(
            executable_path=shutil.which("chromium") or None, headless=True,
            args=["--no-sandbox","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],
        )
        try:
            for width,height in [(1200,800),(900,620)]:
                page=browser.new_page(viewport={"width":width,"height":height})
                page.on("pageerror",lambda error: errors.append(str(error)))
                page.route("http://127.0.0.1:9/**",lambda route: route.fulfill(status=200,body="<html></html>",content_type="text/html"))
                page.goto("http://127.0.0.1:9/")
                page.set_content(editor_html(),wait_until="domcontentloaded")
                page.wait_for_selector(".ct-long-text")
                assert not errors,errors
                assert page.locator(".lex-paged-list-detail").count()==1
                page.locator(".ct-long-text").fill("Changed in rendered acceptance")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled && document.querySelector('.ct-long-text')?.value.includes('rendered acceptance')")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/messages/save')")
                page.screenshot(path=str(ARTIFACTS/f"text-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Areas").click()
                page.locator("#main").get_by_text("PC WORD", exact=True).wait_for()
                assert "Millennial Fair" in page.locator("#main").inner_text()
                assert "PC WORD" in page.locator("#main").inner_text()
                assert page.get_by_label("PC WORD",exact=True).input_value()=="0xBEEF"
                page.screenshot(path=str(ARTIFACTS/f"areas-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Worlds").click()
                page.locator("#main").get_by_text("PALETTE ANIMATION BYTE", exact=True).wait_for()
                assert "World 0" in page.locator("#main").inner_text()
                assert page.get_by_label("BYTE OFFSET",exact=True).input_value()=="0xFD10"
                page.get_by_label("MAP",exact=True).fill("42")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/worlds/save')")
                assert page.get_by_label("MAP",exact=True).input_value()=="42"
                page.screenshot(path=str(ARTIFACTS/f"worlds-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Area Exits").click()
                page.locator("#main").get_by_text("PRESERVED BITS", exact=True).wait_for()
                assert "PRESERVED BITS" in page.locator("#main").inner_text()
                assert page.get_by_label("PRESERVED BITS",exact=True).input_value()=="0xA0"
                page.screenshot(path=str(ARTIFACTS/f"exits-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Treasure").click()
                page.locator("#main").get_by_text("PRESERVED WORD", exact=True).wait_for()
                assert "Ruby Vest" in page.locator("#main").inner_text()
                assert page.get_by_label("PRESERVED WORD",exact=True).input_value()=="0xCAFE"
                page.screenshot(path=str(ARTIFACTS/f"treasure-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Palettes").click()
                page.locator('input[type="color"]').wait_for()
                assert page.locator('input[type="color"]').count()==1
                assert "BIT 15" in page.locator("#main").inner_text()
                page.screenshot(path=str(ARTIFACTS/f"palettes-{width}.png"),full_page=True)

                page.locator("#plugin-data-map").click()
                page.locator(".lex-data-map-table").wait_for()
                assert page.locator(".lex-data-map-table").count()==1
                assert "Area settings" in page.locator("#main").inner_text()
                layout=metrics(page)
                assert layout["bodyHeight"]<=height+2,layout
                assert layout["mainBottom"]<=height+2,layout
                assert layout["bodyWidth"]<=width+2,layout
                page.screenshot(path=str(ARTIFACTS/f"datamap-{width}.png"),full_page=True)
                results.append({"width":width,"height":height,"metrics":layout,"status":"passed"})
                page.close()
        finally:
            browser.close()
    (ARTIFACTS/"results.json").write_text(json.dumps({"fixtureOnly":True,"results":results,"errors":errors},indent=2),encoding="utf-8")
    assert not errors,errors
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    main()
