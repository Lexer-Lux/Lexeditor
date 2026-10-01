"""Bounded, deterministic preview scheduling for GF cinematic resources."""
import struct

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
        if instruction.code == 6 and instruction.op & 0x8000:
            slot = (instruction.op >> 9) & 63
            if slot & 32:
                # Shared page loads replace the last-upload source even though
                # they do not replace a summon-specific file slot.
                self._last_load = f'ma8def_p.{slot & 31}'


def simulate(data: bytes) -> PreviewSimulation:
    if not 48 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError('Summon script size is outside the supported bounds')
    root, = struct.unpack_from('<I', data, 4)
    if root < 48 or root >= len(data) or root % 2:
        raise ValueError('Summon root script is outside the file')
    return PreviewSimulation(data, root, max_ticks=3000, target_count=1, seed=0)
