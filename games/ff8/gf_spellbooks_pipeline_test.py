"""Temporary-project save/composition proof. Never installs a game runtime."""
from hashlib import sha256
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from . import gf_spellbooks as books, gameplay_settings as settings, paths

DOCUMENT={"schemaVersion":1,"books":[{"gfId":0,"pages":[[{"magicId":7,"abilityId":None}],[{"magicId":4,"abilityId":20}]]}]}


def digest(path):
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class PipelineTests(unittest.TestCase):
    def test_isolated_save_reload_disable_and_dependency_rejection(self):
        protected=[paths.GAME_ROOT/"FF8_EN.exe",paths.GAME_ROOT/"FFNx.toml",paths.GAME_ROOT/"AF3DN.P",settings.settings_path(paths.PROJECT_ROOT),settings.patch_path(paths.PROJECT_ROOT)]
        original={p:digest(p) for p in protected}
        try:
            with tempfile.TemporaryDirectory(prefix="lexeditor-gf93-pipeline-") as name:
                directory=Path(name);project=directory/"project";runtime=directory/"runtime"
                with patch.object(paths,"MODS_ROOT",directory/"mods"),patch.object(settings.ffnx_manager,"install_derivative",side_effect=AssertionError("Unexpected runtime install")):
                    data=settings.load(project,paths.GAME_ROOT,runtime)
                    self.assertFalse(data["gfSpellbooksEnabled"])
                    data.update(gfSpellbooksEnabled=True,singleGf=True,sharedMagicInventory=False,flatStatAbilities=True,streamlinedDraw=True,maxSpellEnabled=True)
                    with self.assertRaisesRegex(ValueError,"at least one"):
                        settings.save(data,paths.GAME_ROOT,project,install_runtime=False,runtime_root=runtime)
                    books.save(project,DOCUMENT)
                    for cap in (1,100,150,255):
                        data["maxSpell"]=cap
                        settings.save(data,paths.GAME_ROOT,project,install_runtime=False,runtime_root=runtime)
                        loaded=settings.load(project,paths.GAME_ROOT,runtime)
                        self.assertTrue(loaded["gfSpellbooksEnabled"])
                        self.assertEqual(loaded["maxSpell"],cap)
                        self.assertEqual(books.load(project),DOCUMENT)
                        generated=settings.patch_path(project).read_text(encoding="utf-8")
                        self.assertIn("27B0000:2000",generated)
                        assignments={int(a,16):bytes.fromhex(b) for a,b in re.findall(r"(?m)^([0-9A-F]+) = ([0-9A-F ]+)$",generated)}
                        self.assertEqual(assignments[0x4C8A14],bytes.fromhex("84 C0 75 0A"))
                        self.assertEqual(len(assignments[0x4C8A0C]),8)
                        materialized=settings.materialized_runtime_patch_path(runtime)
                        self.assertTrue(materialized.is_file())
                        self.assertIn("27B0000",materialized.read_text(encoding="utf-8"))
                    before={p:p.read_bytes() for p in (settings.settings_path(project),settings.patch_path(project),project/books.FILE_NAME)}
                    for bad in ({"singleGf":False},{"sharedMagicInventory":True,"maxSpell":100}):
                        with self.assertRaises(ValueError):
                            settings.save({**data,**bad},paths.GAME_ROOT,project,install_runtime=False,runtime_root=runtime)
                        self.assertEqual({p:p.read_bytes() for p in before},before)
                    settings.save({**data,"gfSpellbooksEnabled":False},paths.GAME_ROOT,project,install_runtime=False,runtime_root=runtime)
                    self.assertFalse(settings.load(project,paths.GAME_ROOT,runtime)["gfSpellbooksEnabled"])
                    self.assertNotIn("27B0000",settings.patch_path(project).read_text(encoding="utf-8"))
                    self.assertNotIn("27B0000",settings.materialized_runtime_patch_path(runtime).read_text(encoding="utf-8"))
                    self.assertEqual(books.load(project),DOCUMENT)
        finally:
            self.assertEqual({p:digest(p) for p in protected},original,"A protected user file changed")


if __name__=="__main__":unittest.main()
