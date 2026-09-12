from __future__ import annotations

import base64
import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server
from games.terraria.assets import asset_index, asset_state, create_asset, read_asset, replace_asset


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PNG_1X1_ALT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nAAAAABJRU5ErkJggg=="
)


class TerrariaAssetTests(unittest.TestCase):
    def test_create_indexes_and_reads_png_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = create_asset(root, "Content/Items/Sword.png", PNG_1X1)
            self.assertEqual(state["path"], "Content/Items/Sword.png")
            self.assertEqual(state["kind"], "image")
            self.assertEqual(state["preview"], "image")
            self.assertEqual((state["width"], state["height"]), (1, 1))

            index = asset_index(root)
            self.assertEqual([row["path"] for row in index["files"]], ["Content/Items/Sword.png"])
            self.assertTrue(index["files"][0]["editable"])
            target, data, read_state = read_asset(root, state["path"])
            self.assertEqual(target, root / "Content" / "Items" / "Sword.png")
            self.assertEqual(data, PNG_1X1)
            self.assertEqual(read_state["sha256"], state["sha256"])

    def test_replace_is_sha_guarded_and_noop_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = create_asset(root, "icon.png", PNG_1X1)
            noop = replace_asset(root, "icon.png", PNG_1X1, created["sha256"])
            self.assertEqual(noop["sha256"], created["sha256"])

            changed = replace_asset(root, "icon.png", PNG_1X1_ALT, created["sha256"])
            self.assertNotEqual(changed["sha256"], created["sha256"])
            self.assertEqual(asset_state(root, "icon.png")["sha256"], changed["sha256"])

            with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                replace_asset(root, "icon.png", PNG_1X1, created["sha256"])

    def test_create_never_overwrites_and_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_asset(root, "Texture.png", PNG_1X1)
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_asset(root, "Texture.png", PNG_1X1_ALT)
            with self.assertRaisesRegex(ValueError, "Invalid tModLoader asset path"):
                create_asset(root, "../Outside.png", PNG_1X1)
            with self.assertRaisesRegex(ValueError, "ignored/generated"):
                create_asset(root, "obj/Texture.png", PNG_1X1)
            with self.assertRaisesRegex(ValueError, "Invalid tModLoader asset path"):
                create_asset(root, "Content/readme.txt", b"text")

    def test_known_audio_and_compiled_asset_extensions_are_inventoried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE"
            create_asset(root, "Sounds/Test.wav", wav)
            create_asset(root, "Effects/Test.fxc", b"compiled-effect")
            create_asset(root, "Textures/Test.rawimg", b"raw-image")
            create_asset(root, "Compiled/Test.xnb", b"XNBw")
            rows = {row["path"]: row for row in asset_index(root)["files"]}
            self.assertEqual(rows["Sounds/Test.wav"]["preview"], "audio")
            self.assertEqual(rows["Effects/Test.fxc"]["kind"], "effect")
            self.assertEqual(rows["Textures/Test.rawimg"]["kind"], "image-compiled")
            self.assertEqual(rows["Compiled/Test.xnb"]["kind"], "compiled")

    def test_signature_validation_catches_mislabeled_preview_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "PNG signature"):
                create_asset(root, "Bad.png", b"not-png")
            with self.assertRaisesRegex(ValueError, "RIFF/WAVE"):
                create_asset(root, "Bad.wav", b"not-wav")
            with self.assertRaisesRegex(ValueError, "Ogg"):
                create_asset(root, "Bad.ogg", b"not-ogg")

    def test_service_create_read_replace_and_stale_refusal_use_selected_project(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                root.mkdir()
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)

                created = server.create_asset_file("Content/Sword.png", PNG_1X1)
                self.assertEqual(created["path"], "Content/Sword.png")
                self.assertEqual([row["path"] for row in server.assets_state()["files"]], ["Content/Sword.png"])

                data, state = server.asset_content("Content/Sword.png")
                self.assertEqual(data, PNG_1X1)
                self.assertEqual(state["sha256"], created["sha256"])

                replaced = server.replace_asset_file(
                    "Content/Sword.png",
                    PNG_1X1_ALT,
                    created["sha256"],
                )
                self.assertNotEqual(replaced["sha256"], created["sha256"])
                self.assertEqual(server.asset_file("Content/Sword.png")["sha256"], replaced["sha256"])

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.replace_asset_file("Content/Sword.png", PNG_1X1, created["sha256"])
                with self.assertRaisesRegex(ValueError, "Invalid tModLoader asset path"):
                    server.asset_file("../Outside.png")
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
