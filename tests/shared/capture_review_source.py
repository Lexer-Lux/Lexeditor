"""Capture bounded, tracked review sources and expose existing test evidence paths."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SUFFIXES = {
    ".py", ".js", ".cjs", ".css", ".html", ".json", ".xml", ".md", ".txt",
    ".toml", ".ini", ".yml", ".yaml", ".c", ".h", ".cpp", ".s", ".ld", ".svg",
    ".bat", ".cmd", ".ps1", ".gitignore", ".gitattributes",
}
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 96 * 1024 * 1024


def capture(ref: str, destination: Path) -> dict:
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", ref + "^{commit}"], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(["git", "archive", "--format=zip", commit], cwd=ROOT)
    total = 0
    included = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(
            destination, "w", zipfile.ZIP_DEFLATED) as output:
        for entry in source.infolist():
            path = Path(entry.filename)
            if entry.is_dir() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if entry.file_size > MAX_FILE:
                continue
            total += entry.file_size
            if total > MAX_TOTAL:
                raise ValueError("Review source snapshot exceeds its 96 MiB bound")
            output.writestr(entry.filename, source.read(entry))
            included += 1
    return {"commit": commit, "files": included, "uncompressedBytes": total}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare")
    args = parser.parse_args()
    if not os.environ.get("GITHUB_ACTIONS"):
        raise SystemExit("Source capture is a CI-only review operation")
    out = Path(os.environ["RUNNER_TEMP"]) / "lexeditor-review"
    out.mkdir(exist_ok=True)
    facts = {"head": capture("HEAD", out / "source-head.zip")}
    if args.compare:
        if len(args.compare) != 40 or any(c not in "0123456789abcdef" for c in args.compare):
            raise ValueError("Comparison source must be a full commit SHA")
        subprocess.run(["git", "fetch", "--depth=1", "origin", args.compare],
                       cwd=ROOT, check=True)
        facts["comparison"] = capture(args.compare, out / "source-comparison.zip")
    (out / "source-evidence.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"source_dir={out}\n")
        stream.write(f"test_dir={Path(tempfile.gettempdir()) / 'lexeditor-dev'}\n")
    print(json.dumps(facts))


if __name__ == "__main__":
    main()
