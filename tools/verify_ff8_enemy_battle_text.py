"""Corpus identity, isolated mutation, and validation checks for battle text."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import enemy_battle_text, paths  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def require_error(action, fragment: str) -> None:
    try:
        action()
    except ValueError as error:
        assert fragment.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"Expected an error containing {fragment!r}")


def editable_glyph(text: str) -> str | None:
    """Return one ASCII letter which is not inside an FF8 control token."""
    inside_token = False
    for character in text:
        if character == "{":
            inside_token = True
        elif character == "}":
            inside_token = False
        elif not inside_token and character.isascii() and character.isalpha():
            return character
    return None


def api(url: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = Request(url + path, data=data,
                      headers={"Content-Type": "application/json"} if data else {})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> int:
    files = sorted((paths.BASELINE_ROOT / "battle").glob("c0m*.dat"))
    assert len(files) == 200, len(files)
    available = []
    total_lines = 0

    # Every supported baseline DAT must survive a full decode/rebuild exactly.
    for path in files:
        raw = path.read_bytes()
        document = enemy_battle_text.read(raw)
        rebuilt, changed = enemy_battle_text.rebuild(
            raw, [line["text"] for line in document["lines"]])
        assert changed == 0 and rebuilt == raw, path
        if not document["available"]:
            continue
        available.append(path)
        total_lines += len(document["lines"])

    assert available and total_lines > 0
    sample_path = next(path for path in available
                       if enemy_battle_text.read(path.read_bytes())["lines"])
    baseline = sample_path.read_bytes()
    document = enemy_battle_text.read(baseline)
    line = document["lines"][0]

    # Replace one one-byte glyph with another.  Only that payload byte may
    # change; the terminator, offsets, AI, and later DAT sections stay exact.
    replacement = "A" if line["text"] != "A" else "B"
    same_size_source = editable_glyph(line["text"])
    if same_size_source:
        replacement = line["text"].replace(
            same_size_source, "A" if same_size_source != "A" else "B", 1)
    else:
        # Find another line with a printable one-byte glyph when line zero is
        # only made of controls on an unusual corpus.
        for candidate in document["lines"]:
            source = editable_glyph(candidate["text"])
            if source:
                line = candidate
                replacement = candidate["text"].replace(
                    source, "A" if source != "A" else "B", 1)
                break
        else:
            raise AssertionError("No one-byte battle-text glyph was found")
    mutated, changed = enemy_battle_text.apply_edits(
        baseline, [{"id": line["id"], "text": replacement}])
    assert changed == 1 and len(mutated) == len(baseline)
    before_layout = enemy_battle_text._layout(baseline)
    after_layout = enemy_battle_text._layout(mutated)
    entry = before_layout["entries"][line["id"]]
    differences = [index for index, pair in enumerate(zip(baseline, mutated))
                   if pair[0] != pair[1]]
    assert len(differences) == 1, differences
    assert all(entry["absolute_offset"] <= index <
               entry["absolute_offset"] + len(entry["payload"])
               for index in differences)
    assert after_layout["entries"][line["id"]]["text"] == replacement

    # A larger edit changes only section 8 plus later top-level pointers.  The
    # original AI prefix and every later section payload remain byte-identical.
    longer = replacement + " TEST"
    grown, changed = enemy_battle_text.apply_edits(
        baseline, [{"id": line["id"], "text": longer}])
    assert changed == 1
    grown_layout = enemy_battle_text._layout(grown)
    old_prefix = before_layout["section"][:before_layout["offset_start"]]
    new_prefix = grown_layout["section"][:grown_layout["offset_start"]]
    # Header byte 12 can change only if line-count table size changes.  Existing
    # line editing keeps it fixed, so the complete prefix is exact.
    assert new_prefix == old_prefix
    assert baseline[before_layout["section_end"]:] == grown[grown_layout["section_end"]:]
    assert grown_layout["entries"][line["id"]]["text"] == longer

    require_error(
        lambda: enemy_battle_text.apply_edits(baseline, [
            {"id": line["id"], "text": "first"},
            {"id": line["id"], "text": "second"},
        ]),
        "duplicate",
    )
    require_error(
        lambda: enemy_battle_text.apply_edits(
            baseline, [{"id": len(document["lines"]), "text": "bad"}]),
        "does not exist",
    )
    require_error(
        lambda: enemy_battle_text.apply_edits(
            baseline, [{"id": line["id"], "text": "snowman ☃"}]),
        "not available",
    )
    require_error(
        lambda: enemy_battle_text.apply_edits(
            baseline, [{"id": line["id"], "text": "Z" * 100}]),
        "limit is 100",
    )

    malformed = bytearray(baseline)
    malformed[before_layout["section_start"] + 12:
              before_layout["section_start"] + 16] = (before_layout["offset_start"] + 2).to_bytes(4, "little")
    require_error(lambda: enemy_battle_text.read(bytes(malformed)), "four-byte aligned")

    # The dedicated endpoint writes a selected-mod override, and the rendered
    # Enemies subtab exposes each existing line as a provenance-aware textarea.
    output = ROOT / "worklog" / "issues" / "rendered" / "goal-ff8-enemy-battle-text.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    project = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-battle-text-project-", ignore_cleanup_errors=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-battle-text-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            payload = api(session.url, "/api/enemy-battle-text?id=3&dataset=current")
            assert len(payload["rows"]) == 1 and len(payload["rows"][0]["lines"]) == 4
            original = payload["rows"][0]["lines"][0]["text"]
            saved = api(session.url, "/api/enemy-battle-text/save", {
                "edits": [{"id": 3, "line": 0, "text": original + " TEST"}],
            })
            assert saved["saved"] == 1
            current = api(session.url, "/api/enemy-battle-text?id=3&dataset=current")
            assert current["rows"][0]["lines"][0]["text"] == original + " TEST"
            written = Path(project.name) / "direct" / "battle" / "c0m003.dat"
            assert written.is_file() and enemy_battle_text.read(
                written.read_bytes())["lines"][0]["text"] == original + " TEST"

            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
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
                "width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 120)
            cdp.eval("state.selected.enemies=3;state.enemyPanelTab='battleText';navigate('enemies');renderEnemies()")
            wait_eval(cdp, "document.querySelectorAll('.enemy-battle-text-line textarea').length===4", 45)
            rendered = cdp.eval("({tabs:[...document.querySelectorAll('.enemy-tabbed-column .lex-subtab-button')].map(node=>node.textContent.trim()),values:[...document.querySelectorAll('.enemy-battle-text-line textarea')].map(node=>node.value),refs:document.querySelectorAll('.enemy-battle-text-line .lex-source-control').length,status:state.status})")
            assert any(value.startswith("Battle Text") for value in rendered["tabs"]), rendered
            assert len(rendered["values"]) == 4 and rendered["values"][0] == original + " TEST"
            assert rendered["refs"] == 4
            cdp.eval("const input=document.querySelector('.enemy-battle-text-line textarea');input.value+='!';input.dispatchEvent(new Event('input',{bubbles:true}))")
            assert cdp.eval("dirtyCount()") > 0
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True})
            output.write_bytes(base64.b64decode(shot["data"]))
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()

    print({
        "files": len(files),
        "supported": len(available),
        "lines": total_lines,
        "identity": True,
        "sameSizeChangedBytes": differences,
        "grownDelta": len(grown) - len(baseline),
        "sample": sample_path.name,
        "apiAndRendered": True,
        "screenshot": str(output),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
