"""API and hidden-Edge acceptance for FF8 Data Map cleanup."""

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

from games.ff8.formats import data_map_rows  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    rows = data_map_rows()["rows"]
    filenames = [row["filename"] for row in rows]
    assert "Models and textures" not in filenames
    assert "Music and audio" not in filenames
    for required in ("kernel.bin", "menu/price.bin", "battle/c0m*.dat", "field.fs"):
        assert required in filenames, required

    source = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    assert ".lex-data-map-table code,.lex-data-map-link{font-family:var(--lex-font)" in source

    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-47-ff8-datamap.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-datamap-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-datamap-project-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
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
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('datamap')")
            wait_eval(cdp, "state.tab==='datamap'&&!!document.querySelector('.lex-data-map-table')", 30)
            wait_eval(cdp, "document.fonts.check('16px \\\"FF8 Menu\\\"')", 30)
            result = cdp.eval("""(()=>{
              const cell=document.querySelector('.lex-data-map-table .lex-column-list-cell:first-child');
              const filename=cell?.querySelector('code,.lex-data-map-link');
              const text=document.querySelector('.lex-data-map-table')?.textContent||'';
              const pager=document.querySelector('.lex-data-map-view>.lex-pager');
              const statuses=[...document.querySelectorAll('.lex-data-map-table .lex-integration-status')];
              return {rows:document.querySelectorAll('.lex-data-map-table .lex-column-list-row').length,
                font:filename?getComputedStyle(filename).fontFamily:'',
                removed:!text.includes('Models and textures')&&!text.includes('Music and audio'),
                bottomSearch:!!pager?.querySelector('.lex-pager-left .lex-pager-search input[type=search]'),
                bottomStatus:!!pager?.querySelector('.lex-pager-right select[aria-label="Filter files by integration status"]'),
                obsoleteToolbarControls:document.querySelectorAll('#toolbar input[type=search],#toolbar select').length,
                statusIcons:statuses.length,
                statusLabels:statuses.map(node=>node.getAttribute('aria-label')),
                statusText:statuses.map(node=>node.textContent.trim()),errors:window.__testErrors};
            })()""")
            assert result["rows"] == len(rows), result
            assert "FF8 Menu" in result["font"] and result["removed"], result
            assert result["bottomSearch"] and result["bottomStatus"], result
            assert result["obsoleteToolbarControls"] == 0, result
            assert result["statusIcons"] == len(rows), result
            assert all(label in {"Integrated", "Partial", "Not integrated"}
                       for label in result["statusLabels"]), result
            assert all(text not in {"Integrated", "Partial", "Not integrated"}
                       for text in result["statusText"]), result
            assert not result["errors"], result
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            print({"rows": len(rows), "font": result["font"], "screenshot": str(output)})
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
