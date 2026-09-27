"""World-to-field edits compose by proven fields, with opaque tails atomic."""
import struct
import tempfile
import unittest
from pathlib import Path

from plugins.ff8 import fixed_data_merge, runtime_layout, wm2field


class Wm2fieldCompositionTests(unittest.TestCase):
    def test_independent_fields_priority_and_removal(self):
        raw = b''.join(struct.pack('<hhHH',i,-i,20,100+i)+bytes(range(16)) for i in range(72))
        first = wm2field.apply_edits(raw,[dict(id=0,x=40,y=0,z=20,fieldId=100)])
        second = wm2field.apply_edits(raw,[dict(id=0,x=0,y=80,z=20,fieldId=100)])
        third = wm2field.apply_edits(raw,[dict(id=0,x=90,y=0,z=20,fieldId=100)])
        with tempfile.TemporaryDirectory(prefix='ff8-wm2field-merge-') as directory:
            baseline = Path(directory)
            (baseline/'main').mkdir()
            (baseline/'main/wm2field.tbl').write_bytes(raw)
            def compose(mods):
                return runtime_layout._compose_logical_payload('direct/wm2field.tbl',mods,baseline,None,None)
            merged, mode, conflicts = compose([('first',first),('second',second)])
            self.assertEqual(mode,'semantic merge')
            self.assertFalse(conflicts)
            self.assertEqual(wm2field.parse(merged)['rows'][0],dict(id=0,token='wm2field:0',x=40,y=80,z=20,fieldId=100,pointer=0))
            self.assertEqual(merged[8:],raw[8:])
            merged, _, conflicts = compose([('first',first),('third',third)])
            self.assertEqual(wm2field.parse(merged)['rows'][0]['x'],90)
            self.assertEqual(conflicts[0]['winner'],'third')
            reordered, _, _ = compose([('third',third),('first',first)])
            self.assertEqual(wm2field.parse(reordered)['rows'][0]['x'],40)
            removed, _, _ = compose([('second',second)])
            self.assertEqual(removed,second)

    def test_reserved_tail_is_preserved_as_one_claim(self):
        raw = bytes(1728)
        low, high = bytearray(raw), bytearray(raw)
        low[8] = 1
        high[10] = 2
        spec = fixed_data_merge.SPECS['direct/wm2field.tbl']
        merged, conflicts = fixed_data_merge.merge(raw,[('low',bytes(low)),('high',bytes(high))],spec,'direct/wm2field.tbl')
        self.assertEqual(merged,bytes(high))
        self.assertEqual(conflicts[0]['unit'],'direct/wm2field.tbl:record:0:reserved')
        with self.assertRaisesRegex(ValueError,'record count'):
            fixed_data_merge.merge(raw[:-24],[],spec,'direct/wm2field.tbl')
        with self.assertRaisesRegex(ValueError,'fixed size'):
            fixed_data_merge.merge(raw,[('bad',raw[:-24])],spec,'direct/wm2field.tbl')


if __name__ == '__main__':
    unittest.main()
