"""Invalid PlayerParameter drafts must survive navigation without saving."""
import shutil
import struct
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from ff7r2_fixture import fixture
from plugins.ff7r2.dataobject import DataObjectPackage
from plugins.ff7r2.plugin import Ff7r2Session


PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")


@pytest.mark.parametrize("hp_type", [7, 9])
def test_numeric_drafts_and_real_save(tmp_path, hp_type):
    project = tmp_path / "project"
    project.mkdir()
    (project / "lexeditor-project.json").write_text('{"format":1,"game":"ff7r2"}')
    source = project / "source" / PLAYER
    source.parent.mkdir(parents=True)
    original = fixture(hp_type=hp_type)
    source.write_bytes(original)
    requests, errors = [], []
    with Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(project)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(executable_path=shutil.which("chromium") or None, headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url) if request.method == "POST" else None)
                page.goto(session.url, wait_until="domcontentloaded")
                page.wait_for_selector('input[aria-label="HPMax"]')
                hp = page.get_by_label("HPMax", exact=True)
                assert hp.get_attribute("type") == "number"
                assert hp.get_attribute("step") == ("1" if hp_type == 7 else "any")
                assert float(hp.get_attribute("max")) == (2147483647 if hp_type == 7 else 3.4028234663852886e38)
                assert float(hp.get_attribute("min")) == (-2147483648 if hp_type == 7 else -3.4028234663852886e38)
                invalid_values = ["1.5", "2147483648", ""] if hp_type == 7 else ["3.5e38", "-3.5e38", ""]
                for raw in invalid_values:
                    hp.fill(raw)
                    assert page.evaluate("fieldOf(player.records[0],'HPMax').value") == 1000
                    assert page.evaluate("dirtyCount()") == 1
                    assert page.evaluate("pendingChanges()[0].after") == raw
                    failure = page.evaluate("async()=>{try{await savePlayer();return null}catch(error){return error.message}}")
                    assert "Correct HPMax" in failure
                    page.evaluate("render()")
                    assert hp.input_value() == raw
                    page.locator(".lex-column-list-row").filter(has_text="TestCharacter03").first.click()
                    assert hp.input_value() == "850"
                    failure = page.evaluate("async()=>{try{await savePlayer();return null}catch(error){return error.message}}")
                    assert "Correct HPMax in Cloud" in failure
                    page.locator(".lex-column-list-row").filter(has_text="Cloud").first.click()
                    assert hp.input_value() == raw
                    assert not any("/api/player-parameter/save" in url for url in requests)
                page.evaluate("discardPlayer()")
                page.wait_for_function("dirtyCount()===0")
                assert hp.input_value() == "1000"
                valid = "2147483647" if hp_type == 7 else "1234.125"
                hp.fill(valid)
                assert page.evaluate("dirtyCount()") == 1
                # An invalid draft on an already changed field counts once.
                hp.fill(invalid_values[0])
                assert page.evaluate("dirtyCount()") == 1
                assert page.evaluate("fieldOf(player.records[0],'HPMax').value") == float(valid)
                hp.fill(valid)
                page.evaluate("savePlayer()")
                page.wait_for_function("dirtyCount()===0")
                assert (project / "content" / PLAYER).is_file()
                expected = bytearray(original)
                offset = DataObjectPackage.from_bytes(original).records[0].fields[0].offset
                struct.pack_into("<i" if hp_type == 7 else "<f", expected, offset,
                                 int(valid) if hp_type == 7 else float(valid))
                assert (project / "content" / PLAYER).read_bytes() == bytes(expected)
                page.evaluate("reopenPlayer()")
                assert float(hp.input_value()) == float(valid)
                assert source.read_bytes() == original
                assert not errors
            finally:
                browser.close()
