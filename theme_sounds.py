"""Private extraction and reporting for game-themed interface sounds."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct


SOUND_SLOTS = ("confirm", "back", "move", "launch", "exit", "save")


def _audio_pair(game_root: Path, candidates: tuple[str, ...]) -> tuple[Path, Path] | None:
    for relative in candidates:
        fmt = game_root / relative / "audio.fmt"
        dat = game_root / relative / "audio.dat"
        if fmt.is_file() and dat.is_file():
            return fmt, dat
    return None


def _read_ff8_entries(fmt_path: Path) -> list[dict]:
    payload = fmt_path.read_bytes()
    if len(payload) < 2:
        raise ValueError(f"Invalid sound index: {fmt_path}")
    count = struct.unpack_from("<H", payload, 0)[0]
    position = 2
    entries: list[dict] = []
    for _index in range(count + 1):
        if position + 38 > len(payload):
            break
        length, offset, flags, _a, _b, _c, read_cursor, write_cursor = struct.unpack_from(
            "<IIBBBBII", payload, position
        )
        position += 20
        wave_format = payload[position:position + 18]
        tag, channels, rate, average, alignment, bits, extra_size = struct.unpack(
            "<HHIIHHH", wave_format
        )
        position += 18
        if position + extra_size > len(payload):
            raise ValueError(f"Truncated sound format record in {fmt_path}")
        extra = payload[position:position + extra_size]
        position += extra_size
        entries.append({
            "length": length, "offset": offset, "flags": flags,
            "readCursor": read_cursor, "writeCursor": write_cursor,
            "format": wave_format, "extra": extra, "tag": tag,
            "channels": channels, "rate": rate, "average": average,
            "alignment": alignment, "bits": bits,
        })
    return entries


def _read_ff7_entries(fmt_path: Path) -> list[dict]:
    payload = fmt_path.read_bytes()
    position = 0
    data_offset = 0
    entries: list[dict] = []
    for _index in range(750):
        if position + 24 > len(payload):
            break
        length, _stored_offset, loop, _count, start, end = struct.unpack_from(
            "<IIIIII", payload, position
        )
        position += 24
        if position + 18 > len(payload):
            raise ValueError(f"Truncated FF7 sound format record in {fmt_path}")
        wave_format = payload[position:position + 18]
        position += 18
        tag, channels, rate, average, alignment, bits, extra_size = struct.unpack(
            "<HHIIHHH", wave_format
        )
        extra = b""
        if length:
            if position + extra_size > len(payload):
                raise ValueError(f"Truncated FF7 ADPCM record in {fmt_path}")
            extra = payload[position:position + extra_size]
            position += extra_size
        entries.append({
            "length": length, "offset": data_offset, "flags": int(loop > 0),
            "readCursor": start, "writeCursor": end,
            "format": wave_format, "extra": extra, "tag": tag,
            "channels": channels, "rate": rate, "average": average,
            "alignment": alignment, "bits": bits,
        })
        data_offset += length
    return entries


def _wav(entry: dict, dat_path: Path) -> bytes:
    length = int(entry["length"])
    if length <= 0:
        raise ValueError("The selected game sound is empty")
    with dat_path.open("rb") as stream:
        stream.seek(int(entry["offset"]))
        data = stream.read(length)
    if len(data) != length:
        raise ValueError(f"Sound data is truncated in {dat_path}")
    if int(entry["tag"]) == 2:
        data = _decode_ms_adpcm(entry, data)
        channels = int(entry["channels"])
        rate = int(entry["rate"])
        alignment = channels * 2
        format_data = struct.pack("<HHIIHH", 1, channels, rate,
                                  rate * alignment, alignment, 16)
    else:
        format_data = entry["format"] + entry["extra"]
    riff_length = 4 + 8 + len(format_data) + 8 + len(data)
    return b"".join((
        b"RIFF", struct.pack("<I", riff_length), b"WAVE",
        b"fmt ", struct.pack("<I", len(format_data)), format_data,
        b"data", struct.pack("<I", len(data)), data,
    ))


_MS_ADPCM_ADAPTATION = (230, 230, 230, 230, 307, 409, 512, 614,
                        768, 614, 512, 409, 307, 230, 230, 230)


def _decode_ms_adpcm(entry: dict, payload: bytes) -> bytes:
    """Decode Microsoft's game-era ADPCM blocks to browser-safe PCM16."""
    channels = int(entry["channels"])
    block_alignment = int(entry["alignment"])
    extra = bytes(entry["extra"])
    if channels not in (1, 2) or block_alignment <= 0 or len(extra) < 4:
        raise ValueError("Unsupported Microsoft ADPCM format")
    coefficient_count = struct.unpack_from("<H", extra, 2)[0]
    if len(extra) < 4 + coefficient_count * 4:
        raise ValueError("Truncated Microsoft ADPCM coefficient table")
    coefficients = [struct.unpack_from("<hh", extra, 4 + index * 4)
                    for index in range(coefficient_count)]
    header_size = 7 * channels
    output = bytearray()

    def append_frame(values: list[int]) -> None:
        for value in values:
            output.extend(struct.pack("<h", max(-32768, min(32767, int(value)))))

    for block_start in range(0, len(payload), block_alignment):
        block = payload[block_start:block_start + block_alignment]
        if len(block) < header_size:
            continue
        position = 0
        predictors = list(block[position:position + channels])
        position += channels
        if any(index >= len(coefficients) for index in predictors):
            raise ValueError("Invalid Microsoft ADPCM predictor")
        deltas = list(struct.unpack_from(f"<{channels}h", block, position))
        position += channels * 2
        sample1 = list(struct.unpack_from(f"<{channels}h", block, position))
        position += channels * 2
        sample2 = list(struct.unpack_from(f"<{channels}h", block, position))
        position += channels * 2
        append_frame(sample2)
        append_frame(sample1)

        def decode_nibble(channel: int, raw_nibble: int) -> int:
            signed = raw_nibble - 16 if raw_nibble >= 8 else raw_nibble
            coefficient1, coefficient2 = coefficients[predictors[channel]]
            prediction = int((sample1[channel] * coefficient1
                              + sample2[channel] * coefficient2) / 256)
            value = max(-32768, min(32767, prediction + signed * deltas[channel]))
            sample2[channel], sample1[channel] = sample1[channel], value
            deltas[channel] = max(16,
                (_MS_ADPCM_ADAPTATION[raw_nibble] * deltas[channel]) // 256)
            return value

        if channels == 1:
            for encoded in block[position:]:
                append_frame([decode_nibble(0, encoded >> 4)])
                append_frame([decode_nibble(0, encoded & 0x0F)])
        else:
            for encoded in block[position:]:
                append_frame([decode_nibble(0, encoded >> 4),
                              decode_nibble(1, encoded & 0x0F)])
    return bytes(output)


def ensure_theme_sounds(game_root: Path, data_root: Path, candidates: tuple[str, ...],
                        sound_ids: dict[str, int | None], format_kind: str = "ff8") -> dict:
    """Extract proven numeric sound records into the plugin's private cache."""
    unknown = set(sound_ids) - set(SOUND_SLOTS)
    if unknown:
        raise ValueError(f"Unknown semantic sound slots: {', '.join(sorted(unknown))}")
    pair = _audio_pair(Path(game_root), candidates)
    output = Path(data_root) / "theme-sfx"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    if pair is None:
        return {"ready": False, "root": str(output), "rows": [
            {"slot": slot, "available": False, "sourceId": sound_ids.get(slot),
             "message": "The installed game sound archive was not found."}
            for slot in SOUND_SLOTS
        ]}
    fmt_path, dat_path = pair
    signature = {
        "fmt": [str(fmt_path), fmt_path.stat().st_size, fmt_path.stat().st_mtime_ns],
        "dat": [str(dat_path), dat_path.stat().st_size, dat_path.stat().st_mtime_ns],
        "ids": sound_ids,
        "format": format_kind,
        "decoder": 1,
    }
    manifest_path = output / "manifest.json"
    try:
        cached = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        cached = None
    entries = None
    for slot in SOUND_SLOTS:
        sound_id = sound_ids.get(slot)
        target = output / f"{slot}.wav"
        message = "No proven source sound is mapped."
        available = False
        if sound_id is not None:
            if cached != signature or not target.is_file():
                entries = entries or (
                    _read_ff7_entries(fmt_path) if format_kind == "ff7"
                    else _read_ff8_entries(fmt_path)
                )
                entry_index = sound_id - 1 if format_kind == "ff7" else sound_id
                if 0 <= entry_index < len(entries):
                    temporary = target.with_suffix(".wav.tmp")
                    temporary.write_bytes(_wav(entries[entry_index], dat_path))
                    os.replace(temporary, target)
            available = target.is_file()
            message = (
                f"Extracted from numeric sound ID {sound_id}."
                if available else f"Numeric sound ID {sound_id} is unavailable."
            )
        rows.append({
            "slot": slot, "available": available, "sourceId": sound_id,
            "url": f"/assets/theme-sfx/{slot}.wav" if available else "",
            "message": message,
        })
    manifest_path.write_text(json.dumps(signature, indent=2) + "\n", encoding="utf-8")
    return {"ready": any(row["available"] for row in rows), "root": str(output), "rows": rows}


def sound_file(data_root: Path, slot: str) -> Path | None:
    if slot not in SOUND_SLOTS:
        return None
    target = Path(data_root) / "theme-sfx" / f"{slot}.wav"
    return target if target.is_file() else None
