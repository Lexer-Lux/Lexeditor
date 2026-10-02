"""Tweaks live in the mod library, never in Lexeditor's repository.

A tweak is an ordinary mod: its script, ASI, Hext, DLL or INI travels with the
mod that owns it, under the reader's mod library. This check fails when tweak
code or a built tweak payload is committed here, and when an allowance below
outlives the thing it allowed, so the list can only shrink.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

# Built payloads a game loads as a tweak. Hext text is recognised by its
# folder, since FFNx reads plain .txt files from hext/.
TWEAK_SUFFIXES = (".asi", ".hext")
TWEAK_FOLDERS = ("hext", "native_runtime", "GameplayTweaks")

# Binaries that may stay, each with the reason. A driver or a third-party
# runtime is plugin infrastructure, not a tweak; the rest wait on their issue.
ALLOWED_BINARIES = {
    "plugins/ff8/ffnx_issue_51/package/AF3DN.P": "FFNx derivative driver (plugin infrastructure)",
    "plugins/ff8/ffnx_issue_51/package/FFNx_steam_api.dll": "FFNx derivative driver (plugin infrastructure)",
    "plugins/ff9/runtime/Memoria.Scripts.Lexeditor.dll": "FF9 tweaks, moving to library mods in #913",
}
# Folders holding tweak source that has not moved yet.
ALLOWED_FOLDERS = {
    "plugins/ff7r/native_runtime": "FF7R runtime tweaks, moving to library mods in #912",
}
# Asset build tools and editors that ship as binaries but never load into a game.
TOOL_PREFIXES = ("tools/", "plugins/rdr2/assets/item-icons/")


def tracked() -> list[str]:
    output = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True).stdout.decode("utf-8")
    return [path for path in output.split("\0") if path]


class NoTweakPayloadsTests(unittest.TestCase):
    def setUp(self):
        self.files = tracked()

    def test_no_built_tweak_payloads(self):
        found = [path for path in self.files
                 if path.casefold().endswith(TWEAK_SUFFIXES)]
        self.assertEqual(found, [], "Built tweaks belong in a library mod, not in Lexeditor")

    def test_no_tweak_source_folders(self):
        found = sorted({
            "/".join(parts[:index + 1])
            for parts in (path.split("/") for path in self.files)
            for index, part in enumerate(parts[:-1])
            if part in TWEAK_FOLDERS
        } - set(ALLOWED_FOLDERS))
        self.assertEqual(found, [], "Tweak source belongs in the mod that ships it")

    def test_no_unlisted_game_binaries(self):
        found = [path for path in self.files
                 if path.startswith("plugins/")
                 and path.casefold().endswith((".dll", ".asi", ".p"))
                 and not path.startswith(TOOL_PREFIXES)
                 and path not in ALLOWED_BINARIES]
        self.assertEqual(found, [], "A game-loaded binary is a tweak unless listed here with its reason")

    def test_allowances_still_exist(self):
        present = set(self.files)
        stale = [path for path in ALLOWED_BINARIES if path not in present]
        stale += [folder for folder in ALLOWED_FOLDERS
                  if not any(path.startswith(folder + "/") for path in present)]
        self.assertEqual(stale, [], "Remove allowances for payloads that already left")


if __name__ == "__main__":
    unittest.main()
