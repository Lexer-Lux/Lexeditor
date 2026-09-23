"""Derived RDR1 camera-data fixes built from the installed archive at deploy time.

No vanilla camera program is stored in the repository.  The one supported transform
is deliberately narrow: enable the CoverCamera program's existing side-switch
output while preserving every other byte/line, including the separate passenger-
vehicle assignment.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path


CAMERA_ARCHIVE_RELATIVE = Path("game") / "camera.rpf"
CAMERA_ENTRY_RELATIVE = Path("camera") / "default.ccm"
GENERATOR_VERSION = 1
# Installed PC evidence: the CoverCamera assignment is line 1167 and is directly
# preceded by its output register.  Keep the line number as an additional guard;
# if Rockstar changes the program, fail closed and re-audit rather than patching a
# similarly named assignment elsewhere.
COVER_ASSIGNMENT_LINE = 1167
_REGISTER = b"R allowCameraSideSwitch"
_FALSE_ASSIGNMENT = b"E 0 C 17"
_TRUE_ASSIGNMENT = b"E 0 C 1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_body(line: bytes) -> bytes:
    return line.rstrip(b"\r\n").strip()


def _false_side_switch_pairs(lines: list[bytes]) -> list[int]:
    result = []
    for index in range(1, len(lines)):
        if (_line_body(lines[index - 1]) == _REGISTER and
                _line_body(lines[index]) == _FALSE_ASSIGNMENT):
            result.append(index)
    return result


def patch_cover_camera_program(source: bytes) -> bytes:
    """Return *source* with exactly the proven CoverCamera permission changed.

    The current PC program has 3,675 lines and the assignment itself is line 1167.
    We do not require the total line count so harmless tail growth can survive, but
    we do require that exact line/preceding-register signature and at least one
    other false side-switch assignment.  That second assignment is the separately
    audited passenger-vehicle path and must remain false.
    """
    lines = source.splitlines(keepends=True)
    target = COVER_ASSIGNMENT_LINE - 1
    if target >= len(lines) or target <= 0:
        raise ValueError("Installed default.ccm is shorter than the audited CoverCamera program")
    if _line_body(lines[target - 1]) != _REGISTER or _line_body(lines[target]) != _FALSE_ASSIGNMENT:
        raise ValueError(
            "Installed default.ccm no longer has the audited CoverCamera side-switch assignment"
        )
    false_pairs = _false_side_switch_pairs(lines)
    if target not in false_pairs or len(false_pairs) < 2:
        raise ValueError(
            "Installed default.ccm does not preserve the audited cover/vehicle side-switch structure"
        )

    line = lines[target]
    match = re.fullmatch(rb"(?P<prefix>\s*)E 0 C 17(?P<ending>\r?\n)?", line)
    if not match:
        raise ValueError("CoverCamera assignment contains unexpected data")
    lines[target] = match.group("prefix") + _TRUE_ASSIGNMENT + (match.group("ending") or b"")
    result = b"".join(lines)

    changed = [index for index, (before, after) in enumerate(zip(source.splitlines(), result.splitlines()), 1)
               if before != after]
    if changed != [COVER_ASSIGNMENT_LINE]:
        raise RuntimeError(f"Cover-camera transform changed unexpected lines: {changed}")
    after_lines = result.splitlines(keepends=True)
    if _line_body(after_lines[target]) != _TRUE_ASSIGNMENT:
        raise RuntimeError("CoverCamera side-switch permission did not become true")
    # Exactly one audited false pair is consumed. At least the passenger assignment
    # remains false, proving we did not globally enable camera-side switching.
    if len(_false_side_switch_pairs(after_lines)) != len(false_pairs) - 1:
        raise RuntimeError("Cover-camera transform changed another side-switch assignment")
    return result


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, document: dict) -> None:
    payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_bytes(path, payload)


def _record(path: Path, *, include_hash: bool = False) -> dict:
    stat = path.stat()
    record = {"path": str(path.resolve()), "size": stat.st_size, "mtimeNs": stat.st_mtime_ns}
    if include_hash:
        record["sha256"] = sha256_file(path)
    return record


def ensure_cover_shoulder_override(
    game_root: Path,
    tool: Path,
    generated_root: Path,
    *,
    runner=subprocess.run,
) -> dict:
    """Materialize the derived `camera/default.ccm` override if necessary.

    The generated file lives in Lexeditor's workspace-owned generated directory,
    never in the installed game archive.  A stat-keyed manifest avoids repeatedly
    extracting the camera program; every regeneration hashes the source before and
    after extraction to prove the installed archive stayed unchanged.
    """
    game_root = Path(game_root).resolve()
    tool = Path(tool).resolve()
    generated_root = Path(generated_root).resolve()
    archive = (game_root / CAMERA_ARCHIVE_RELATIVE).resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Missing RDR camera archive: {archive}")
    if not tool.is_file():
        raise FileNotFoundError(f"Missing RPF6 bridge: {tool}")
    with archive.open("rb") as stream:
        if stream.read(4) != b"RPF6":
            raise ValueError(f"Expected an RPF6 camera archive: {archive}")

    output = generated_root / CAMERA_ENTRY_RELATIVE
    manifest = generated_root / ".cover-shoulder.json"
    source_fast = _record(archive)
    try:
        current = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        current = {}
    if (current.get("version") == GENERATOR_VERSION and current.get("source") == source_fast and
            current.get("output") == str(output) and output.is_file() and
            current.get("outputSha256") == sha256_file(output)):
        return {"source": str(archive), "output": str(output), "cached": True,
                "sha256": current["outputSha256"]}

    generated_root.mkdir(parents=True, exist_ok=True)
    before_hash = sha256_file(archive)
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-camera-") as temp_name:
        temporary_root = Path(temp_name)
        result = runner(
            [str(tool), "extract", str(archive), str(temporary_root), "*default.ccm"],
            cwd=str(tool.parent), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"RPF6 camera extraction failed: {detail}")
        candidates = [path for path in temporary_root.rglob("default.ccm") if path.is_file()]
        if len(candidates) != 1:
            raise RuntimeError(
                f"RPF6 camera extraction returned {len(candidates)} default.ccm files; expected one"
            )
        vanilla = candidates[0].read_bytes()
        patched = patch_cover_camera_program(vanilla)
    after_hash = sha256_file(archive)
    if after_hash != before_hash:
        raise RuntimeError("Installed camera.rpf changed while preparing the shoulder-swap override")

    _atomic_bytes(output, patched)
    output_hash = sha256_file(output)
    source_record = {**source_fast, "sha256": before_hash}
    _atomic_json(manifest, {
        "version": GENERATOR_VERSION,
        "source": source_fast,
        "sourceSha256": before_hash,
        "output": str(output),
        "outputSha256": output_hash,
        "transform": "CoverCamera.allowCameraSideSwitch false->true",
        "changedLine": COVER_ASSIGNMENT_LINE,
    })
    return {"source": str(archive), "output": str(output), "cached": False,
            "sha256": output_hash, "sourceRecord": source_record}
