"""Prepare/export the FF8 derivative in an isolated pinned FFNx checkout.

This does not compile, deploy, or modify a game installation. Use a CLEAN
FFNx checkout at the package's source commit; existing work is never reset.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8.ffnx_issue_51 import runtime_package

COPIES = {
    "lexeditor_ff8_party_switch.cpp": "ffnx_party_switch",
    "lexeditor_ff8_party_switch.h": "ffnx_party_switch",
    "lexeditor_ff8_bars.cpp": "ffnx_status_bars",
    "lexeditor_ff8_bars.h": "ffnx_status_bars",
    "lexeditor_ff8_battle_meters.h": "ffnx_status_bars",
}
PACKAGE_PATCH = ROOT / "games/ff8/ffnx_issue_51/package/ISSUE51_DERIVATIVE_SOURCE.patch"


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def verify_revision(root: Path) -> None:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    if head != runtime_package.SOURCE_COMMIT:
        raise ValueError(f"Expected FFNx {runtime_package.SOURCE_COMMIT}; found {head}")


def source_paths() -> list[str]:
    paths = re.findall(r"^diff --git a/(\S+) b/\S+$", PACKAGE_PATCH.read_text(encoding="utf-8"), re.M)
    paths.append("src/lexeditor_ff8_battle_meters.h")
    if not paths or any(".." in Path(path).parts or Path(path).is_absolute() for path in paths):
        raise ValueError("Invalid derivative patch paths")
    return sorted(set(paths))


def prepare(root: Path) -> None:
    verify_revision(root)
    if git(root, "status", "--porcelain", "--untracked-files=normal").strip():
        raise ValueError("Use a clean isolated FFNx checkout; existing changes will not be overwritten")
    git(root, "apply", "--check", "--ignore-space-change", str(PACKAGE_PATCH))
    git(root, "apply", "--ignore-space-change", str(PACKAGE_PATCH))
    for name, module in COPIES.items():
        shutil.copyfile(ROOT / "games/ff8" / module / "ffnx-src" / name, root / "src" / name)
    edits = {
        "src/cfg.cpp": [
            ("bool enable_ff8_hp_bars;", "bool enable_ff8_hp_bars;\nbool enable_ff8_gf_hp_bars;"),
            ('\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);',
             '\tenable_ff8_hp_bars = config["enable_ff8_hp_bars"].value_or(false);\n\tenable_ff8_gf_hp_bars = config["enable_ff8_gf_hp_bars"].value_or(false);'),
        ],
        "src/cfg.h": [("extern bool enable_ff8_hp_bars;", "extern bool enable_ff8_hp_bars;\nextern bool enable_ff8_gf_hp_bars;")],
        "misc/FFNx.toml": [("enable_ff8_hp_bars = false", "enable_ff8_hp_bars = false\n\n# Blue junctioned-GF HP above battle names, filled left to right.\nenable_ff8_gf_hp_bars = false")],
    }
    for name, replacements in edits.items():
        target = root / name
        original = target.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        text = original.decode("utf-8").replace("\r\n", "\n")
        for old, new in replacements:
            if new in text:
                continue  # The shipped source patch may already include this batch.
            if text.count(old) != 1:
                raise ValueError(f"{name}: missing or duplicated configuration anchor")
            text = text.replace(old, new, 1)
        target.write_bytes(text.replace("\n", newline).encode("utf-8"))
    verify_canonical(root)
    print("Prepared canonical battle extensions on the pinned derivative; no game deployment")


def verify_canonical(root: Path) -> None:
    for name, module in COPIES.items():
        expected = ROOT / "games/ff8" / module / "ffnx-src" / name
        if (root / "src" / name).read_bytes() != expected.read_bytes():
            raise ValueError(f"Build source differs from canonical {name}")
    for name in ("src/cfg.cpp", "src/cfg.h", "misc/FFNx.toml"):
        if "enable_ff8_gf_hp_bars" not in (root / name).read_text(encoding="utf-8"):
            raise ValueError(f"GF HP integration missing from {name}")


def export(root: Path, output: Path) -> None:
    verify_revision(root)
    verify_canonical(root)
    paths = source_paths()
    git(root, "add", "--intent-to-add", "--", *paths)
    patch = git(root, "diff", "--binary", "HEAD", "--", *paths)
    if not patch.startswith(b"diff --git "):
        raise ValueError("No complete source patch was generated")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)
    print(f"Exported complete matching derivative source to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ffnx_source", type=Path)
    parser.add_argument("--export", type=Path, help="Export an already prepared source tree")
    args = parser.parse_args()
    if args.export:
        export(args.ffnx_source.resolve(), args.export)
    else:
        prepare(args.ffnx_source.resolve())


if __name__ == "__main__":
    main()
