"""Build a local-only title-label test from the user's installed FF7R files."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from plugins.ff7r.archive import extract_pair
from plugins.ff7r.textresource import TextResourcePackage
from plugins.ff7r.tooling import pack_directory, get_file
from plugins.ff7r.mod_support import PakModAdapter
from mod_library import file_tree, digest


def prepare(game: Path, data: Path, output: Path):
    if output.exists():
        raise ValueError("Choose a new output folder; existing test files will not be replaced")
    asset = "End/Content/GameContents/Text/US/Resident_TxtRes"
    index = json.loads((data / "ff7r-index.json").read_text(encoding="utf-8"))
    source_uasset, source_uexp = extract_pair(game, data, index, asset, collection="textAssets")
    package = TextResourcePackage(source_uasset, source_uexp)
    matches = [(i, row) for i, row in enumerate(package.entries) if row.id == "$menu_title_0001_0000"]
    if len(matches) != 1 or matches[0][1].text != "New Game":
        raise ValueError("The installed English title label does not match the test baseline")
    package.apply_edits([{"entry": matches[0][0], "text": "MOD TEST"}])
    output.mkdir(parents=True)
    folder = output / "Folder package/Unusual wrapper/Game files"
    folder.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="lexeditor-title-test-") as temp:
        content = Path(temp)
        package.write_pair(content / (asset + ".uasset"), content / (asset + ".uexp"))
        pak = folder / "LexeditorLibraryTest_P.pak"
        pack_directory(content, pak, version="V4")
    checked = TextResourcePackage.from_bytes(get_file(pak, asset + ".uasset"), get_file(pak, asset + ".uexp"))
    assert checked.text_map()["$menu_title_0001_0000"] == "MOD TEST"
    info = {"name": "Library title test", "version": "0.0.1-local-test"}
    (folder / "mod.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    report = PakModAdapter().inspect(folder, file_tree(folder))
    if not report["valid"]:
        raise RuntimeError("; ".join(report["problems"]))
    archive = output / "Library title test.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for relative in file_tree(output / "Folder package"):
            zipped.write(output / "Folder package" / relative, relative.as_posix())
    (output / "TEST.md").write_text(
        "# Local FF7R mod-library test\n\n"
        "This contains modified files from your installed game. Keep it local.\n\n"
        "Use the new Lexeditor host code and FF7R Part 1 plugin. Close the game first.\n"
        "1. Open Mod library. Drop the Folder package folder or the ZIP into it.\n"
        "2. Set Data folder to Unusual wrapper/Game files (or the same folder below the dropped root).\n"
        "3. Import Library title test. Enable it and choose Apply enabled mods.\n"
        "4. Start FF7R with your existing DX11 launch method, in English.\n"
        "5. On the title menu, New Game must read MOD TEST. Do not start a new game.\n"
        "6. Close the game. Disable this test mod and apply the change.\n"
        "7. Start again in DX11. The title menu must read New Game again.\n\n"
        "Report both results and any import or activation error. The package was checked\n"
        "by reading it back; the game result is not yet verified.\n", encoding="utf-8")
    result = {"folder": str(output / "Folder package"), "zip": str(archive),
              "pakSha256": digest(pak), "instructions": str(output / "TEST.md")}
    (output / "checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.game, args.data, args.output), indent=2))
