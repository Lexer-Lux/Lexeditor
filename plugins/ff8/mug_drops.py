"""Optional normal item drops after a successful Mug, without repeat stealing.

Supported Steam English FF8_EN.exe:
064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570.
The reward builder reads DAT drop chance at +14D and the tier's four pairs at
+134. Its early test at 00486666 skips drops on actor flags bit 0800. The Mug
success path sets precisely that bit at 0049073A; its already-stolen check at
004906CB and the death-reward-once bit 40000 at 00494903 remain untouched.
"""
from __future__ import annotations

DROP_SUPPRESSION_MASK = 0x00486668
ORIGINAL = b'\x08'
PATCHED = b'\x00'
GUARDS = (
    (0x00486666, bytes.fromhex('F6 C5 08 0F 85 D7 00 00 00')),
    (0x004906CB, bytes.fromhex('F6 C4 08 74 07')),
    (0x0049073A, bytes.fromhex('80 CD 08')),
    (0x00494903, bytes.fromhex('F7 86 8C 7B D2 01 00 00 04 00')),
)


def verify_executable(stream) -> None:
    for address, expected in GUARDS:
        stream.seek(address - 0x400000)
        if stream.read(len(expected)) != expected:
            raise ValueError(f'Unsupported Mug/drop executable seam at {address:08X}')


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError('Drops After Mug must be true or false')
    if not enabled:
        return ''
    return '# Drops After Mug: retain normal drop rolls; keep Mug-once and reward-once flags.\n486668 = 00\n'
