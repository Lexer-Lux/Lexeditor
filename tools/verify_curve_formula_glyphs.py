"""Curve formula text must never overlap itself, on any character's curve.

The formula rides a guide path, so each glyph takes the local slope of that
path. Clamping the steepest ANGLE was not enough: what collides letters is how
fast the angle CHANGES, which is why the stairstep curves (MAG, STR) had
characters biting into the one before them. The framework now measures its own
glyph boxes and rebuilds the guide gentler until nothing touches; this check
measures the same boxes independently and fails on any real penetration.
"""

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

AUDIT = r"""
window.__glyphAudit = () => {
  const quadOf = (text, index, size) => {
    // Baseline start/end, never getExtentOfChar: that returns the axis-aligned
    // box of an already-rotated glyph, which would inflate every letter.
    const start = text.getStartPositionOfChar(index);
    const end = text.getEndPositionOfChar(index);
    const advanceX = end.x - start.x, advanceY = end.y - start.y;
    const advance = Math.hypot(advanceX, advanceY);
    if (!(advance > 0)) return null;
    const alongX = advanceX / advance, alongY = advanceY / advance;
    const upX = alongY, upY = -alongX;
    const corner = (along, up) => ({
      x: start.x + alongX * along + upX * up,
      y: start.y + alongY * along + upY * up,
    });
    const rise = size * 0.74, drop = size * 0.2;
    const bearing = Math.min(advance * 0.1, 0.9);
    return {angle: Math.atan2(advanceY, advanceX) * 180 / Math.PI,
      quad: [corner(bearing, rise), corner(advance - bearing, rise),
        corner(advance - bearing, -drop), corner(bearing, -drop)]};
  };
  const penetration = (a, b) => {
    let worst = Infinity;
    for (const source of [a, b]) {
      for (let index = 0; index < 4; index++) {
        const from = source[index], to = source[(index + 1) % 4];
        const length = Math.hypot(to.x - from.x, to.y - from.y) || 1;
        const axisX = -(to.y - from.y) / length, axisY = (to.x - from.x) / length;
        const span = quad => {
          let low = Infinity, high = -Infinity;
          for (const point of quad) {
            const value = point.x * axisX + point.y * axisY;
            if (value < low) low = value;
            if (value > high) high = value;
          }
          return [low, high];
        };
        const [aLow, aHigh] = span(a), [bLow, bHigh] = span(b);
        const depth = Math.min(aHigh, bHigh) - Math.max(aLow, bLow);
        if (depth <= 0) return 0;
        if (depth < worst) worst = depth;
      }
    }
    return worst;
  };
  return [...document.querySelectorAll('.lex-curve-editor')].map(card => {
    const text = card.querySelector('.lex-curve-path-formula');
    // The plot is 320x160 stretched with preserveAspectRatio="none", so both
    // the boxes and the angles are taken in SCREEN space - what the eye sees.
    const svg = card.querySelector('.lex-curve-svg').getBoundingClientRect();
    const zoom = {x: (svg.width || 320) / 320, y: (svg.height || 160) / 160};
    const characters = text ? (text.textContent || '') : '';
    const count = text ? text.getNumberOfChars() : 0;
    const size = parseFloat(getComputedStyle(text).fontSize) || 10;
    const glyphs = [];
    for (let index = 0; index < count; index++) {
      if (!characters[index] || characters[index] === ' ') continue;
      const glyph = quadOf(text, index, size);
      if (!glyph) continue;
      const quad = glyph.quad.map(point => ({x: point.x * zoom.x, y: point.y * zoom.y}));
      const along = {x: quad[1].x - quad[0].x, y: quad[1].y - quad[0].y};
      glyphs.push({quad, angle: Math.atan2(along.y, along.x) * 180 / Math.PI});
    }
    let worst = 0, worstAt = -1;
    for (let index = 1; index < glyphs.length; index++) {
      for (let other = index - 1; other >= Math.max(0, index - 3); other--) {
        const depth = penetration(glyphs[index].quad, glyphs[other].quad);
        if (depth > worst) { worst = depth; worstAt = index; }
      }
    }
    const angles = glyphs.map(glyph => glyph.angle);
    // How closely the text tracks the line it describes: for each glyph, the
    // screen slope of the drawn curve directly beneath it.
    const path = card.querySelector('.lex-curve-line');
    const lineAngleAt = x => {
      const total = path.getTotalLength();
      let low = 0, high = total;
      for (let pass = 0; pass < 24; pass++) {
        const mid = (low + high) / 2;
        if (path.getPointAtLength(mid).x * zoom.x < x) low = mid; else high = mid;
      }
      const step = Math.max(total / 200, 0.5);
      const before = path.getPointAtLength(Math.max(0, low - step));
      const after = path.getPointAtLength(Math.min(total, low + step));
      return Math.atan2((after.y - before.y) * zoom.y, (after.x - before.x) * zoom.x) * 180 / Math.PI;
    };
    const divergence = glyphs.map(glyph =>
      Math.abs(glyph.angle - lineAngleAt((glyph.quad[0].x + glyph.quad[1].x) / 2)));
    return {
      step: Number(card.dataset.formulaGuideStep ?? -1),
      bites: card.dataset.formulaGuideBites || '',
      title: card.dataset.curveTitle || card.querySelector('h4')?.textContent || '',
      formula: characters,
      glyphs: glyphs.length,
      worstPenetration: worst,
      worstAt,
      maxAngle: angles.length ? Math.max(...angles.map(Math.abs)) : 0,
      meanDivergence: divergence.length
        ? divergence.reduce((total, value) => total + value, 0) / divergence.length : 0,
      maxTurn: angles.slice(1).reduce((most, angle, index) =>
        Math.max(most, Math.abs(angle - angles[index])), 0),
    };
  });
};
"""


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    # LEX_GLYPH_BASELINE renders and reports WITHOUT asserting, so the same
    # measurement can be taken against a deliberately broken framework to show
    # what the search is worth.
    baseline = bool(os.environ.get("LEX_GLYPH_BASELINE"))
    output = ROOT / "worklog" / "issues" / "rendered" / (
        "curve-formula-glyphs-before.png" if baseline else "curve-formula-glyphs.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-glyphs-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-glyphs-project-", ignore_cleanup_errors=True)
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
                "width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('characters')")
            wait_eval(cdp, "state.tab==='characters'&&document.querySelectorAll('.ff8-character-curve').length>=8", 30)
            cdp.eval(AUDIT)

            tabs = int(cdp.eval("document.querySelectorAll('.ff8-portrait-tab').length"))
            report = []
            for index in range(tabs):
                cdp.eval(f"document.querySelectorAll('.ff8-portrait-tab')[{index}].click()")
                wait_eval(cdp, "document.querySelectorAll('.ff8-character-curve').length>=8", 20)
                # The search re-runs on the next frame with real boxes, so let
                # two frames pass before believing what is measured.
                cdp.eval("new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))", True)
                who = cdp.eval("document.querySelector('.ff8-portrait-selected-name')?.textContent||''")
                for card in cdp.eval("window.__glyphAudit()"):
                    card["character"] = who
                    card["tab"] = index
                    report.append(card)

            touching = [card for card in report if card["worstPenetration"] > 0.35]
            measured = [card for card in report if card["glyphs"] > 1]
            steps = [card["step"] for card in measured]
            sloped = [card for card in measured if card["maxAngle"] > 3]
            divergence = [card["meanDivergence"] for card in measured]
            if not baseline:
                assert len(measured) >= 8 * tabs * 0.9, (len(measured), tabs)
                assert not touching, json.dumps(touching[:6], indent=2)
                # The formula must still FOLLOW the graph. If every glyph came
                # out level the collisions would be gone for the wrong reason.
                assert len(sloped) >= len(measured) * 0.5, (len(sloped), len(measured))
                # The search must earn its keep: the steepest guide is not good
                # enough everywhere, and the flat fallback is never needed.
                assert max(steps) < 5, steps
                # And it must sit ON the line it describes, which is the whole
                # point of putting it there: the average glyph is within a few
                # degrees of the curve directly beneath it.
                assert max(divergence) < 30, [
                    (card["character"], card["title"], round(card["meanDivergence"], 1),
                     round(card["maxAngle"], 1), card["step"])
                    for card in sorted(measured, key=lambda card: -card["meanDivergence"])[:5]]

            # Shoot the character whose formulae came closest to colliding,
            # so before and after are the same worst case rather than whoever
            # happened to be selected last.
            worst = max(report, key=lambda card: card["worstPenetration"])
            cdp.eval(f"document.querySelectorAll('.ff8-portrait-tab')[{worst['tab']}].click()")
            wait_eval(cdp, "document.querySelectorAll('.ff8-character-curve').length>=8", 20)
            cdp.eval("new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))", True)
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({
                "characters": tabs, "curves": len(report), "touching": len(touching),
                "sloped": len(sloped), "steps": {str(value): steps.count(value) for value in sorted(set(steps))},
                "worstDivergence": round(max(divergence), 2),
                "meanDivergence": round(sum(divergence) / len(divergence), 2),
                "worst": {key: worst[key] for key in
                          ("character", "title", "worstPenetration", "maxAngle", "maxTurn")},
                "maxTurn": max(card["maxTurn"] for card in report),
                "screenshot": str(output),
            }, ensure_ascii=True))
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
