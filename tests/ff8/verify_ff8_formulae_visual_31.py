"""Hidden rendered check for the FF8 Formulae tweaks subtab (GitHub #31)."""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from plugins.ff8 import paths  # noqa: E402
from plugins.ff8.plugin import FF8Session  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    # The Tweaks list renders real settings data. Without the extracted FF8
    # baseline the editor can boot, but those payloads are null and a browser
    # TypeError would misreport "no game data" as a UI regression.
    required = (
        paths.BASELINE_ROOT / "main" / "kernel.bin",
        paths.BASELINE_ROOT / "menu" / "mitem.bin",
    )
    missing = next((path for path in required if not path.is_file()), None)
    if missing:
        raise FileNotFoundError(f"Installed FF8 extracted baseline is missing: {missing}")

    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = DEV_CACHE / "rendered" / "github-31-ff8-formulae.png"
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
            cdp.eval("navigate('settings')")
            wait_eval(cdp, "state.tab==='settings'&&document.querySelectorAll('.lex-subtab-button').length===3", 30)
            result = cdp.eval("""(() => ({
              subtabs:[...document.querySelectorAll('.lex-subtab-button')].map(button=>({
                label:button.querySelector('.lex-tab-label-text').textContent.trim(),
                disabled:button.disabled,active:button.classList.contains('active')})),
              tweak:(()=>{const input=document.querySelector('[aria-label="Formulae Rework"]');
                return input?{checked:input.checked,disabled:input.disabled,
                  row:!!input.closest('.lex-detail-panel')}:null})(),
              formulaCards:document.querySelectorAll('[data-formula-id]').length,
              settingsTab:state.settingsTab,
              available:state.data.settings.formulaeReworkAvailable,
              rework:state.data.settings.formulaeRework,
              errors:window.__testErrors,
            }))()""")
            # The live backend still lists incomplete rows, so the owning
            # toggle stays unavailable and its subtab stays locked. The page
            # content itself is covered stubbed (no game) by the scroll check.
            labels = [tab["label"] for tab in result["subtabs"]]
            assert labels == ["Gameplay", "Formulae", "FFNx"], result
            formulae_tab = next(tab for tab in result["subtabs"] if tab["label"] == "Formulae")
            assert formulae_tab["disabled"] is True, result
            assert result["tweak"] == {"checked": False, "disabled": True, "row": True}, result
            assert result["formulaCards"] == 0, result
            assert result["available"] is False and result["rework"] is False, result
            assert not result["errors"], result
            # An old formulae link must land on the Gameplay list that owns
            # the toggle, never on a locked subtab.
            cdp.eval("navigate('formulae')")
            wait_eval(cdp, "state.tab==='settings'&&state.settingsTab==='gameplay'", 30)
            fallback = cdp.eval("""(() => ({
              formulaCards:document.querySelectorAll('[data-formula-id]').length,
              tweak:!!document.querySelector('[aria-label="Formulae Rework"]'),
            }))()""")
            assert fallback == {"formulaCards": 0, "tweak": True}, fallback
            geometry = cdp.eval("""(() => ({
              overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth}))()""")
            assert geometry["overflow"] <= 0, geometry
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"tweaks": result, "fallback": fallback,
                              "geometry": geometry}, ensure_ascii=True))
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
