"""Rendered live-volume contract for game-theme sounds (GitHub #23)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-sound-volume-edge-", ignore_cleanup_errors=True)
    fixture = tempfile.TemporaryDirectory(prefix="lexeditor-sound-volume-page-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    try:
        page_path = Path(fixture.name) / "sound.html"
        page_path.write_text(f"""<!doctype html><html><body><header id="shell"></header><main></main>
<script>
window.__audios=[];
window.Audio=class {{
  constructor(url){{this.url=url;this.volume=1;this.paused=false;window.__audios.push(this)}}
  addEventListener(){{}}
  play(){{return Promise.resolve()}}
  pause(){{this.paused=true}}
}};
window.__settings={{developerMode:false,lexerMode:false,soundEnabled:true,soundVolumePercent:1,viewPreferences:{{}}}};
window.pywebview={{api:{{lexeditor_settings:async()=>structuredClone(window.__settings),window_state:async()=>({{maximized:false}})}}}};
</script>
<script src="{(ROOT / 'ui' / 'framework.js').as_uri()}"></script>
<script>
LexeditorUI.mountShell({{host:'#shell',plugin:{{id:'test',name:'Test'}},tabs:[{{id:'one',label:'One'}}],activeTab:()=> 'one',navigate:()=>{{}},dirtyCount:()=>0}});
LexeditorUI.configureThemeSounds({{rows:[{{slot:'move',available:true,url:'memory://move'}}]}});
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
        cdp.call("Page.navigate", {"url": page_path.as_uri()})
        wait_eval(cdp, "LexeditorUI.sharedSettings()?.soundVolumePercent===1", 10)
        one = cdp.eval("""(()=>({played:LexeditorUI.playThemeSound('move'),volume:window.__audios.at(-1)?.volume,count:window.__audios.length}))()""")
        assert one == {"played": True, "volume": .0001, "count": 1}, one
        zero = cdp.eval("""(()=>{window.__settings.soundVolumePercent=0;window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:structuredClone(window.__settings)}));return{played:LexeditorUI.playThemeSound('move'),count:window.__audios.length,priorPaused:window.__audios[0].paused,live:LexeditorUI.sharedSettings().soundVolumePercent}})()""")
        assert zero == {"played": False, "count": 1, "priorPaused": True, "live": 0}, zero
        print({"onePercentGain": one["volume"], "zeroPlayed": zero["played"], "updatedWithoutRestart": True})
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
