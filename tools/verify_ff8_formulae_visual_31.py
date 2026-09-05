"""Hidden rendered check for the FF8 Formulae page (GitHub #31)."""

from __future__ import annotations

import base64
import json
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


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-31-ff8-formulae.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-formulae-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-formulae-project-", ignore_cleanup_errors=True)
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
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
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('formulae')")
            wait_eval(cdp, "state.tab==='formulae'&&document.querySelectorAll('.formula-card').length===6&&document.querySelectorAll('.formula-rework').length===4", 30)
            result = cdp.eval("""(() => ({
              cards:[...document.querySelectorAll('.formula-card>h2')].map(node=>node.textContent.trim()),
              groups:[...document.querySelectorAll('.formula-subheading')].map(node=>node.textContent.trim()),
              expressions:[...document.querySelectorAll('.formula-expression')].map(node=>node.textContent.trim()),
              editableTerms:document.querySelectorAll('.formula-terms input').length,
              termsPerCard:[...document.querySelectorAll('.formula-card:not(.formula-rework)')].map(card=>card.querySelectorAll('.formula-terms input').length),
              termValues:[...document.querySelectorAll('.formula-terms input')].map(input=>({label:input.getAttribute('aria-label'),value:input.value,checked:input.checked,type:input.type})),
              previewInputs:document.querySelectorAll('.formula-preview-inputs input').length,
              reworkControl:(()=>{const input=document.querySelector('[aria-label="Formulae Rework"]');return input?{checked:input.checked,inside:!!input.closest('.formula-rework-master')}:null})(),
              errors:window.__testErrors,
            }))()""")
            geometry_script = """(() => {
              const view=document.querySelector('.formulae-view');
              const cards=[...document.querySelectorAll('.formula-card')];
              const box=view.getBoundingClientRect();
              const right=Math.max(...cards.map(card=>card.getBoundingClientRect().right));
              return {viewport:innerWidth,left:box.left,right:box.right,
                contentRight:box.left+view.clientWidth,cardRight:right,
                overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};
            })()"""
            geometry_1600 = cdp.eval(geometry_script)
            assert result["cards"] == ["PHYSICAL DAMAGE", "PHYSICAL ACCURACY", "MELEE DAMAGE (REWORK)", "MAGIC DAMAGE (REWORK)", "STATUS INFLICTION (REWORK)", "SPELL HEALING (REWORK)"], result
            assert result["reworkControl"] == {"checked": False, "inside": True}, result
            assert cdp.eval("document.querySelector('[aria-label=\"Formulae Rework\"]').disabled") is True
            assert result["groups"].count("FORMULA") == 2, result
            assert "EDITABLE FORMULA TERMS" in result["groups"], result
            assert any("DAMAGE" in value for value in result["expressions"]), result
            assert any("HIT CHANCE" in value for value in result["expressions"]), result
            joined_expressions = "\n".join(result["expressions"])
            for text in ("0x491AD0", "0x48F9F0", "0x493280"):
                assert text in joined_expressions, (text, result)
            assert "Not yet transcribed" not in joined_expressions, result
            assert result["termsPerCard"] and all(count >= 2 for count in result["termsPerCard"]), result
            assert result["previewInputs"] > 1, result
            assert not result["errors"], result
            assert abs(geometry_1600["contentRight"] - geometry_1600["cardRight"]) <= 2, geometry_1600
            assert geometry_1600["overflow"] <= 0, geometry_1600
            assert cdp.eval("state.data.settings.formulaeRework") is False
            edit = cdp.eval("""(() => {
              const weapon=state.data.weapons.rows.find(row=>Number(row.id)===Number(state.formula.weaponId));
              const field=weapon.fields.find(value=>value.field==='attack_power');
              const input=document.querySelector('.formula-card:not(.formula-rework) .formula-terms input');
              const output=document.querySelector('.formula-card:not(.formula-rework) .formula-output');
              const before={value:Number(field.value),output:output.textContent};
              const next=before.value<255?before.value+1:before.value-1;
              input.value=String(next);
              input.dispatchEvent(new Event('input',{bubbles:true}));
              return {before,next};
            })()""")
            wait_eval(cdp, f"dirtyCount()>0&&Number(state.data.weapons.rows.find(row=>Number(row.id)===Number(state.formula.weaponId)).fields.find(value=>value.field==='attack_power').value)==={edit['next']}", 10)
            wait_eval(cdp, f"document.querySelector('.formula-card:not(.formula-rework) .formula-output').textContent!=={json.dumps(edit['before']['output'])}", 10)
            cdp.eval("saveAll()", True)
            wait_eval(cdp, "dirtyCount()===0", 20)
            cdp.eval("reloadEditable().then(()=>navigate('formulae'))", True)
            wait_eval(cdp, "state.tab==='formulae'&&state.data.settings.formulaeRework===false&&document.querySelectorAll('.formula-card').length===6&&document.querySelectorAll('.formula-rework').length===4", 20)
            saved_value = cdp.eval("state.data.weapons.rows.find(row=>Number(row.id)===Number(state.formula.weaponId)).fields.find(value=>value.field==='attack_power').value")
            assert int(saved_value) == int(edit["next"]), (saved_value, edit)
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            wait_eval(cdp, "innerWidth===1280", 10)
            geometry_1280 = cdp.eval(geometry_script)
            assert abs(geometry_1280["contentRight"] - geometry_1280["cardRight"]) <= 2, geometry_1280
            assert geometry_1280["overflow"] <= 0, geometry_1280
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"content": result, "geometry1600": geometry_1600,
                              "geometry1280": geometry_1280}, ensure_ascii=True))
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
