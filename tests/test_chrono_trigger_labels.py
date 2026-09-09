from __future__ import annotations

from types import SimpleNamespace
import unittest

from games.chrono_trigger.labels import (
    decorate_scene_exits,
    decorate_scenes,
    decorate_treasure,
    decorate_world_table,
    label_bundle,
)


class _Store:
    def __init__(self, rows: dict[str, bytes]):
        self.rows = rows
        self.archive = SimpleNamespace(entries=[SimpleNamespace(path=path) for path in rows])

    def read(self, path: str, _source: str):
        if path not in self.rows:
            raise KeyError(path)
        return self.rows[path], "archive"


class LabelTests(unittest.TestCase):
    def _store(self):
        debug = b"0000,Millennial Fair\n0001,Guardia Forest\n0002,Guardia Castle\n"
        world_lines = [f"{index:04d},Exit {index}" for index in range(106)]
        world_lines += [
            "0106,Present", "0107,Middle Ages", "0108,Future",
            "0109,Prehistory", "0110,Antiquity", "0111,End of Time",
        ]
        return _Store({
            "Localize/fr/msg/debug_map.txt": b"0000,Foire\n",
            "Localize/en/msg/debug_map.txt": debug,
            "Localize/en/msg/w_map.txt": ("\n".join(world_lines) + "\n").encode(),
            "Localize/en/msg/item.txt": b"0000,Wood Sword\n0001,Bronze Bow\n0002,Tonic\n",
            "Localize/en/msg/player.txt": b"0000,Crono\n0001,Marle\n",
        })

    def test_prefers_english_and_builds_ctviewer_world_order(self):
        labels = label_bundle(self._store())
        self.assertEqual(labels["languages"]["scenes"], "en")
        self.assertEqual(labels["sceneNames"][1], "Millennial Fair")
        self.assertEqual(labels["worldNames"], [
            "Present", "Middle Ages", "Future", "Prehistory",
            "Antiquity", "Antiquity", "Antiquity", "End of Time",
        ])
        self.assertEqual(labels["worldExitNames"][7], "Exit 7")
        self.assertEqual(labels["itemNames"][2], "Tonic")
        self.assertEqual(labels["playerNames"][0], "Crono")

    def test_decorates_ids_without_removing_raw_values(self):
        labels = label_bundle(self._store())
        scenes = {"rows": [{"id": 1, "name": "Scene 0001"}]}
        decorate_scenes(scenes, labels)
        self.assertEqual(scenes["rows"][0]["name"], "Millennial Fair")

        exits = {"rows": [{"values": {"destination": 2}, "derived": {}}]}
        decorate_scene_exits(exits, labels)
        self.assertEqual(exits["rows"][0]["values"]["destination"], 2)
        self.assertEqual(exits["rows"][0]["derived"]["destinationName"], "Guardia Forest")

        treasure = {"rows": [{"values": {"contents": 2}, "derived": {"itemId": 2}}]}
        decorate_treasure(treasure, labels)
        self.assertEqual(treasure["rows"][0]["derived"]["itemName"], "Tonic")

        world = {"exits": [{
            "values": {"nameIndex": 7, "sceneIndex": 2}, "derived": {"scripted": False},
        }]}
        decorate_world_table(world, labels)
        self.assertEqual(world["exits"][0]["derived"]["exitName"], "Exit 7")
        self.assertEqual(world["exits"][0]["derived"]["destinationName"], "Guardia Forest")

    def test_missing_files_fall_back_cleanly(self):
        labels = label_bundle(_Store({}))
        self.assertEqual(labels["worldNames"][0], "World 0")
        self.assertEqual(labels["itemNames"], [])


if __name__ == "__main__":
    unittest.main()
