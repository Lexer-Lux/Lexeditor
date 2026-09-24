import unittest
from PIL import Image
from tools.prepare_rdr2_gold_cores import masks


class CoreMasksTests(unittest.TestCase):
    def test_grey_area_is_transparent_and_fill_grows_upward(self):
        states = []
        for i in range(16):
            image = Image.new('RGBA', (2, 16), (100, 100, 100, 255))
            for y in range(16):
                image.putpixel((1, y), (255, 255, 255, 0))
                if y >= 16-i:
                    image.putpixel((0, y), (250, 250, 250, 255))
            if i == 15:
                image.putpixel((0, 0), (250, 250, 250, 255))
            states.append(image)
        base, frames = masks(states)
        self.assertEqual(frames[0].getchannel('A').getextrema(), (0, 0))
        self.assertEqual(base.getpixel((0, 0)), (255, 255, 255, 255))
        self.assertEqual(frames[7].getpixel((0, 0))[3], 0)
        self.assertEqual(frames[7].getpixel((0, 15))[3], 255)
        for frame in frames:
            self.assertTrue(all(frame.getpixel((1, y))[3] == 0 for y in range(16)))
        self.assertEqual(frames[-1].tobytes(), base.tobytes())

    def test_incomplete_or_mixed_size_art_is_rejected(self):
        with self.assertRaises(ValueError):
            masks([Image.new('RGBA', (2, 2))])
        with self.assertRaises(ValueError):
            masks([Image.new('RGBA', (2, 2))]*15+[Image.new('RGBA', (3, 2))])
