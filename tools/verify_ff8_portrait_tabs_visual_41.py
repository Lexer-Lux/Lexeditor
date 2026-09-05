"""Hidden Edge visual and interaction proof for Lexeditor issue 41."""

from __future__ import annotations

import base64
import json
import re
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def capture(cdp: Cdp, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    shot = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    output.write_bytes(base64.b64decode(shot["data"]))


def snapshot(cdp: Cdp, output_stem: str, width: int, height: int) -> dict:
    cdp.call("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
    })
    cdp.eval("navigate('gfs')")
    wait_eval(cdp, "document.querySelectorAll('.ff8-portrait-tab').length===16", 30)
    wait_eval(cdp, "[...document.querySelectorAll('.ff8-portrait-tab img')].every(img=>img.complete&&img.naturalWidth===32)", 30)
    gf = cdp.eval("""(()=>{const tabs=[...document.querySelectorAll('.ff8-portrait-tab')],chosen=tabs[12],expected=Number(chosen.id.replace('gfs-tab-',''));chosen.click();return{count:tabs.length,images:tabs.filter(tab=>tab.querySelector('img').complete&&tab.querySelector('img').naturalWidth===32).length,expected,selected:state.selected.gfs,panel:Number(document.querySelector('#gf-detail').dataset.gf),names:tabs.map(tab=>tab.title),selectedName:document.querySelector('.ff8-portrait-selected-name')?.textContent,selectedId:document.querySelector('.ff8-portrait-selected-id')?.textContent,repeatedId:document.querySelector('.gf-panel-id')?.textContent||'',missing:tabs.filter(tab=>tab.classList.contains('missing-portrait')).length}})()""")
    if gf["count"] != 16 or gf["images"] != 16 or gf["selected"] != gf["expected"] or gf["panel"] != gf["expected"] or gf["missing"]:
        raise AssertionError(gf)
    capture(cdp, ROOT / "worklog" / "issues" / "rendered" / f"{output_stem}-gfs.png")
    cdp.eval("navigate('characters')")
    wait_eval(cdp, "document.querySelectorAll('.ff8-portrait-tab').length===11", 30)
    wait_eval(cdp, "[...document.querySelectorAll('.ff8-portrait-tab img')].every(img=>img.complete&&img.naturalWidth===32)", 30)
    character = cdp.eval("""(()=>{let tabs=[...document.querySelectorAll('.ff8-portrait-tab')],expected=Number(tabs[8].id.replace('characters-tab-',''));tabs[8].click();tabs=[...document.querySelectorAll('.ff8-portrait-tab')];const boxes=tabs.map(tab=>{const r=tab.getBoundingClientRect(),image=tab.querySelector('img').getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,imageW:image.width,imageH:image.height,fit:getComputedStyle(tab.querySelector('img')).objectFit}}),curves=[...document.querySelectorAll('.ff8-character-curve')];return{count:tabs.length,images:tabs.filter(tab=>tab.querySelector('img').complete&&tab.querySelector('img').naturalWidth===32).length,expected,selected:state.selected.characters,panel:Number(document.querySelector('#character-detail').dataset.character),names:tabs.map(tab=>tab.title),selectedName:document.querySelector('.ff8-portrait-selected-name')?.textContent,selectedId:document.querySelector('.ff8-portrait-selected-id')?.textContent,detailHead:document.querySelectorAll('#character-detail>.detail-head').length,missing:tabs.filter(tab=>tab.classList.contains('missing-portrait')).length,boxes,collapsibles:document.querySelectorAll('#character-detail details.field-group').length,headers:document.querySelectorAll('#character-detail section.field-group>.lex-detail-section-title').length,growthHeaders:document.querySelectorAll('#character-detail .character-stat-growth>.lex-detail-section-title').length,curves:curves.map(card=>{const cr=card.getBoundingClientRect(),vr=card.querySelector('.lex-curve-variables').getBoundingClientRect(),inputs=[...card.querySelectorAll('.lex-curve-variable input')];return{title:card.dataset.curveTitle,heading:card.querySelector('h4')?.textContent,variables:card.querySelectorAll('.lex-curve-variable').length,variableRatio:vr.width/cr.width,variableHeightRatio:vr.height/cr.height,inputWidths:inputs.map(input=>input.getBoundingClientRect().width),headingFormula:card.querySelector('.lex-curve-heading-formula')?.textContent,footerFormula:card.querySelector('.lex-curve-formula')?.textContent||'',min:card.querySelector('.lex-curve-hover-minimum')?.textContent,max:card.querySelector('.lex-curve-hover-maximum')?.textContent,path:card.querySelector('.lex-curve-line')?.getAttribute('d')||'',axes:[...card.querySelectorAll('.lex-curve-axis')].map(node=>node.textContent),disabled:card.querySelectorAll('input:disabled').length}}),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,errors:window.__testErrors}})()""")
    bad_boxes = any(
        box["w"] < 48 or box["h"] < 72 or
        abs(box["w"] / box["h"] - (2 / 3)) > .02 or
        box["imageW"] < box["w"] - 5 or box["imageH"] < box["h"] - 5 or
        box["fit"] != "cover"
        for box in character["boxes"]
    )
    if (gf["selectedName"] != gf["names"][12]
            or int(gf["selectedId"].lstrip("#") or 0) != gf["expected"]
            or gf["repeatedId"]):
        raise AssertionError(gf)
    curve_titles = [curve["title"] for curve in character["curves"]]
    expected_variables = {"HP": 3, "XP": 2}
    bad_curves = (curve_titles != ["HP", "STR", "VIT", "MAG", "SPR", "SPD", "LUCK", "XP"] or
                  any(curve["variables"] != expected_variables.get(curve["title"], 4) or
                      curve["variableHeightRatio"] > .45 or min(curve["inputWidths"]) < 42 or
                      curve["heading"].strip() != curve["title"] or
                      not curve["footerFormula"] or not curve["path"] or
                      not curve["min"] or not curve["max"] or
                      curve["axes"][1:] != ["0", "1", "100"] or
                      not re.fullmatch(r"[\d,]+", curve["axes"][0] or "") or
                      int((curve["axes"][0] or "0").replace(",", "")) <= 0 or
                      int((curve["axes"][0] or "0").replace(",", ""))
                      > (9999 if curve["title"] == "HP" else
                         99000 if curve["title"] == "XP" else 255)
                      for curve in character["curves"]) or
                  any(curve["disabled"] for curve in character["curves"]))
    if character["count"] != 11 or character["images"] != 11 or character["selected"] != character["expected"] or character["panel"] != character["expected"] or not character["selectedName"].startswith(character["names"][8]) or character["selectedName"][-1] not in "♂♀" or int(character["selectedId"].lstrip("#") or 0) != character["expected"] or character["detailHead"] or character["missing"] or character["overflow"] > 0 or character["errors"] or character["collapsibles"] or character["headers"] != 0 or character["growthHeaders"] != 1 or bad_curves or bad_boxes:
        raise AssertionError(character)
    cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]'),input=card.querySelector('input:not(:disabled)');window.__curvePathBefore=card.querySelector('.lex-curve-line').getAttribute('d');input.value=String(Number(input.value.replaceAll(',',''))+1);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
    wait_eval(cdp, "document.querySelector('.ff8-character-curve[data-curve-title=STR]').querySelector('.lex-curve-line').getAttribute('d')!==window.__curvePathBefore", 5)
    character["liveCurve"] = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]');return{changed:card.querySelector('.lex-curve-line').getAttribute('d')!==window.__curvePathBefore,min:card.querySelector('.lex-curve-hover-minimum').textContent,max:card.querySelector('.lex-curve-hover-maximum').textContent,refs:card.querySelectorAll('.lex-reference-values').length}})()""")
    if not character["liveCurve"]["changed"] or not character["liveCurve"]["min"] or not character["liveCurve"]["max"] or not character["liveCurve"]["refs"]:
        raise AssertionError(character["liveCurve"])
    gender_reference = cdp.eval("""(()=>{document.querySelector('.ff8-portrait-selected-name .lex-reference-value')?.click();const gender=document.querySelector('.ff8-gender'),before=gender.getAttribute('aria-label');gender.click();const source=document.querySelector('.ff8-portrait-selected-name .lex-reference-value'),icon=source?.querySelector('.ff8-gender-symbol'),style=source?getComputedStyle(source):null;return{before,after:document.querySelector('.ff8-gender')?.getAttribute('aria-label'),text:source?.textContent||'',title:source?.title||'',icon:icon?.textContent||'',iconLabel:icon?.getAttribute('aria-label')||'',iconSize:icon?getComputedStyle(icon).fontSize:'',fontSize:style?.fontSize||'',border:style?.borderStyle||'',boxShadow:style?.boxShadow||'',errors:window.__testErrors}})()""")
    if gender_reference["text"] not in {"V♂", "V♀"} or gender_reference["icon"] not in {"♂", "♀"} or gender_reference["iconLabel"] not in {"Male", "Female"} or any(digit in gender_reference["text"] for digit in "01") or gender_reference["border"] != "none" or gender_reference["boxShadow"] != "none" or float(gender_reference["fontSize"].removesuffix("px")) > 16 or gender_reference["errors"]:
        raise AssertionError(gender_reference)
    character["genderReference"] = gender_reference
    capture(cdp, ROOT / "worklog" / "issues" / "rendered" / f"{output_stem}-characters.png")
    return {"size": [width, height], "gfs": gf, "characters": character}


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    rendered = ROOT / "worklog" / "issues" / "rendered"
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-portraits-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-portraits-project-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            port = free_port()
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            results = [
                snapshot(cdp, "github-41-ff8-portraits-1280x720", 1280, 720),
                snapshot(cdp, "github-41-ff8-portraits-1600x900", 1600, 900),
            ]
            print(json.dumps(results, ensure_ascii=True))
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
