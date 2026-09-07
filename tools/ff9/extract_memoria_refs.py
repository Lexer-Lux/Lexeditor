"""Extract only compile-time references from the verified pinned Memoria patcher."""
from __future__ import annotations

import gzip
import io
from pathlib import Path
import struct
import sys

from games.ff9 import memoria_manager
from games.ff9.memoria_patcher import MAGIC, inspect_payload

WANTED = {
    "Assembly-CSharp.dll": "Assembly-CSharp.dll",
    "Memoria.Prime.dll": "Memoria.Prime.dll",
}


def extract(destination: Path) -> dict[str, Path]:
    patcher, published = memoria_manager.stage()
    # Reuse production validation before reading any embedded data.
    inspect_payload(patcher)
    data = patcher.read_bytes()
    footer = data.rfind(MAGIC, max(0, len(data) - 65536))
    if footer < 0:
        raise RuntimeError("Pinned Memoria payload footer was not found")
    remaining, offset = struct.unpack_from("<qq", data, footer + len(MAGIC))
    parts: dict[int, str] = {}
    found: dict[str, Path] = {}
    destination.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(fileobj=io.BytesIO(data[offset:footer])) as stream:
        while remaining:
            header = stream.read(13)
            if len(header) != 13:
                raise RuntimeError("Pinned Memoria payload is truncated")
            size, _ticks, count = struct.unpack("<IqB", header)
            components = []
            for _ in range(count):
                token_raw = stream.read(2)
                if len(token_raw) != 2:
                    raise RuntimeError("Pinned Memoria path table is truncated")
                token = struct.unpack("<H", token_raw)[0]
                key = token & 0x7FFF
                if token & 0x8000:
                    length_raw = stream.read(1)
                    if not length_raw:
                        raise RuntimeError("Pinned Memoria path table is truncated")
                    length = length_raw[0]
                    parts[key] = stream.read(length).decode("utf-8")
                components.append(parts[key])
            name = "/".join(components)
            payload = stream.read(size)
            if len(payload) != size:
                raise RuntimeError("Pinned Memoria file is truncated")
            remaining -= size
            basename = Path(name).name
            if basename in WANTED and "/FF9_Data/Managed/" in name.replace("\\", "/"):
                target = destination / WANTED[basename]
                if basename not in found:
                    target.write_bytes(payload)
                    found[basename] = target
    missing = sorted(set(WANTED) - set(found))
    if missing:
        raise RuntimeError(f"Pinned Memoria payload is missing compile references: {missing}")
    print(f"Memoria {published['version']} references: " + ", ".join(str(path) for path in found.values()))
    return found


if __name__ == "__main__":
    extract(Path(sys.argv[1] if len(sys.argv) > 1 else "out/ff9-memoria-refs"))
