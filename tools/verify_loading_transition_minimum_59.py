"""Rendered timing contract for the shared loading-screen minimum (GitHub #59)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-load-minimum-edge-", ignore_cleanup_errors=True)
    fixture = tempfile.TemporaryDirectory(prefix="lexeditor-load-minimum-page-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    try:
        page_path = Path(fixture.name) / "plugin.html"
        page_path.write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="{(ROOT / 'ui' / 'framework.css').as_uri()}"></head>
<body><main>Loaded editor</main>
<script>
window.__testSettings={{loadingTransitionMinimumSeconds:.75}};
window.pywebview={{api:{{
  transition_snapshot:async()=>({{html:""}}),
  lexeditor_settings:async()=>structuredClone(window.__testSettings)
}}}};
</script>
<script src="{(ROOT / 'ui' / 'framework.js').as_uri()}"></script>
<script>
window.__finishInvokedAt=Date.now();
LexeditorUI.finishPluginLoading().then(()=>{{window.__finishedAt=Date.now();}});
</script></body></html>""", encoding="utf-8")
        port = free_port()
        browser = subprocess.Popen([
            str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--remote-allow-origins=*", "--use-angle=swiftshader",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           creationflags=subprocess.CREATE_NO_WINDOW)
        target = next(row for row in wait_json(
            f"http://127.0.0.1:{port}/json/list") if row.get("type") == "page")
        cdp = Cdp(target["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        started = int(time.time() * 1000)
        query = urlencode({
            "lexTransition": "load", "lexLoadStarted": started,
            "lexQuote": "Timing test",
        })
        cdp.call("Page.navigate", {"url": f"{page_path.as_uri()}?{query}"})
        wait_eval(cdp, "!!window.__finishInvokedAt", 10)
        time.sleep(.2)
        visible = cdp.eval("!!document.querySelector('.lex-plugin-loading-screen:not(.closing)')")
        assert visible, "the loading screen closed before the configured minimum"
        wait_eval(cdp, "!!window.__finishedAt", 10)
        result = cdp.eval("""(()=>({
          elapsed:window.__finishedAt-Number(new URLSearchParams(location.search).get('lexOriginalStart')||0),
          finished:window.__finishedAt,
          url:location.href,
          screenClosing:!!document.querySelector('.lex-plugin-loading-screen.closing')
        }))()""")
        elapsed = result["finished"] - started
        assert 700 <= elapsed <= 2500, {**result, "elapsed": elapsed}
        assert "lexLoadStarted" not in result["url"], result
        print({"elapsedMs": elapsed, "heldAt200Ms": visible, "urlCleaned": True})
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
        profile.cleanup()
        fixture.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
