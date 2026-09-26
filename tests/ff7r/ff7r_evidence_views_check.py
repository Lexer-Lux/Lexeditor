"""A read-only research view is not a tweak setting.

Lexer, on the Tweaks page: "still says '15 more groups still loading' then the
entire program freezes up." Reproduced against the installed game: opening
Tweaks asked the service for all seventeen "Lexeditor ..." catalog rows, and
eight of those rows are read-only research evidence (catalog synthetic names
ending in "-probe"). Reading one re-scans the installed game, so that tab open
cost about 170 seconds of CPU and about 1.8 GB before it settled.

This check holds the two halves of the repair:

1. The service marks those rows so a reader can tell evidence from a setting,
   and the Data Map still calls them a generated research view.
2. The Tweaks page reads only the groups a reader can change. An evidence row
   opened from the Data Map is shown by the DataObject screen instead, and the
   Tweaks page never fetches it.

Both halves run here: a service-level assertion over the real virtual rows,
then a rendered run of the real editor with in-memory fixtures modelled on
those rows, with the evidence asset deliberately slow so that loading it (the
old behaviour) cannot be mistaken for the settings arriving.
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
sys.path.insert(0, str(ROOT))

from plugins.ff7r import archive, server  # noqa: E402

SETTINGS = "Lexeditor/RuntimeTweaks"
EVIDENCE = "Lexeditor/ATBRuntimeProbe"
# Long enough that loading the evidence view cannot be confused with the
# settings arriving, short enough that a broken page still settles.
EVIDENCE_DELAY_MS = 12000
SETTLED_TIMEOUT_MS = 8000


def service_contract() -> dict:
    """The catalog rows the editor reads, straight from the service's own rows."""
    rows = archive._with_virtual_assets({"assets": [], "textAssets": []})["assets"]
    by_asset = {row["asset"]: row for row in rows}
    assert by_asset[EVIDENCE].get("readOnly") is True, by_asset[EVIDENCE]
    assert "readOnly" not in by_asset[SETTINGS], by_asset[SETTINGS]
    read_only = sorted(row["asset"] for row in rows if row.get("readOnly"))
    assert len(read_only) == 8, read_only
    assert all(archive.is_read_only_evidence(by_asset[asset]) for asset in read_only)
    # The Data Map already describes these eight as generated research views.
    original = server.catalog
    server.catalog = lambda: {"assets": rows, "textAssets": []}
    try:
        map_rows = {row["target"]: row for row in server.data_map_payload()["rows"]}
    finally:
        server.catalog = original
    for asset in read_only:
        assert "generated research view" in map_rows[asset]["filename"], map_rows[asset]
        assert map_rows[asset]["coverage"] == "view", map_rows[asset]
    return {"readOnlyRows": read_only}


def fixture(*, base=None) -> dict:
    """One editable group and one read-only evidence view, as the service sends them."""
    payload = (base or bc.fixtures)()
    payload["catalog"] = {"assets": [
        {"asset": SETTINGS, "name": "Runtime Tweaks", "group": "Lexeditor Runtime",
         "synthetic": "runtime-settings"},
        {"asset": EVIDENCE, "name": "ATB Runtime Research", "group": "Lexeditor Research",
         "synthetic": "atb-runtime-probe", "readOnly": True},
    ], "textAssets": []}
    payload["data"] = {
        SETTINGS: {
            "asset": SETTINGS, "sourceSha256": "1" * 64, "activeSha256": "2" * 64,
            "usingProject": False, "exportName": "LexeditorRuntimeTweaks",
            "names": [], "textLookup": {},
            "properties": [bc.prop("Enabled", "BOOL")],
            "records": [{"id": 0, "tag": "Runtime", "values": {"Enabled": False}}],
        },
        EVIDENCE: {
            "asset": EVIDENCE, "sourceSha256": "3" * 64, "activeSha256": "4" * 64,
            "usingProject": False, "exportName": "LexeditorATBRuntimeProbe",
            "names": [], "textLookup": {},
            "properties": [
                bc.prop("ImplementationReady", "BOOL", editable=False),
                bc.prop("Blockers", "STRING", editable=False),
                bc.prop("ResidentCandidateRows", "INT32", editable=False),
            ],
            "records": [{"id": 0, "tag": "ATB Runtime Research", "values": {
                "ImplementationReady": False,
                "Blockers": "assessed-state-query-unproven",
                "ResidentCandidateRows": 0,
            }}],
        },
    }
    return payload


def document() -> str:
    original = bc.fixtures
    bc.fixtures = lambda: fixture(base=original)
    try:
        html = bc.document()
    finally:
        bc.fixtures = original
    # The harness records only the request path. Keep the whole URL so this
    # check can say which resource a screen asked for.
    push = 'window.__requests.push({path, method: options.method || "GET", body});'
    assert push in html, "the shared harness no longer records requests the same way"
    html = html.replace(
        push,
        'window.__requests.push({path, method: options.method || "GET", body,'
        ' url: String(url.href)});',
        1,
    )
    # Every settings group is back inside a second; only the evidence view is
    # slow, because reading one re-scans the installed game. Loading it is
    # exactly what this check is about.
    served = ('    data = window.__fixture.data[url.searchParams.get("asset")];\n'
              '    if(!data){data={error:"Synthetic DataObject not found"};status=404;}')
    assert served in html, "the shared harness no longer serves /api/data the same way"
    html = html.replace(
        served,
        '    const wanted = url.searchParams.get("asset");\n'
        f'    if(wanted === {json.dumps(EVIDENCE)})'
        f' await new Promise(done => setTimeout(done, {EVIDENCE_DELAY_MS}));\n'
        '    data = window.__fixture.data[wanted];\n'
        '    if(!data){data={error:"Synthetic DataObject not found"};status=404;}',
        1,
    )
    return html


def data_requests(page) -> list[str]:
    return page.evaluate(
        "window.__requests.filter(row=>row.path==='/api/data')"
        ".map(row=>new URL(row.url,document.baseURI).searchParams.get('asset'))")


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    contract = service_contract()
    html = document()
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--no-sandbox"]}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            context, page, errors = bc.new_page(
                browser, html, 1200, 800, diagnostic=output / "boot-failure.png")
            try:
                # The harness waits for a loaded DataObject; the first catalog
                # row is the settings group, so that wait is already satisfied.
                page.evaluate("() => { void navigate('tweaks'); }")
                page.wait_for_function(
                    "() => state.tweaks && Object.keys(state.tweaks).length"
                    " && !state.tweaksPending",
                    timeout=SETTLED_TIMEOUT_MS)
                groups = page.evaluate("Object.keys(state.tweaks)")
                assert groups == [SETTINGS], groups
                fetched = [asset for asset in data_requests(page) if asset]
                assert EVIDENCE not in fetched, fetched
                pending = page.evaluate("state.tweaksPending")
                assert pending == 0, pending
                text = page.locator("#main").inner_text()
                assert "still reading" not in text, text
                assert "runtime tweaks" in text.lower(), text
                page.screenshot(path=str(output / "tweaks-settings-only.png"), full_page=True)

                # The evidence view the Data Map offers is still reachable: it
                # is opened as read-only data, not by loading the tweak page.
                page.evaluate("() => { void openMapRow({target: '"
                              + EVIDENCE + "'}); }")
                page.wait_for_function(
                    "asset => state.tab==='misc' && state.data?.asset===asset && !state.busy",
                    arg=EVIDENCE, timeout=60000)
                fetched = [asset for asset in data_requests(page) if asset]
                assert fetched.count(EVIDENCE) == 1, fetched
                assert page.evaluate("state.tweaks && Object.keys(state.tweaks).length") == 1, \
                    "opening one evidence view must not reload the tweak groups"
                # The report's own values are what this view is for, and every
                # field it carries is read-only and carries the lock.
                fields = page.evaluate("""() => [...document.querySelectorAll(
                    '#main .lex-detail-field')].map(field => {
                  const control = field.querySelector('input,select,textarea,output');
                  return {
                    label: field.querySelector('.lex-detail-field-label-text')?.textContent || '',
                    value: control?.type === 'checkbox'
                      ? (control.checked ? 'checked' : 'unchecked') : (control?.value ?? ''),
                    readOnly: field.dataset.lexReadonly === 'true',
                    locked: !!field.querySelector('.lex-field-readonly-lock'),
                  };
                })""")
                assert fields == [
                    {"label": "ImplementationReady", "value": "unchecked", "readOnly": True,
                     "locked": True},
                    {"label": "Blockers", "value": "assessed-state-query-unproven",
                     "readOnly": True, "locked": True},
                    {"label": "ResidentCandidateRows", "value": "0", "readOnly": True,
                     "locked": True},
                ], fields
                picker = page.get_by_role("combobox", name="FF7 Remake misc data table")
                assert picker.input_value() == EVIDENCE, picker.input_value()
                assert "ATB Runtime Research" in picker.locator(
                    "option:checked").inner_text(), picker.inner_text()
                page.screenshot(path=str(output / "evidence-view-readonly.png"),
                                full_page=True)

                # A settings row still opens the Tweaks page it belongs to.
                page.evaluate("() => { void openMapRow({target: '" + SETTINGS + "'}); }")
                page.wait_for_function(
                    "() => state.tab==='tweaks' && !state.tweaksPending", timeout=30000)
                assert page.evaluate("state.tab") == "tweaks"
                assert not errors, errors
            finally:
                context.close()
        finally:
            browser.close()
    print(json.dumps({
        "readOnlyCatalogRows": contract["readOnlyRows"],
        "tweaksPageFetches": "settings groups only",
        "evidenceOpensAs": "read-only DataObject record",
    }, indent=2))
    print("PASS: the Tweaks page loads only groups a reader can change; a read-only "
          "research view opens on the DataObject screen and keeps its locks.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path,
                        default=DEV_CACHE / "ff7r-evidence-views")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
