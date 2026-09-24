"""FF8 field cameras, movie cameras, and INF header/range editing.

Covers Deling's CaFile/MskFile/InfFile ground the Field tab edits: reads
accept only proved sizes, writes patch proved scalars in place, and mod
merges compose per scalar with a visible whole-file fallback.
"""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.ff8 import field_camera, field_data, field_movie, runtime_layout


def _ca(zoom=400):
    return (struct.pack("<9h", 4096, 0, 0, 0, 4096, 0, 0, 0, 4096)
            + struct.pack("<h", 4096)
            + struct.pack("<3i", 1000, 2000, 3000)
            + struct.pack("<i", 0)
            + struct.pack("<2H", zoom, zoom))


def _msk(*frames):
    body = b"".join(struct.pack("<12h", *[c for point in frame for c in point])
                    for frame in frames)
    return struct.pack("<I", len(frames)) + body


def _inf676():
    raw = bytearray(676)
    raw[0:7] = b"bghall1"
    raw[9] = 128
    struct.pack_into("<H", raw, 16, 12)
    struct.pack_into("<h", raw, 18, 200)
    for slot in range(8):
        struct.pack_into("<hhhh", raw, 20 + slot * 8, -112, 112, 160, -160)
    for slot in range(2):
        struct.pack_into("<hhhh", raw, 84 + slot * 8, 0, 224, 320, 0)
    return bytes(raw)


class CameraTests(unittest.TestCase):
    def test_read_round_trips_a_camera(self):
        parsed = field_camera.read(_ca())
        self.assertEqual(parsed["cameraCount"], 1)
        camera = parsed["cameras"][0]
        self.assertEqual(camera["axis"][0], {"x": 4096, "y": 0, "z": 0})
        self.assertEqual(camera["position"], {"x": 1000, "y": 2000, "z": 3000})
        self.assertEqual(camera["zoom"], 400)

    def test_legacy_camera_reads_but_saves_padded(self):
        parsed = field_camera.read(_ca()[:38])
        self.assertEqual(parsed["cameraCount"], 1)
        raw, changed = field_camera.apply_edits(
            _ca()[:38], [{"camera": 0, "field": "zoom", "value": 500}])
        self.assertEqual(len(raw), 40)
        self.assertEqual(changed, 1)
        self.assertEqual(field_camera.read(raw)["cameras"][0]["zoom"], 500)

    def test_odd_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported field camera size"):
            field_camera.read(bytes(39))

    def test_edits_patch_scalars_and_refresh_padding(self):
        raw = bytearray(_ca())
        struct.pack_into("<H", raw, 38, 0)  # stale zoom padding copy
        edited, changed = field_camera.apply_edits(bytes(raw), [
            {"camera": 0, "field": "axis0", "axis": "x", "value": 100},
            {"camera": 0, "field": "position", "axis": "y", "value": -5},
            {"camera": 0, "field": "zoom", "value": 401},
        ])
        self.assertEqual(changed, 3)
        camera = field_camera.read(edited)["cameras"][0]
        self.assertEqual(camera["axis"][0]["x"], 100)
        self.assertEqual(camera["position"]["y"], -5)
        self.assertEqual(struct.unpack_from("<2H", edited, 36), (401, 401))

    def test_zoom_zero_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be 1 to 65535"):
            field_camera.apply_edits(_ca(), [{"camera": 0, "field": "zoom", "value": 0}])

    def test_duplicate_and_unknown_edits_are_rejected(self):
        edit = {"camera": 0, "field": "zoom", "value": 401}
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            field_camera.apply_edits(_ca(), [edit, edit])
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            field_camera.apply_edits(_ca(), [{"camera": 9, "field": "zoom", "value": 1}])

    def test_merge_composes_scalars_and_names_conflicts(self):
        vanilla = _ca()
        mod_a, _ = field_camera.apply_edits(
            vanilla, [{"camera": 0, "field": "zoom", "value": 401}])
        mod_b, _ = field_camera.apply_edits(
            vanilla, [{"camera": 0, "field": "position", "axis": "x", "value": 7}])
        merged, conflicts, reason = field_camera.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.ca")
        self.assertEqual(reason, "")
        self.assertEqual(conflicts, [])
        camera = field_camera.read(merged)["cameras"][0]
        self.assertEqual((camera["zoom"], camera["position"]["x"]), (401, 7))
        mod_c, _ = field_camera.apply_edits(
            vanilla, [{"camera": 0, "field": "zoom", "value": 402}])
        merged, conflicts, _ = field_camera.merge(
            vanilla, [("mod-a", mod_a), ("mod-c", mod_c)], "direct/x/y/y.ca")
        self.assertEqual(field_camera.read(merged)["cameras"][0]["zoom"], 402)
        self.assertEqual(conflicts[0]["winner"], "mod-c")
        self.assertIsNone(field_camera.merge(
            vanilla, [("mod-a", mod_a + _ca())], "direct/x/y/y.ca")[0])

    def test_compose_routes_camera_and_movie_paths(self):
        self.assertTrue(runtime_layout.FIELD_CAMERA_PATH.match(
            "direct/field/mapdata/grp/mapa/mapa.ca"))
        self.assertTrue(runtime_layout.FIELD_MOVIE_PATH.match(
            "direct/field/mapdata/grp/mapa/mapa.msk"))
        self.assertFalse(runtime_layout.FIELD_CAMERA_PATH.match(
            "direct/field/mapdata/grp/mapa/mapa.msk"))


class MovieTests(unittest.TestCase):
    FRAME = [(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)]

    def test_read_round_trips_frames(self):
        parsed = field_movie.read(_msk(self.FRAME, self.FRAME))
        self.assertEqual(parsed["frameCount"], 2)
        self.assertEqual(parsed["frames"][1]["points"][3], {"x": 10, "y": 11, "z": 12})

    def test_count_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "declares 2 frames"):
            field_movie.read(struct.pack("<I", 2) + bytes(24))

    def test_edits_patch_vertices_in_place(self):
        raw, changed = field_movie.apply_edits(
            _msk(self.FRAME),
            [{"frame": 0, "point": 3, "axis": "z", "value": -12}])
        self.assertEqual(changed, 1)
        self.assertEqual(len(raw), len(_msk(self.FRAME)))
        self.assertEqual(field_movie.read(raw)["frames"][0]["points"][3]["z"], -12)
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            field_movie.apply_edits(_msk(self.FRAME), [
                {"frame": 0, "point": 0, "axis": "x", "value": 1},
                {"frame": 0, "point": 0, "axis": "x", "value": 2}])

    def test_merge_composes_vertices(self):
        vanilla = _msk(self.FRAME, self.FRAME)
        mod_a, _ = field_movie.apply_edits(
            vanilla, [{"frame": 0, "point": 0, "axis": "x", "value": 9}])
        mod_b, _ = field_movie.apply_edits(
            vanilla, [{"frame": 1, "point": 3, "axis": "z", "value": 9}])
        merged, conflicts, reason = field_movie.merge(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.msk")
        self.assertEqual((reason, conflicts), ("", []))
        frames = field_movie.read(merged)["frames"]
        self.assertEqual((frames[0]["points"][0]["x"], frames[1]["points"][3]["z"]), (9, 9))


class InfHeaderTests(unittest.TestCase):
    def test_full_variant_parses_header_and_ranges(self):
        parsed = field_data._parse_inf(_inf676())
        self.assertEqual(parsed["header"]["name"], "bghall1")
        self.assertEqual(
            (parsed["header"]["control"], parsed["header"]["pvp"], parsed["header"]["focus"]),
            (128, 12, 200))
        self.assertEqual(len(parsed["cameraRanges"]), 8)
        self.assertTrue(all(entry["present"] for entry in parsed["cameraRanges"]))
        self.assertEqual(parsed["cameraRanges"][0]["left"], -160)
        self.assertEqual(parsed["screenRanges"][1]["right"], 320)

    def test_short_variant_reports_absent_ranges_with_deling_defaults(self):
        parsed = field_data._parse_inf(bytes(504))
        self.assertIsNone(parsed["header"]["pvp"])
        self.assertEqual(parsed["header"]["pvpDefault"], 12)
        self.assertEqual(
            [entry["present"] for entry in parsed["cameraRanges"]],
            [True] + [False] * 7)
        self.assertEqual(parsed["cameraRanges"][7]["left"], -160)
        self.assertEqual([entry["present"] for entry in parsed["screenRanges"]],
                         [False, False])
        self.assertEqual(parsed["screenRanges"][0]["bottom"], 224)

    def test_misc_and_range_edits_apply(self):
        raw = field_data._edit_inf_bytes(_inf676(), [
            {"kind": "misc", "field": "control", "value": 129},
            {"kind": "misc", "field": "pvp", "value": 13},
            {"kind": "misc", "field": "focus", "value": 201},
            {"kind": "cameraRange", "slot": 7, "field": "left", "value": -159},
            {"kind": "screenRange", "slot": 1, "field": "right", "value": 321},
        ])
        self.assertEqual(len(raw), 676)
        parsed = field_data._parse_inf(raw)
        self.assertEqual(
            (parsed["header"]["control"], parsed["header"]["pvp"], parsed["header"]["focus"]),
            (129, 13, 201))
        self.assertEqual(parsed["cameraRanges"][7]["left"], -159)
        self.assertEqual(parsed["screenRanges"][1]["right"], 321)

    def test_absent_range_edits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            field_data._edit_inf_bytes(bytes(504), [
                {"kind": "cameraRange", "slot": 7, "field": "left", "value": 0}])
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            field_data._edit_inf_bytes(bytes(504), [
                {"kind": "misc", "field": "pvp", "value": 12}])

    def test_range_edits_compose_with_entrance_edits(self):
        vanilla = _inf676()
        mod_a = field_data._edit_inf_bytes(vanilla, [
            {"kind": "cameraRange", "slot": 0, "field": "top", "value": -111}])
        mod_b = field_data._edit_inf_bytes(vanilla, [
            {"kind": "gateway", "slot": 0, "field": "fieldId", "value": 5}])
        merged, conflicts, reason = field_data.merge_inf(
            vanilla, [("mod-a", mod_a), ("mod-b", mod_b)], "direct/x/y/y.inf")
        self.assertEqual((reason, conflicts), ("", []))
        parsed = field_data._parse_inf(merged)
        self.assertEqual(parsed["cameraRanges"][0]["top"], -111)
        self.assertEqual(parsed["gateways"][0]["fieldId"], 5)

    def test_save_writes_camera_and_movie_edits(self):
        row = {"id": 1, "key": "grp/mapa", "name": "mapa", "group": "grp",
               "mapId": None, "listed": False}
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            camera_path = root / "mapa.ca"
            camera_path.write_bytes(_ca())
            movie_path = root / "mapa.msk"
            movie_path.write_bytes(_msk(self.FRAME if hasattr(self, "FRAME") else
                                         [(0, 0, 0)] * 4))
            with patch.object(field_data, "_map_row", return_value=row), \
                 patch.object(field_data, "_camera_source_path",
                              return_value=camera_path), \
                 patch.object(field_data, "_movie_source_path",
                              return_value=movie_path), \
                 patch.object(field_data.paths, "DIRECT_ROOT", root / "direct"):
                result = field_data.save([
                    {"type": "camera", "map": "grp/mapa", "camera": 0,
                     "field": "zoom", "value": 401},
                    {"type": "movie", "map": "grp/mapa", "frame": 0,
                     "point": 0, "axis": "x", "value": 9},
                ])
            self.assertEqual(result["maps"], 1)
            self.assertEqual(result["saved"], 2)
            written_ca = root / "direct" / "field" / "mapdata" / "grp" / "mapa" / "mapa.ca"
            self.assertEqual(field_camera.read(written_ca.read_bytes())["cameras"][0]["zoom"], 401)


ROOT = Path(__file__).resolve().parents[1]


class SaveWiringTests(unittest.TestCase):
    """The Field tab's save diff emits every edit type its pages produce."""

    def test_save_diff_covers_camera_movie_and_inf_extras(self):
        diff = (ROOT / "plugins" / "ff8" / "boot.js").read_text(encoding="utf-8")
        for marker in ('type:"camera"', 'type:"movie"', 'kind:"misc"',
                       '"cameraRange"', '"screenRange"', '"axis"+vector',
                       "row.camera?.cameras", "row.movie?.frames"):
            self.assertIn(marker, diff)

    def test_field_pages_use_defined_helpers_and_payload_shapes(self):
        source = (ROOT / "plugins" / "ff8" / "places.js").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?<![\w$])Detail(?:Field|Section)\(")
        self.assertIn("value?.axis?.[vector]?.[axis]", source)
        self.assertIn("target.axis[vector][axis]", source)
