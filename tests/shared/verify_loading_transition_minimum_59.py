"""Rendered timing contract for the shared loading-screen minimum (GitHub #59)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[2]

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
<body><div id="lexeditor-shell"></div><main>Loaded editor</main>
<script>
window.__testSettings={{loadingTransitionMinimumSeconds:.75}};
window.__loadingStartedAt=Date.now();
const loadingUrl=new URL(location.href);
loadingUrl.searchParams.set('lexLoadStarted',String(window.__loadingStartedAt));
history.replaceState(history.state,'',loadingUrl);
window.pywebview={{api:{{
  transition_snapshot:async()=>({{html:""}}),
  lexeditor_settings:async()=>structuredClone(window.__testSettings)
}}}};
</script>
<script src="{(ROOT / 'ui' / 'framework.js').as_uri()}"></script>
<script>
window.__finishInvokedAt=Date.now();
const loadingScreen=document.querySelector('.lex-plugin-loading-screen');
window.__initiallyVisible=!!loadingScreen&&!loadingScreen.classList.contains('closing');
new MutationObserver(()=>{{
  if(loadingScreen.classList.contains('closing')&&!window.__closedAt)window.__closedAt=Date.now();
}}).observe(loadingScreen,{{attributes:true,attributeFilter:['class']}});
setTimeout(()=>{{window.__earlyObservation={{elapsed:Date.now()-window.__loadingStartedAt,
  visible:!!document.querySelector('.lex-plugin-loading-screen:not(.closing)')}};}},200);
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
        query = urlencode({
            "lexTransition": "load",
            "lexQuote": "Timing test",
        })
        cdp.call("Page.navigate", {"url": f"{page_path.as_uri()}?{query}"})
        wait_eval(cdp, "!!window.__finishInvokedAt", 10)
        wait_eval(cdp, "!!window.__finishedAt", 10)
        result = cdp.eval("""(()=>({
          started:window.__loadingStartedAt,
          initiallyVisible:window.__initiallyVisible,
          early:window.__earlyObservation,
          closed:window.__closedAt,
          finished:window.__finishedAt,
          url:location.href,
          screenClosing:!!document.querySelector('.lex-plugin-loading-screen.closing')
        }))()""")
        elapsed = result["finished"] - result["started"]
        assert result["initiallyVisible"], result
        assert result["closed"] - result["started"] >= 700, result
        assert elapsed >= 700, {**result, "elapsed": elapsed}
        # CI may deliver a timer or CDP response after the minimum has passed.
        # Assert the early hold only when the observation was actually early;
        # the mandatory closing timestamp verifies the minimum in every run.
        if result["early"]["elapsed"] < 700:
            assert result["early"]["visible"], result
        assert "lexLoadStarted" not in result["url"], result
        print({"elapsedMs": elapsed, "earlyObservation": result["early"], "urlCleaned": True})
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
