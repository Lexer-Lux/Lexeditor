"""Rendered and source contract for game-themed semantic UI sounds (#72)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff7.plugin import FF7Session  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402
from service_session import request_json  # noqa: E402
from theme_sounds import SOUND_SLOTS  # noqa: E402


def decode_session(session_type, expected: dict[str, int | None]) -> dict:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-theme-sfx-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    try:
        with session_type() as session:
            dashboard = request_json(session.url + "api/dashboard")
            rows = {row["slot"]: row for row in dashboard["themeSounds"]["rows"]}
            assert tuple(rows) == SOUND_SLOTS, rows
            assert {slot: rows[slot]["sourceId"] for slot in rows} == expected, rows
            port = free_port()
            hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--autoplay-policy=no-user-gesture-required",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(row for row in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if row.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "document.readyState==='complete'", 20)
            available = [slot for slot, row in rows.items() if row["available"]]
            result = cdp.eval("""
              Promise.all(SLOTS.map(async slot=>{
                const response=await fetch(`/assets/theme-sfx/${slot}.wav`);
                const bytes=await response.arrayBuffer();
                const context=new AudioContext();
                try {
                  const decoded=await context.decodeAudioData(bytes.slice(0));
                  return {slot,ok:true,status:response.status,duration:decoded.duration,
                    channels:decoded.numberOfChannels,sampleRate:decoded.sampleRate};
                } catch(error) {
                  return {slot,ok:false,status:response.status,error:String(error)};
                } finally { await context.close(); }
              }))
            """.replace("SLOTS", repr(available).replace("'", '"')), await_promise=True)
            assert result and all(row["ok"] and row["status"] == 200 and row["duration"] > 0
                                  for row in result), result
            return {"available": available, "decoded": result}
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    settings = (ROOT / "settings_manager.py").read_text(encoding="utf-8")
    manual = Path(r"C:\RDR2Mod\codex\lexeditor.md").read_text(encoding="utf-8")
    for slot in SOUND_SLOTS:
        assert f'"{slot}"' in framework, slot
        assert f"`{slot}`" in manual, slot
    assert '"soundEnabled": True' in settings
    assert "private local cache" in manual
    ff8 = decode_session(FF8Session, {
        "confirm": 1, "back": 9, "move": 1, "launch": 29, "exit": 9, "save": 37,
    })
    ff7 = decode_session(FF7Session, {
        "confirm": 1, "back": 4, "move": 1, "launch": None, "exit": 4, "save": 2,
    })
    assert ff8["available"] == list(SOUND_SLOTS), ff8
    assert ff7["available"] == ["confirm", "back", "move", "exit", "save"], ff7
    print({"ff8": ff8, "ff7": ff7})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
