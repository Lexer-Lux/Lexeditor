"""Rendered cross-plugin command-row geometry contract for issue 27."""

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
from games.rdr2.plugin import Rdr2Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def inspect(cdp: Cdp, plugin: str, url: str) -> dict:
    navigation = cdp.call("Page.navigate", {"url": url})
    if navigation.get("errorText"):
        raise AssertionError({plugin: navigation, "url": url})
    try:
        wait_eval(cdp, "!!document.querySelector('.lex-shell-command-row')", 30)
    except AssertionError as error:
        diagnostic = cdp.eval("({url:location.href,state:document.readyState,title:document.title,body:document.body?.innerText?.slice(0,300),headers:[...document.querySelectorAll('header')].map(x=>({class:x.className,children:[...x.children].map(y=>y.className)}))})")
        raise AssertionError({plugin: diagnostic, "url": url}) from error
    result = cdp.eval("""(()=>{
      const row=document.querySelector('.lex-shell-command-row');
      const brand=document.querySelector('.lex-brand-button h1');
      const box=row.getBoundingClientRect();
      const style=getComputedStyle(row);
      const brandStyle=getComputedStyle(brand);
      return {height:box.height,boxSizing:style.boxSizing,
        brandMarginTop:brandStyle.marginTop,brandMarginBottom:brandStyle.marginBottom,
        overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth};
    })()""")
    if result != {
        "height": 81,
        "boxSizing": "border-box",
        "brandMarginTop": "0px",
        "brandMarginBottom": "0px",
        "overflow": 0,
    }:
        raise AssertionError({plugin: result})
    output = ROOT / "worklog" / "issues" / "rendered" / f"github-27-{plugin}-compact-command-row.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    output.write_bytes(base64.b64decode(screenshot["data"]))
    return result


def render(plugin: str, session) -> dict:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix=f"lexeditor-{plugin}-command-row-edge-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
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
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        })
        return inspect(cdp, plugin, session.url)
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-command-row-ff8-", ignore_cleanup_errors=True) as project:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project}) as session:
            ff8 = render("ff8", session)
    with Rdr2Session() as session:
        rdr2 = render("rdr2", session)
    if ff8["height"] != rdr2["height"]:
        raise AssertionError({"ff8": ff8, "rdr2": rdr2})
    print({"ff8": ff8, "rdr2": rdr2})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
