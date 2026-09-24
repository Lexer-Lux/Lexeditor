"""Native SFX/music split anchors for issue #498.

The research is static analysis of FF8_EN.exe; these tests stay hermetic
by planting the pinned byte patterns in synthetic buffers. A live run
against the installed executable matched all six anchors on 2026-09-23.
"""
import unittest

from plugins.ff8 import audio_split_issue_498 as audio


def _image_with(probes):
    size = 0x470000
    image = bytearray(b"\x00" * size)
    for va, blob in probes:
        start = va - audio.IMAGE_BASE
        image[start:start + len(blob)] = blob
    return bytes(image)


class ClampTests(unittest.TestCase):
    def test_menu_volume_accepts_whole_0_to_100(self):
        self.assertEqual(audio.clamp_menu_volume(0), 0)
        self.assertEqual(audio.clamp_menu_volume(100), 100)
        for bad in (True, False, -1, 101, "80", 80.0, None, [], {}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                audio.clamp_menu_volume(bad)

    def test_channel_volume_accepts_whole_0_to_127(self):
        self.assertEqual(audio.clamp_channel_volume(0), 0)
        self.assertEqual(audio.clamp_channel_volume(127), 127)
        for bad in (True, -1, 128, "64", 64.0, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                audio.clamp_channel_volume(bad)


class ScalingTests(unittest.TestCase):
    def test_scaling_matches_integer_division_everywhere(self):
        for volume in range(128):
            for master in range(101):
                self.assertEqual(
                    audio.scaled_channel_volume(volume, master),
                    (volume * master) // 100, (volume, master))

    def test_endpoints(self):
        self.assertEqual(audio.scaled_channel_volume(127, 100), 127)
        self.assertEqual(audio.scaled_channel_volume(127, 0), 0)
        self.assertEqual(audio.scaled_channel_volume(0, 100), 0)

    def test_rejects_out_of_range_inputs(self):
        with self.assertRaises(ValueError):
            audio.scaled_channel_volume(128, 100)
        with self.assertRaises(ValueError):
            audio.scaled_channel_volume(64, 101)


class CallEncodingTests(unittest.TestCase):
    def test_forward_call(self):
        self.assertEqual(audio.call_bytes(0x004EE284, 0x0046A470),
                         bytes.fromhex("E8 E7 C1 F7 FF"))

    def test_backward_call_round_trip(self):
        caller, target = 0x0046A939, 0x0046A480
        encoded = audio.call_bytes(caller, target)
        import struct
        relative = struct.unpack("<i", encoded[1:])[0]
        self.assertEqual(caller + 5 + relative, target)

    def test_rejects_bad_addresses(self):
        for bad in (-1, 0x100000000, "0x46a470", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                audio.call_bytes(bad, 0x0046A470)


class ProbeTests(unittest.TestCase):
    def test_matching_image_reports_no_errors(self):
        image = _image_with(
            (va, blob) for _, va, blob in audio.PROBES)
        self.assertEqual(audio.verify_probes(image), [])

    def test_corrupted_anchor_is_reported(self):
        image = bytearray(_image_with(
            (va, blob) for _, va, blob in audio.PROBES))
        _, va, blob = audio.PROBES[0]
        start = va - audio.IMAGE_BASE
        image[start] ^= 0xFF
        errors = audio.verify_probes(bytes(image))
        self.assertEqual(len(errors), 1)
        self.assertIn("set-master entry", errors[0])

    def test_truncated_image_is_reported_not_crash(self):
        errors = audio.verify_probes(b"\x00" * 16)
        self.assertEqual(len(errors), len(audio.PROBES))

    def test_rejects_non_bytes(self):
        with self.assertRaises(ValueError):
            audio.verify_probes("not bytes")


if __name__ == "__main__":
    unittest.main()
