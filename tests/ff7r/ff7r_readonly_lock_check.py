"""Rendered proof that the FF7R editor's read-only lock mark sits in the same
place - centred on its control box, at a fixed inset from that box's right
edge - across every read-only property kind the plugin renders: a resolved
text value (Name), a resolved long text value (Explanation), an unresolved
raw text value, a read-only number, and a read-only enum select.

This is a rendered/measured check, not a source read: it boots the real FF7R
editor with in-memory fixtures (same harness as ff7r_browser_check.py),
screenshots the Abilities detail panel, and measures every
`.lex-has-readonly-lock` box against the `.lex-field-readonly-lock` svg it
carries.

Issue reported by Lexer: in Abilities, the lock on Name/Explanation sat far
below the value it marks. Root cause was plugin-side: `readonlyResolved()`
in plugins/ff7r/editor.js wrapped a resolved value in an extra <div> holding
two stacked lines (the resolved text and a raw-id note beneath it), so the
shared lock's host box was twice the height of the visible value box and the
lock centred on the wrong box. The shared ui/framework.css lock-positioning
rule itself (`top:50%` of `.lex-has-readonly-lock`, right inset via
`--lex-readonly-lock-inset`) is correct for a single-element control; this
check exists to prove the plugin now only ever hands it one.
"""
from __future__ import annotations

DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ff7r_browser_check as bc

ROOT = bc.ROOT


def build_fixture() -> dict:
    fixture = bc.fixtures()
    ability = fixture["data"][bc.ABILITY]
    ability["properties"] = [
        bc.prop("ATB", editable=False),
        bc.prop("Element", "ENUM", editable=False),
        bc.prop("Name", "STRING", editable=False),
        bc.prop("Explanation", "STRING", editable=False),
        bc.prop("InternalCode", "STRING", editable=False),
    ]
    ability["names"] = ["Fire", "Ice", "Lightning"]
    ability["records"] = [
        {"id": 0, "tag": "Braver", "values": {
            "ATB": 1, "Element": "Fire",
            "Name": "$Ability_Braver_Name",
            "Explanation": "$Ability_Braver_Help",
            "InternalCode": "ABL_BRAVER_001",
        }},
    ]
    ability["textLookup"] = {
        "$Ability_Braver_Name": "Braver",
        "$Ability_Braver_Help": (
            "A powerful strike that channels the user's ATB gauge directly "
            "into a single heavy blow against one target."
        ),
    }
    return fixture


def document(fixture: dict) -> str:
    original = bc.fixtures
    bc.fixtures = lambda: fixture
    try:
        return bc.document()
    finally:
        bc.fixtures = original


def measure(page) -> list[dict]:
    return page.evaluate("""() => {
      const out = [];
      for (const host of document.querySelectorAll('.lex-has-readonly-lock')) {
        const lock = host.querySelector('.lex-field-readonly-lock');
        if (!lock) continue;
        const field = host.closest('.lex-detail-field');
        const labelNode = field?.querySelector('.lex-detail-field-label-text');
        const box = host.matches('input,select,textarea,output')
          ? host
          : (host.querySelector('input,select,textarea,output') || host);
        const boxRect = box.getBoundingClientRect();
        const lockRect = lock.getBoundingClientRect();
        out.push({
          label: (labelNode?.textContent || '').trim(),
          boxTop: boxRect.top, boxBottom: boxRect.bottom, boxRight: boxRect.right,
          boxCenterY: (boxRect.top + boxRect.bottom) / 2,
          lockCenterY: (lockRect.top + lockRect.bottom) / 2,
          lockRight: lockRect.right,
          insetFromRight: boxRect.right - lockRect.right,
        });
      }
      return out;
    }""")


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fixture = build_fixture()
    html = document(fixture)
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--no-sandbox"]}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            context, page, errors = bc.new_page(
                browser, html, 1200, 800, diagnostic=output / "boot-failure.png")
            try:
                page.evaluate("() => { void navigate('abilities'); }")
                page.wait_for_function(
                    "() => state.tab==='abilities' && !state.busy")
                page.wait_for_selector(".lex-field-readonly-lock")
                page.screenshot(path=str(output / "abilities-readonly-locks.png"), full_page=True)
                measurements = measure(page)
            finally:
                context.close()
        finally:
            browser.close()

    (output / "measurements.json").write_text(
        json.dumps(measurements, indent=2), encoding="utf-8")
    print(json.dumps(measurements, indent=2))

    assert measurements, "No read-only lock rendered at all; nothing to measure"
    by_label = {row["label"]: row for row in measurements}
    expected_labels = {"ATB", "Element", "Name", "Explanation", "InternalCode"}
    missing = expected_labels - set(by_label)
    assert not missing, f"Expected read-only fields not rendered: {missing}"

    # Every kind must centre its lock on its own control box. A wrapper that
    # stacks a second line under the value (the old Name/Explanation shape)
    # shows up here as a multi-pixel vertical miss.
    for label, row in by_label.items():
        drift = abs(row["lockCenterY"] - row["boxCenterY"])
        assert drift <= 1.5, (
            f"{label}: lock is {drift:.1f}px off the vertical centre of its own "
            f"control box (box {row['boxTop']:.1f}-{row['boxBottom']:.1f}, "
            f"lock centre {row['lockCenterY']:.1f})"
        )

    # Every kind must sit the same fixed distance from its own box's right
    # edge - "far too left" on some other field would show up as an outlier
    # inset here relative to the rest.
    insets = {label: row["insetFromRight"] for label, row in by_label.items()}
    spread = max(insets.values()) - min(insets.values())
    assert spread <= 1.5, f"Lock inset from the control's right edge is inconsistent: {insets}"

    print("PASS: read-only lock is centred on its own control box, "
          f"{next(iter(insets.values())):.1f}px inset from its right edge, "
          f"across all {len(by_label)} read-only property kinds: {sorted(by_label)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=DEV_CACHE / "ff7r-readonly-lock")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
