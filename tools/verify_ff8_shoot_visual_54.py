"""Hidden rendered Settings/Weapons check for FF8 fixed Shoot (GitHub #54)."""

from __future__ import annotations

import base64
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


def shot(cdp: Cdp, target: Path) -> None:
    image = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    target.write_bytes(base64.b64decode(image["data"]))


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered"
    output.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shoot-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shoot-project-", ignore_cleanup_errors=True)
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
            pages = wait_json(f"http://127.0.0.1:{port}/json/list")
            page = next(value for value in pages if value.get("type") == "page")
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
            wait_eval(cdp, "state.tab==='settings'&&!!document.querySelector('[aria-label=\"Command Menu Rework\"]')", 30)
            cdp.eval("document.querySelector('[aria-label=\"Monogamy\"]').click()")
            wait_eval(cdp, "!document.querySelector('[aria-label=\"Command Menu Rework\"]').disabled", 5)
            settings = cdp.eval("""(()=>{
              const shoot=document.querySelector('[aria-label="Command Menu Rework"]');
              shoot.click();
              const row=shoot.closest('.setting-row');
              return {enabled:shoot.checked,title:row?.querySelector('strong')?.textContent,
                description:row?.querySelector('p')?.textContent,visible:shoot.getBoundingClientRect().height>0,
                checkPosition:getComputedStyle(shoot).backgroundPosition,
                checkSize:getComputedStyle(shoot).backgroundSize,
                errors:window.__testErrors};
            })()""")
            assert settings["enabled"] and settings["visible"], settings
            assert settings["title"] == "COMMAND MENU REWORK", settings
            assert "fixed four-slot command layout" in settings["description"] and "Requires Monogamy" in settings["description"], settings
            assert settings["checkPosition"] == "50% 50%" and settings["checkSize"] == "17px 17px", settings
            assert not settings["errors"], settings
            shot(cdp, output / "github-54-ff8-irvine-shoot-settings.png")

            cdp.eval("navigate('weapons')")
            wait_eval(cdp, "state.tab==='weapons'&&!!document.querySelector('.weapon-detail')", 30)
            wait_eval(cdp, "[...document.querySelectorAll('.weapon-data-field .lex-detail-field-label')].some(n=>n.textContent.includes('Shots per ATB'))", 30)
            weapon = cdp.eval("""(()=>{
              const field=[...document.querySelectorAll('.weapon-data-field')]
                .find(node=>node.querySelector('.lex-detail-field-label')?.textContent.includes('Shots per ATB'));
              const input=field?.querySelector('.lex-detail-field-control input[inputmode="numeric"]');
              const detail=document.querySelector('.weapon-detail');
              return {label:field?.querySelector('.lex-detail-field-label')?.textContent.trim(),value:input?.value,
                min:input?.dataset.min,max:input?.dataset.max,visible:!!field&&field.getBoundingClientRect().height>0,
                fits:detail.scrollHeight<=detail.clientHeight+1,overflowY:getComputedStyle(detail).overflowY,
                errors:window.__testErrors};
            })()""")
            assert weapon["label"].startswith("Shots per ATB"), weapon
            assert tuple(weapon.get(key) for key in ("value", "min", "max")) == ("1", "1", "10"), weapon
            assert weapon["visible"] and weapon["fits"] and weapon["overflowY"] in {"hidden", "visible"}, weapon
            assert not weapon["errors"], weapon
            shot(cdp, output / "github-54-ff8-shots-per-atb.png")
            print({"settings": settings, "weapon": weapon})
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
