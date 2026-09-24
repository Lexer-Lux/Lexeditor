"""Curve viewBox must settle instead of ratcheting (issue 527).

draw() sizes the viewBox from the svg's own box. When an ancestor chain is
content-driven, the box height falls back to the intrinsic ratio plus an
offset, so every adopted viewBox grows the next box and the self-observation
re-fires without bound. These tests model that fallback deterministically by
stubbing getBoundingClientRect; the first test fails on the unguarded code.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401  (pytest fixture)


def mount(page, count=2):
    framework(page)
    page.evaluate("""(count)=>{
      const U = LexeditorUI;
      const main = document.querySelector('main');
      for (let i = 0; i < count; i++) {
        main.append(U.curveEditor({title: 'Growth ' + i,
          domain: {min: 1, max: 100}, range: {min: 0, max: 255},
          evaluate: x => x * 2, formula: U.mathFormula('Value = Level * A'),
          variables: [{label: 'A', control: U.el('input', {type: 'number', value: 1})}]}));
      }
    }""", count)
    page.wait_for_timeout(200)


def viewbox_heights(page):
    return page.evaluate(
        "()=>[...document.querySelectorAll('.lex-curve-svg')]"
        ".map(n=>Number(n.getAttribute('viewBox').split(' ')[3]))")


def refresh_all(page):
    page.evaluate(
        "()=>{for (const n of document.querySelectorAll('.lex-curve-editor'))"
        " n.refreshCurve();}")


def test_curve_viewbox_settles_when_box_follows_viewbox(page):
    mount(page)
    # Content-driven fallback: fixed width, height re-derived from the live
    # viewBox plus a constant offset every pass, as the issue describes.
    page.evaluate("""()=>{
      window.__w = document.querySelector('.lex-curve-svg').getBoundingClientRect().width;
      for (const svg of document.querySelectorAll('.lex-curve-svg')) {
        svg.getBoundingClientRect = () => {
          const vb = Number(svg.getAttribute('viewBox').split(' ')[3]);
          const height = window.__w * vb / 320 + 40;
          return {x: 0, y: 0, left: 0, top: 0, right: window.__w,
            bottom: height, width: window.__w, height};
        };
      }
    }""")
    for _ in range(60):
        refresh_all(page)
    page.wait_for_timeout(300)
    heights = viewbox_heights(page)
    assert len(heights) == 2
    assert all(h < 320 for h in heights), heights


def test_curve_viewbox_tracks_external_height_changes(page):
    mount(page, count=1)
    page.evaluate("""()=>{
      const svg = document.querySelector('.lex-curve-svg');
      window.__w = svg.getBoundingClientRect().width;
      window.__h = svg.getBoundingClientRect().height;
      svg.getBoundingClientRect = () => ({x: 0, y: 0, left: 0, top: 0,
        right: window.__w, bottom: window.__h,
        width: window.__w, height: window.__h});
    }""")
    steps = 10
    for i in range(steps):
        page.evaluate(f"()=>window.__h = {300 + i * 15}")
        refresh_all(page)
    page.wait_for_timeout(200)
    width = page.evaluate("()=>window.__w")
    expected = 320 * (300 + (steps - 1) * 15) / width
    # At most one pass of lag: a move seen right after our own write waits a
    # pass before adopting, so genuine resizes still track.
    assert abs(viewbox_heights(page)[0] - expected) <= 320 * 15 / width + 1
