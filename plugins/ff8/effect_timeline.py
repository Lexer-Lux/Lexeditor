"""Bounded, deterministic preview scheduling for GF cinematic resources."""
import struct
from functools import lru_cache

from .vendor.ff8ue.magcine.cinesim import CineSimulation


class PreviewSimulation(CineSimulation):
    MAX_INSTRUCTIONS = 1000000
    MAX_BONES = 4096

    def _decode(self, offset):
        self._preview_instructions = getattr(self, '_preview_instructions', 0) + 1
        if self._preview_instructions > self.MAX_INSTRUCTIONS:
            raise ValueError('Summon preview exceeded its instruction budget')
        return super()._decode(offset)

    def _spawn(self, parent, program, at, bone_id=None):
        if len(self.bones) >= self.MAX_BONES:
            raise ValueError('Summon preview exceeded its object budget')
        return super()._spawn(parent, program, at, bone_id)

    def _record_props(self, bone, instruction):
        super()._record_props(bone, instruction)
        if instruction.code in (0x3C, 0x56):
            bone.props.append((self.tick, 'mesh', instruction.words[0] & 65535))
            bone.props.append((self.tick, 'draw', 2 if instruction.code == 0x3C else 9))
        if instruction.code == 0xB2:
            self._file_slot_base = instruction.words[0] & 255
        elif instruction.code == 6:
            slot = (instruction.op >> 9) & 63
            if instruction.op & 0x8000 and slot & 32:
                # Shared page loads replace the last-upload source even though
                # they do not replace a summon-specific file slot.
                self._last_load = f'ma8def_p.{slot & 31}'
            else:
                slot += getattr(self, '_file_slot_base', 0)
                if not 0 <= slot < 64:
                    raise ValueError('Summon file slot is outside the supported range')
                self._last_load = slot


def simulate(data: bytes) -> PreviewSimulation:
    if not 48 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError('Summon script size is outside the supported bounds')
    root, = struct.unpack_from('<I', data, 4)
    if root < 48 or root >= len(data) or root % 2:
        raise ValueError('Summon root script is outside the file')
    return PreviewSimulation(data, root, max_ticks=3000, target_count=1, seed=0)


@lru_cache(maxsize=8)
def texture_uploads(data: bytes) -> tuple:
    """Cache only upload events, keyed by the actual script bytes."""
    return tuple(simulate(data).vram_events)
