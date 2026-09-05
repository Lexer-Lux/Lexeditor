"""Verify the FFNx-supported FF8 executable-text integration."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX_EXE_DATA = ROOT / "_scratch/ffnx-upstream/src/exe_data.cpp"
FF8UE_EXE = ROOT / "_scratch/ff8ue-upstream/FF8GameData/ExeSection/exefile.py"
FF8UE_SCHEMA = ROOT / "_scratch/ff8ue-upstream/FF8GameData/Resources/json/exe.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8 import executable_text  # noqa: E402
from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import wait_eval  # noqa: E402
from tools.verify_panel_layout_visual_46 import (  # noqa: E402
    browser_session, close_browser, screenshot,
)


def api(url: str, path: str, payload: dict | None = None) -> dict:
    request = Request(url + path)
    if payload is not None:
        request.data = json.dumps(payload).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def raw_entries(data: bytes, count: int) -> list[bytes]:
    offsets = [int.from_bytes(data[index:index + 4], "little")
               for index in range(0, count * 4, 4)]
    result = []
    for index, offset in enumerate(offsets):
        limit = offsets[index + 1] if index + 1 < count else len(data)
        end = data.find(b"\0", offset, limit)
        assert end >= 0
        result.append(data[offset:end + 1])
    return result


def verify_primary_contracts() -> dict:
    assert EXE.is_file()
    digest = sha256(EXE.read_bytes()).hexdigest()
    assert digest == executable_text.SUPPORTED_EXE_SHA256
    ffnx = FFNX_EXE_DATA.read_text(encoding="utf-8")
    for filename in ("card_names", "draw_point", "card_texts"):
        assert f'ff8_get_exe_path("{filename}"' in ffnx
    assert "replace_function(ff8_externals.get_card_name, ff8_get_card_name)" in ffnx
    assert "patch_code_uint(ff8_externals.drawpoint_messages, uint32_t(msd))" in ffnx
    assert "patch_code_uint(uint32_t(ff8_externals.card_texts_off_B96504)" in ffnx
    assert "patch_code_uint(uint32_t(ff8_externals.card_texts_off_B96968)" in ffnx
    ff8ue = FF8UE_EXE.read_text(encoding="utf-8")
    schema = FF8UE_SCHEMA.read_text(encoding="utf-8")
    assert "MsdType.CARD_NAME" in ff8ue and "MsdType.CARD_TEXT" in ff8ue
    assert "MsdType.DRAW_POINT" in ff8ue
    for offset in ("0x7921E4", "0x874b58", "0x875074"):
        assert offset.casefold() in schema.casefold()
    return {"sha256": digest, "ffnxFiles": 3}


def verify_binary() -> dict:
    result = {}
    for source in executable_text.SOURCES:
        original = executable_text.extracted_msd(EXE, source)
        values = executable_text.extract(EXE, source)
        assert len(values) == source.count
        with tempfile.TemporaryDirectory(prefix="lexeditor-exe-text-msd-") as root:
            path = Path(root) / source.filename
            path.write_bytes(original)
            assert executable_text.read_msd(path, source) == values
            broken = bytearray(original)
            broken[:4] = (source.count * 4 + 1).to_bytes(4, "little")
            path.write_bytes(broken)
            try:
                executable_text.read_msd(path, source)
            except ValueError as error:
                assert "exactly" in str(error)
            else:
                raise AssertionError("A malformed FFNx MSD offset table was accepted")
        changed_id = 1
        changed_text = values[changed_id] + "!"
        rebuilt, changed = executable_text.apply_edits(
            original, source, {changed_id: changed_text})
        assert changed == 1
        before_entries = raw_entries(original, source.count)
        after_entries = raw_entries(rebuilt, source.count)
        assert all(before == after for index, (before, after) in
                   enumerate(zip(before_entries, after_entries)) if index != changed_id)
        assert executable_text.apply_edits(original, source, {changed_id: values[changed_id]}) == (original, 0)
        try:
            executable_text.apply_edits(original, source, {changed_id: "cannot encode 🙂"})
        except ValueError as error:
            assert "not available in the FF8 font" in str(error)
        else:
            raise AssertionError("Unsupported executable-text encoding was accepted")
        result[source.id] = {"count": len(values), "bytes": len(original)}
    return result


def verify_api_and_render() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-exe-text-project-",
                                          ignore_cleanup_errors=True)
    profile = browser = cdp = None
    exe_before = sha256(EXE.read_bytes()).hexdigest()
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            current = api(session.url, "/api/text?dataset=current")
            vanilla = api(session.url, "/api/text?dataset=vanilla")
            counts = {source.id: sum(row["source"] == source.id for row in current["rows"])
                      for source in executable_text.SOURCES}
            assert counts == {source.id: source.count for source in executable_text.SOURCES}
            assert [(row["source"], row["recordId"]) for row in current["rows"][-148:]] == [
                (source.id, record_id) for source in executable_text.SOURCES
                for record_id in range(source.count)
            ]
            for source in executable_text.SOURCES:
                target = next(row for row in current["rows"]
                              if row["source"] == source.id and row["recordId"] == 1)
                replacement = target["value"] + "!"
                edit = {key: target[key] for key in
                        ("source", "sectionId", "recordId", "slot")}
                edit["value"] = replacement
                saved = api(session.url, "/api/text/save", {"edits": [edit]})
                expected = Path(project.name) / "direct/ff8/en/exe" / source.filename
                assert saved["saved"] == 1 and expected.is_file()
                refreshed = api(session.url, "/api/text?dataset=current")["rows"]
                assert next(row for row in refreshed if row["source"] == source.id
                            and row["recordId"] == 1)["value"] == replacement
                vanilla_row = next(row for row in vanilla["rows"] if row["source"] == source.id
                                   and row["recordId"] == 1)
                assert vanilla_row["value"] == target["value"]
            bad = next(row for row in current["rows"] if row["source"] == "exe_card_names")
            payload = {key: bad[key] for key in ("source", "sectionId", "recordId", "slot")}
            payload["value"] = "🙂"
            try:
                api(session.url, "/api/text/save", {"edits": [payload]})
            except HTTPError as error:
                body = json.loads(error.read())
                assert error.code == 400 and "FF8 font" in body["error"]
            else:
                raise AssertionError("API accepted an unsupported executable-text character")

            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('text');state.selected.text='exe_card_names:1';renderText()")
            wait_eval(cdp, "document.querySelector('.kernel-text-editor textarea')!==null", 30)
            rendered = cdp.eval("""(()=>{const row=state.data.text.rows.find(row=>row.id==='exe_card_names:1'),area=document.querySelector('.kernel-text-editor textarea'),panel=area.closest('.kernel-text-editor'),help=panel.querySelector('.lex-info-help');return{source:row?.source,label:row?.sourceLabel,value:area.value,help:help?.getAttribute('aria-label')||'',editable:!area.readOnly,rows:state.data.text.rows.length}})()""")
            assert rendered["source"] == "exe_card_names" and rendered["label"] == "Card names"
            assert rendered["editable"] and rendered["rows"] == 2225
            assert "card_names.msd" in rendered["help"] and "never changes FF8_EN.exe" in rendered["help"]
            rendered["screenshot"] = str(screenshot(cdp, "goal-62-ff8-executable-text.png"))
            return {"counts": counts, "rendered": rendered}
    finally:
        assert sha256(EXE.read_bytes()).hexdigest() == exe_before
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def main() -> int:
    formats = (ROOT / "games/ff8/formats.py").read_text(encoding="utf-8")
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert 'paths.DIRECT_ROOT / "ff8" / "en" / "exe" / source.filename' in formats
    assert "exe_card_names" in editor and "exe_draw_point" in editor and "exe_card_texts" in editor
    print(json.dumps({"primary": verify_primary_contracts(), "binary": verify_binary(),
                      "apiRendered": verify_api_and_render()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
