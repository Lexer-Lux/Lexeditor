"""Build Lexeditor's DS1 loader (dinput8.dll) from lexeditor_ds1_loader.c.

    python plugins/ds1/runtime/build.py [--zig PATH] [--check]
    python plugins/ds1/runtime/build.py --debug --dearxan FOLDER [--check]

The debug loader (package/debug/dinput8.dll) is the same loader with
lexeditor_ds1_debug.c: no network, and Arxan switched off by dearxan
(https://github.com/tremwil/dearxan, MIT/Apache-2.0) so a debugger can attach.
dearxan ships as an MSVC static library, so this build uses Visual Studio's
compiler (Build Tools 2022) and the release's include/ and lib/ folders; the
library itself is not kept in the repository.

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
DEBUG_SOURCES = SOURCES + ("lexeditor_ds1_debug.c",)
DEBUG_PACKAGE = PACKAGE / "debug"
DEARXAN = "0.5.6"


def source_hash(names=SOURCES) -> str:
    digest = hashlib.sha256()
    for name in names:
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


def find_vcvars() -> Path:
    where = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if where.is_file():
        found = subprocess.run([str(where), "-latest", "-products", "*", "-property", "installationPath"],
                               capture_output=True, text=True).stdout.strip()
        vcvars = Path(found) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat" if found else None
        if vcvars and vcvars.is_file():
            return vcvars
    raise SystemExit("Visual Studio's C compiler was not found (Build Tools 2022 with the C++ workload).")


def build_debug(dearxan: Path, output: Path) -> None:
    """The debug loader: Microsoft's compiler, dearxan linked in, reproducible (/Brepro)."""
    include, lib = dearxan / "include", dearxan / "lib"
    if not (include / "dearxan.h").is_file() or not (lib / "dearxan.lib").is_file():
        raise SystemExit(f"{dearxan} is not an unpacked dearxan {DEARXAN} release (include/, lib/).")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="lex-ds1-debug-"))
    try:
        for name in DEBUG_SOURCES:
            shutil.copy2(HERE / name, work / name)
        shutil.copy2(include / "dearxan.h", work / "dearxan.h")
        command = (f'call "{find_vcvars()}" >nul && cl /nologo /O2 /LD /MD /Brepro /DLX_DEBUG_BUILD '
                   f'/D_CRT_SECURE_NO_WARNINGS lexeditor_ds1_loader.c lexeditor_ds1_debug.c '
                   f'/link /Brepro /OUT:dinput8.dll "{lib / "dearxan.lib"}" ws2_32.lib ntdll.lib userenv.lib '
                   f'dbghelp.lib kernel32.lib advapi32.lib bcrypt.lib synchronization.lib')
        # A batch file: cmd's quoting does not survive being passed as one argument.
        (work / "build.bat").write_text("@echo off\n" + command + "\n", encoding="utf-8")
        subprocess.run(["cmd", "/c", str(work / "build.bat")], check=True, cwd=work)
        shutil.copy2(work / "dinput8.dll", output)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zig")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--debug", action="store_true", help="build the debug loader (Arxan off, no network)")
    parser.add_argument("--dearxan", type=Path, help="an unpacked dearxan release (include/, lib/)")
    args = parser.parse_args()
    if args.debug:
        if not args.dearxan:
            raise SystemExit("--debug needs --dearxan FOLDER")
        if args.check:
            with tempfile.TemporaryDirectory() as folder:
                build_debug(args.dearxan, Path(folder) / "dinput8.dll")
                same = (Path(folder) / "dinput8.dll").read_bytes() == (DEBUG_PACKAGE / "dinput8.dll").read_bytes()
            print("reproduced" if same else "DIFFERENT from the committed debug dinput8.dll")
            return 0 if same else 1
        build_debug(args.dearxan, DEBUG_PACKAGE / "dinput8.dll")
        dll = (DEBUG_PACKAGE / "dinput8.dll").read_bytes()
        manifest = {"file": "dinput8.dll", "sha256": hashlib.sha256(dll).hexdigest(), "size": len(dll),
                    "sourceSha256": source_hash(DEBUG_SOURCES), "compiler": "msvc (Build Tools 2022)",
                    "dearxan": DEARXAN}
        (DEBUG_PACKAGE / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return 0
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
