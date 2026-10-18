"""FMOD interface banks: FSB4 stream tables and extraction.

Layout probed from the installed ``sound/frpg_sm*.fsb`` banks (read-only;
no FMOD code or documentation is copied): ``FSB4`` magic, a stream count,
then one 80-byte sample header per stream (name, sample count, payload
size, sample rate), then the payloads back to back. Payloads are MPEG
audio (MPEG-1 Layer III frame syncs, LAME tags, 44100 Hz), so browsers
play extracted streams directly. Banks reach 126 MB: the table reads
headers only, and streams are seek-read one at a time under a bound.
"""
import struct
from pathlib import Path

from .formats import FormatError

HEADER_SIZE = 48
SAMPLE_HEADER = 80
MAX_STREAMS = 20000
MAX_STREAM = 64 * 1024 * 1024


class FsbError(FormatError):
    """The bank is not a readable FSB4 interface bank."""


def parse_table(path):
    """[{name, offset, size, samples, rate, duration}] in bank order."""
    path = Path(path)
    try:
        with path.open("rb") as stream:
            header = stream.read(HEADER_SIZE)
            if len(header) < HEADER_SIZE or header[:4] != b"FSB4":
                raise FsbError("That is not an FSB4 sound bank")
            _magic, count, _shdr, _data = struct.unpack_from("<4sIII", header, 0)
            if not 1 <= count <= MAX_STREAMS:
                raise FsbError("That FSB4 bank names no readable streams")
            entries = []
            for _ in range(count):
                raw = stream.read(SAMPLE_HEADER)
                if len(raw) < SAMPLE_HEADER:
                    raise FsbError("That FSB4 bank ends inside its stream table")
                if struct.unpack_from("<H", raw, 0)[0] != SAMPLE_HEADER:
                    raise FsbError("That FSB4 bank has an unproven sample header")
                name = raw[2:32].split(b"\0")[0].decode("ascii", "replace")
                samples, size = struct.unpack_from("<II", raw, 32)
                (rate,) = struct.unpack_from("<I", raw, 52)
                if size > MAX_STREAM or not name:
                    raise FsbError("That FSB4 bank has an unproven sample header")
                entries.append({"name": name, "size": size, "samples": samples,
                                "rate": rate})
            offset = HEADER_SIZE + count * SAMPLE_HEADER
            for entry in entries:
                entry["offset"] = offset
                entry["duration"] = entry["samples"] / entry["rate"] if entry["rate"] else 0.0
                offset += entry["size"]
    except OSError as error:
        raise FsbError(f"That sound bank cannot be read ({error})") from error
    return entries


# MPEG-1 Layer III frame sizing, from the frame header: the installed
# banks encode at 160 kbps / 44100 Hz, but the walker trusts each
# header so variable bitrates stay aligned.
_MPEG1_L3_BITRATE = (None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160,
                     192, 224, 256, 320, None)
_MPEG1_RATE = (44100, 48000, 32000, None)
_MAX_PAD = 16


def _frame_length(head):
    """One MPEG-1 Layer III frame's byte length, or None when the four
    header bytes are not one."""
    if len(head) < 4 or head[0] != 0xFF or head[1] & 0xE0 != 0xE0:
        return None
    if (head[1] >> 3) & 3 != 3 or (head[1] >> 1) & 3 != 1:
        return None
    bitrate = _MPEG1_L3_BITRATE[(head[2] >> 4) & 15]
    rate = _MPEG1_RATE[(head[2] >> 2) & 3]
    if bitrate is None or rate is None:
        return None
    return (144 * bitrate * 1000) // rate + ((head[2] >> 1) & 1)


def extract_mp3(path, entry):
    """One stream as clean MPEG bytes: FMOD slots every frame into a
    fixed stride, and the 1-2 filler bytes between frames (usually
    zeros) make strict players reject the stream, so the walker
    copies header-sized frames and skips the filler. The next frame
    is the first valid header within a few bytes past the declared
    length, pinned to the first frame's version, layer and rate, so
    coincidental sync words in frame data or filler cannot misalign
    it. A truncated trailing frame carries no complete audio and is
    dropped, as decoders do."""
    payload = read_stream(path, entry)
    end = len(payload)
    # Frames start at the first valid MPEG header: some banks open
    # streams with a 16-byte primer of varying content (zeros, or
    # markers like the o7230 stream's 0a00fffb), others with the
    # first frame itself.
    pos = None
    for at in range(0, min(17, max(0, end - 3))):
        if _frame_length(payload[at:at + 4]) is not None:
            pos = at
            break
    if pos is None:
        raise FsbError("That sound stream holds no MPEG audio")
    out = bytearray()
    pinned = None
    while pos < end:
        head = payload[pos:pos + 4]
        length = _frame_length(head)
        if length is None or (pinned is not None and (head[1] & 0x0E, head[2] & 0x0C) != pinned):
            raise FsbError("That sound stream is not clean MPEG audio")
        if pinned is None:
            pinned = (head[1] & 0x0E, head[2] & 0x0C)
        if pos + length > end:
            break
        found = None
        for skip in range(_MAX_PAD + 1):
            candidate = pos + length + skip
            if candidate + 4 > end:
                break
            ahead = payload[candidate:candidate + 4]
            if _frame_length(ahead) is not None and (ahead[1] & 0x0E, ahead[2] & 0x0C) == pinned:
                found = candidate
                break
        if found is None:
            # Past the last frame only filler may remain: zeros, or a
            # few remnant bytes where the bank cut the stream.
            tail = payload[pos + length:].strip(b"\0")
            if len(tail) > 4:
                raise FsbError("That sound stream is not clean MPEG audio")
            out += payload[pos:pos + length]
            break
        out += payload[pos:pos + length]
        pos = found
    if not out:
        raise FsbError("That sound stream holds no MPEG audio")
    return bytes(out)


def read_stream(path, entry):
    """One stream's payload bytes, seek-read under the size bound."""
    size = int(entry["size"])
    if size > MAX_STREAM or size < 0:
        raise FsbError("That sound stream is outside the readable bound")
    try:
        with Path(path).open("rb") as stream:
            stream.seek(int(entry["offset"]))
            payload = stream.read(size)
    except OSError as error:
        raise FsbError(f"That sound bank cannot be read ({error})") from error
    if len(payload) != size:
        raise FsbError("That sound bank ends inside its stream data")
    return payload
