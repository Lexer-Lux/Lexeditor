"""Real rendered animation controls: drill down, edit, selects, save and reload."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "ds1"))
from ds1_effects_fixture import make_effects_archive
from tae_fixture import build_anibnd, build_tae
from plugins.ds1.formats import ItemDocument, inflate, members
from plugins.ds1.tae import TaeDocument
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.tae_store import CHR_DIR
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright

BINDER = "c1200.anibnd.dcx"
TAE = "a87.tae"


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    root = os.environ.get("LEXEDITOR_DS1_ACCEPTANCE_ROOT")
    if root:
        raise AssertionError("Acceptance root is not supported by this check yet")
    raw = make_effects_archive()
    vanilla_binder = build_anibnd({TAE: build_tae()})
    digest = hashlib.sha256(raw).hexdigest()
    binder_digest = hashlib.sha256(vanilla_binder).hexdigest()
    effect_ids = sorted(row.row_id for row in ItemDocument(raw).params["SpEffectParam"].rows)
    expected_options = len(effect_ids) + (0 if 31 in effect_ids else 1)
    exact = lambda value: struct.unpack("<f", struct.pack("<f", value))[0]
    new_start = exact(0.25)
    errors = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-animations-") as temp:
        game, mod = Path(temp) / "game", Path(temp) / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / CHR_DIR).mkdir(parents=True)
        (game / CHR_DIR / BINDER).write_bytes(vanilla_binder)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0", "LEXEDITOR_MOD_READ_ONLY": "0"})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1100, "height": 800})
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="animations"]').click()
                    page.wait_for_function("state.tab==='animations' && state.animChars.length===1")
                    assert page.evaluate("state.animChars[0].name") == "c1200"
                    assert page.evaluate("state.animTabs[0].id") == "animations"
                    if output:
                        page.wait_for_timeout(250)
                        page.screenshot(path=str(output / "animations-chars.png"))
                    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
                    assert page.evaluate("state.rows.map(r=>r.name)") == ["a87_3300.HKX", "animation 3301"]
                    if output:
                        page.screenshot(path=str(output / "animations-anims.png"))
                    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
                    page.wait_for_function("state.animScope.level==='events' && state.rows.length===4")
                    assert page.evaluate("state.rows.map(r=>r.values.label)") == [
                        "Attack", "Add effect", "Unknown event 999", "Unknown event 16"]
                    assert page.locator('[data-anim-left] [data-tabstrip-id="events"].active').count() == 1
                    if output:
                        page.screenshot(path=str(output / "animations-events.png"))
                    page.locator('[data-anim-left] [data-tabstrip-id="chars"]').click()
                    page.wait_for_function("state.animLeftTab==='chars'")
                    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
                    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
                    page.wait_for_function("state.animScope.level==='events' && state.rows.length===4")
                    page.get_by_role("searchbox", name="Search events").fill("Attack")
                    page.locator("[data-anim-list] .lex-list-row", has_text="Attack").click()
                    page.wait_for_function("state.row?.label==='Attack'")
                    assert "Attack at" in page.locator(".lex-detail-panel-title").inner_text()
                    assert page.get_by_text(BINDER, exact=False).count() >= 1
                    field = page.locator('[data-field-key="start"]:visible')
                    assert field.evaluate("n=>n.tagName") == "INPUT" and field.get_attribute("step") == "any"
                    assert field.get_attribute("min") is None and field.get_attribute("max") is None
                    field.fill(str(new_start))
                    field.press("Tab")
                    page.wait_for_function("(x) => state.pending===0 && state.row.fields.find(f=>f.key==='start').value===x", arg=new_start)
                    # The shared timestamp moves the sibling event too.
                    assert page.evaluate("state.dirty") == 2
                    judge = page.locator('[data-field-key="judge"]:visible')
                    judge.fill("300")
                    judge.press("Tab")
                    page.wait_for_function("state.pending===0 && state.row.fields.find(f=>f.key==='judge').value===300")
                    attack = page.locator('[data-field-key="attackType"]:visible')
                    assert attack.evaluate("n=>n.tagName") == "SELECT"
                    assert attack.locator("option").count() == 5
                    box = page.get_by_role("searchbox", name="Search events")
                    box.click()
                    box.press("ControlOrMeta+A")
                    box.press("Backspace")
                    page.wait_for_function("state.animQuery===''")
                    box.fill("Add effect")
                    page.locator("[data-anim-list] .lex-list-row", has_text="Add effect").click()
                    page.wait_for_function("state.row?.label==='Add effect'")
                    effect = page.locator('[data-field-key="effect"]:visible')
                    assert effect.evaluate("n=>n.tagName") == "SELECT"
                    assert effect.locator("option").count() == expected_options
                    effect.select_option("6890")
                    page.wait_for_function("state.pending===0 && state.row.fields.find(f=>f.key==='effect').value===6890")
                    if output:
                        page.screenshot(path=str(output / "animations-detail.png"))
                    page.set_viewport_size({"width": 1000, "height": 700})
                    page.wait_for_timeout(400)
                    assert page.locator('[data-field-key="start"]').evaluate("n=>n.clientWidth") >= 70
                    if output:
                        page.screenshot(path=str(output / "animations-small.png"))
                    page.set_viewport_size({"width": 1100, "height": 800})
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    saved_plain = inflate((mod / CHR_DIR / BINDER).read_bytes())
                    entry = members(saved_plain)[TAE]
                    saved = TaeDocument(bytes(saved_plain[entry.offset:entry.offset + entry.size]))
                    first = saved.read_event(0, 0)
                    by_key = {item["key"]: item["value"] for item in first["fields"]}
                    assert (by_key["start"], by_key["judge"]) == (new_start, 300)
                    second = saved.read_event(0, 1)
                    assert next(item["value"] for item in second["fields"] if item["key"] == "start") == new_start
                    assert next(item["value"] for item in second["fields"] if item["key"] == "effect") == 6890
                    page.locator('[data-tab="animations"]').click()
                    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
                    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
                    page.wait_for_function("state.animScope.level==='events' && state.rows.length===4 && state.row")
                    page.locator('[data-tae-action="add"]').click()
                    page.wait_for_selector('[data-tae-input="type"]')
                    assert page.locator('[data-tae-input="type"] option').count() > 40
                    page.locator('[data-tae-input="start"]').fill("0.1")
                    page.locator('[data-tae-input="end"]').fill("0.2")
                    if output:
                        page.screenshot(path=str(output / "animations-add-form.png"))
                    page.get_by_role("button", name="Create event", exact=True).click()
                    page.wait_for_function("state.rows.length===5 && state.row?.type===66")
                    assert "Add effect at" in page.locator(".lex-detail-panel-title").inner_text()
                    added = page.locator('[data-field-key="effect"]:visible')
                    added.select_option("6890")
                    page.wait_for_function("state.pending===0 && state.row.fields.find(f=>f.key==='effect').value===6890")
                    if output:
                        page.screenshot(path=str(output / "animations-added.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    grown_plain = inflate((mod / CHR_DIR / BINDER).read_bytes())
                    grown_entry = members(grown_plain)[TAE]
                    grown = TaeDocument(bytes(grown_plain[grown_entry.offset:grown_entry.offset + grown_entry.size]))
                    assert [event["type"] for event in grown.list_events(0)] == [1, 66, 999, 16, 66]
                    page.locator('[data-tab="animations"]').click()
                    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
                    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
                    page.wait_for_function("state.animScope.level==='events' && state.rows.length===5")
                    page.locator("[data-anim-list] .lex-list-row", has_text="0.10s").click()
                    page.wait_for_function("state.row?.type===66 && state.row.fields.find(f=>f.key==='start').value<0.11")
                    page.locator('[data-tae-action="remove"]').click()
                    page.locator(".lex-dialog").get_by_role("button", name="Remove event").click()
                    page.wait_for_function("state.rows.length===4")
                    if output:
                        page.screenshot(path=str(output / "animations-removed.png"))
                    page.locator("#global-save").click()
                    page.wait_for_function("state.dirty===0 && state.pending===0")
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    shrunk_plain = inflate((mod / CHR_DIR / BINDER).read_bytes())
                    shrunk_entry = members(shrunk_plain)[TAE]
                    shrunk = TaeDocument(bytes(shrunk_plain[shrunk_entry.offset:shrunk_entry.offset + shrunk_entry.size]))
                    assert [event["type"] for event in shrunk.list_events(0)] == [1, 66, 999, 16]
                    key = f"{TAE}|0|1"
                    for field, value in (("effect", 999999), ("effect", 2 ** 31), ("flag", 8), ("start", "soon")):
                        try:
                            request_json(session.url + "api/edit", {"table": BINDER, "id": key, "field": field, "value": value})
                            raise AssertionError("Invalid animation edit accepted")
                        except HTTPError as error:
                            assert error.code == 400
                    try:
                        request_json(session.url + "api/edit", {"table": "c0001.anibnd.dcx", "id": key, "field": "start", "value": 1.0})
                        raise AssertionError("Unknown binder edit accepted")
                    except HTTPError as error:
                        assert error.code == 400
                    for url, body in (
                            ("api/tae/add", {"table": BINDER, "tae": TAE, "anim": 0, "type": 999, "start": 0.0, "end": 1.0}),
                            ("api/tae/add", {"table": BINDER, "tae": TAE, "anim": 0, "type": 66, "start": 0.0, "end": 1.0,
                                             "values": {"effect": 2 ** 31}}),
                            ("api/tae/remove", {"table": BINDER, "id": f"{TAE}|0|99"})):
                        try:
                            request_json(session.url + url, body)
                            raise AssertionError("Invalid animation add/remove accepted")
                        except HTTPError as error:
                            assert error.code == 400
                    session.stop()
                    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game), "LEXEDITOR_DS1_PROJECT": str(mod),
                                          "LEXEDITOR_NO_MOD": "1", "LEXEDITOR_MOD_READ_ONLY": "1"})
                    session.start()
                    page.goto(session.url + "?lexNoMod=1")
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="animations"]').click()
                    page.wait_for_function("state.tab==='animations' && state.rows.length>0")
                    page.locator("[data-anim-chars] .lex-list-row", has_text="c1200").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    page.wait_for_function("state.animScope.level==='anims' && state.rows.length===2")
                    page.locator("[data-anim-list] .lex-list-row", has_text="a87_3300.HKX").click()
                    page.locator('[data-anim-left] [data-tabstrip-id="events"]').click()
                    page.wait_for_function("state.animScope.level==='events' && state.row?.label==='Attack'")
                    control = page.locator('[data-field-key="start"]:visible')
                    assert control.is_disabled()
                    control.click(force=True)
                    page.get_by_text("Create a mod to edit?", exact=True).wait_for()
                    if output:
                        page.screenshot(path=str(output / "animations-vanilla-prompt.png"))
                    page.get_by_role("button", name="Cancel", exact=True).click()
                    try:
                        request_json(session.url + "api/edit", {"table": BINDER, "id": key, "field": "start", "value": 1.0})
                        raise AssertionError("Vanilla animation edit accepted")
                    except HTTPError as error:
                        assert error.code == 403
                    try:
                        request_json(session.url + "api/tae/add", {"table": BINDER, "tae": TAE, "anim": 0, "type": 66,
                                                                  "start": 0.0, "end": 1.0})
                        raise AssertionError("Vanilla animation add accepted")
                    except HTTPError as error:
                        assert error.code == 403
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == digest
        assert hashlib.sha256((game / CHR_DIR / BINDER).read_bytes()).hexdigest() == binder_digest
    print(json.dumps({"chars": 1, "anims": 2, "events": 4, "effectSelectOptions": len(effect_ids),
                      "fieldsSavedReloaded": 4, "eventAddedRemoved": True, "vanillaCreateModPrompt": True,
                      "originalUnchanged": True, "browserErrors": errors}))


if __name__ == "__main__":
    main()
