"""Build Lexeditor's DS1 loader (dinput8.dll) from lexeditor_ds1_loader.c.

    python plugins/ds1/runtime/build.py [--zig PATH] [--check]

Uses Zig's C compiler (any 0.14 release). The DLL and runtime-manifest.json
land in plugins/ds1/runtime/package/; the manifest records the hash of the
source the DLL was built from, so a stale DLL is caught by
tests/ds1/test_ds1_runtime_loader.py. --check rebuilds into a temporary
folder and fails if the result differs from the committed DLL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "package"
SOURCES = ("lexeditor_ds1_loader.c", "lexeditor_ds1_loader.h")


def source_hash() -> str:
    digest = hashlib.sha256()
    for name in SOURCES:
        digest.update(name.encode() + b"\0" + (HERE / name).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def find_zig(explicit: str | None) -> str:
    for candidate in (explicit, os.environ.get("LEXEDITOR_ZIG"), shutil.which("zig")):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    dev = Path(tempfile.gettempdir()) / "lexeditor-dev"
    found = sorted(dev.glob("zig-*/zig.exe")) if dev.is_dir() else []
    if found:
        return str(found[-1])
    raise SystemExit("Zig was not found. Pass --zig, set LEXEDITOR_ZIG, or put zig on PATH.")


def build(zig: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="lex-ds1-loader-"))
    try:
        # Built from a copy in a path without spaces; zig's linker writes no
        # timestamp, so the DLL is reproducible (--check).
        for name in SOURCES:
            shutil.copy2(HERE / name, work / name)
        subprocess.run([zig, "cc", "-target", "x86_64-windows-gnu", "-shared", "-O2", "-s",
                        "-fno-ident",
                        "-o", str(work / "dinput8.dll"), str(work / SOURCES[0])],
                       check=True, cwd=work)
        shutil.copy2(work / "dinput8.dll", output)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zig")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    zig = find_zig(args.zig)
    version = subprocess.run([zig, "version"], capture_output=True, text=True, check=True).stdout.strip()
    if args.check:
        with tempfile.TemporaryDirectory() as folder:
            build(zig, Path(folder) / "dinput8.dll")
            same = (Path(folder) / "dinput8.dll").read_bytes() == (PACKAGE / "dinput8.dll").read_bytes()
        print("reproduced" if same else "DIFFERENT from the committed dinput8.dll")
        return 0 if same else 1
    build(zig, PACKAGE / "dinput8.dll")
    dll = (PACKAGE / "dinput8.dll").read_bytes()
    manifest = {"file": "dinput8.dll", "sha256": hashlib.sha256(dll).hexdigest(), "size": len(dll),
                "sourceSha256": source_hash(), "compiler": f"zig {version}"}
    (PACKAGE / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
