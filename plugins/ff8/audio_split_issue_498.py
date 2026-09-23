"""Native SFX/music volume split for GitHub issue #498.

Statically proved against the installed FF8_EN.exe (SHA-256 starting
064d466b, the pinned executable). Virtual addresses below are absolute
(file offset equals RVA in .text/.data here; subtract IMAGE_BASE
0x400000 for file offsets).

Proved SFX side:
- MASTER_VOLUME_VA holds the SFX master gain. Audio init writes the
  default 100; the Config-menu Sound slider reads it through
  GET_MASTER_VA and clamps its own value 0-100.
- SET_MASTER_VA rejects values above 100 ("SOUND PARAMETER ERROR -
  sfx_set_master_volume ()"), writes the global, then re-applies the
  scaled gain to every live channel, so calling it moves currently
  playing sounds without a restart.
- SET_CHANNEL_VA takes (channel 0-31, volume 0-127) and scales the
  channel by master/100 before the DirectSound call.
- SET_ALL_VA fans one 0-127 value out across all 32 channels.

Proved music side (entry points, no master global found):
- MUSIC_LOG_PUSH_VA pushes the "sd_music_play (number=%d, song_id=%d,
  volume=%d)" format inside the music command dispatcher, and the
  BdPlayStream/BdPlayStream3D calls carry their own volume argument:
  music volume is per-play, separate from the SFX master.

Backend finding: with use_external_sfx/music off (this machine's
FFNx.toml), the FFNx external gains only scale external files, so they
do not move vanilla audio; the exe master above does. Audible proof of
each slider's isolation and of restart persistence still needs a game
session, so this module installs no bytes.
"""

from __future__ import annotations

IMAGE_BASE = 0x400000

# SFX master gain (absolute VA of the global dword).
MASTER_VOLUME_VA = 0x01CD1794
MASTER_DEFAULT = 100
MASTER_MAXIMUM = 100

# sfx_set_master_volume(value): entry validates 0-100, writes the global,
# re-applies to live channels.
SET_MASTER_VA = 0x0046A390
# get_master_volume(): returns the global; read by the Config-menu slider.
GET_MASTER_VA = 0x0046A470
# sfx_set_volume(channel, volume): channel 0-31, volume 0-127.
SET_CHANNEL_VA = 0x0046A480
# sfx_set_volume_all(volume): all 32 channels.
SET_ALL_VA = 0x0046A8E0
# Config-menu Sound slider read of the master gain.
MENU_READER_VA = 0x004EE284
# sd_music_play format-string push inside the music dispatcher.
MUSIC_LOG_PUSH_VA = 0x0046B596

CHANNEL_COUNT = 32
CHANNEL_MAXIMUM = 127
CHANNEL_STRUCT_BASE_VA = 0x01CD0B00
CHANNEL_STRUCT_STRIDE = 0x60
CHANNEL_VOLUME_OFFSET = 0x28

# (name, absolute VA, expected leading bytes) pinned by verify_probes().
PROBES = (
    ("set-master entry", SET_MASTER_VA, bytes.fromhex("A1 E8 0A CD 01")),
    ("get-master entry", GET_MASTER_VA, bytes.fromhex("A1 94 17 CD 01 C3")),
    ("set-channel string push", 0x0046A48C, bytes.fromhex("68 68 F2 B7 00")),
    ("music log string push", MUSIC_LOG_PUSH_VA, bytes.fromhex("68 70 F5 B7 00")),
    ("menu reader call", MENU_READER_VA, bytes.fromhex("E8 E7 C1 F7 FF")),
    ("init default master", 0x0046966A, bytes.fromhex("C7 05 94 17 CD 01 64 00 00 00")),
)


def _clean_gain(value: object, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number from 0 to {maximum}")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must be a whole number from 0 to {maximum}")
    return value


def clamp_menu_volume(value: object) -> int:
    """Validate a Config-menu slider value: whole 0-100, like the exe."""
    return _clean_gain(value, MASTER_MAXIMUM, "Menu volume")


def clamp_channel_volume(value: object) -> int:
    """Validate a per-channel SFX value: whole 0-127, like the exe."""
    return _clean_gain(value, CHANNEL_MAXIMUM, "Channel volume")


def scaled_channel_volume(volume: int, master: int) -> int:
    """Replicate the exe's volume*master/100 fixed-point scaling.

    The exe multiplies by 0x51EB851F and shifts right 37; over the
    0-127 by 0-100 domain that equals integer division by 100.
    """
    volume = clamp_channel_volume(volume)
    master = clamp_menu_volume(master)
    return ((volume * master * 0x51EB851F) >> 37) & 0xFFFFFFFF


def call_bytes(caller_va: int, target_va: int) -> bytes:
    """Encode an E8 near call from caller to target for a future patch."""
    for name, va in (("caller", caller_va), ("target", target_va)):
        if not isinstance(va, int) or va < 0 or va > 0xFFFFFFFF:
            raise ValueError(f"{name} address out of range: {va!r}")
    relative = (target_va - (caller_va + 5)) & 0xFFFFFFFF
    if relative >= 0x80000000:
        relative -= 0x100000000
    import struct
    return b"\xE8" + struct.pack("<i", relative)


def verify_probes(exe_bytes: bytes, base: int = IMAGE_BASE) -> list[str]:
    """Check the pinned byte patterns against executable bytes.

    Returns a list of mismatch descriptions; empty means every anchor
    matched. Takes raw bytes so tests stay hermetic.
    """
    errors = []
    if not isinstance(exe_bytes, (bytes, bytearray)):
        raise ValueError("Executable bytes required")
    for name, va, expected in PROBES:
        offset = va - base
        actual = bytes(exe_bytes[offset:offset + len(expected)])
        if actual != expected:
            errors.append(
                f"{name} at {va:#010x}: expected {expected.hex(' ')}, "
                f"found {actual.hex(' ') or 'past end of input'}"
            )
    return errors
