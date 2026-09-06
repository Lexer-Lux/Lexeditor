"""Regression checks for the generated RDR1 cover-camera shoulder-swap override."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr.camera_features import (
    COVER_ASSIGNMENT_LINE,
    CAMERA_ENTRY_RELATIVE,
    ensure_cover_shoulder_override,
    patch_cover_camera_program,
)


def fixture(*, bad_target=False, second_false=True):
    lines = [f"noop {index}\r\n".encode() for index in range(1, 3676)]
    lines[COVER_ASSIGNMENT_LINE - 2] = b"R allowCameraSideSwitch\r\n"
    lines[COVER_ASSIGNMENT_LINE - 1] = (
        b"E 0 C 99\r\n" if bad_target else b"E 0 C 17\r\n"
    )
    lines[40] = b"C 1\r\n"
    lines[41] = b"C 17\r\n"
    if second_false:
        lines[3000] = b"R allowCameraSideSwitch\r\n"
        lines[3001] = b"E 0 C 17\r\n"
    return b"".join(lines)


def main():
    vanilla = fixture()
    patched = patch_cover_camera_program(vanilla)
    before = vanilla.splitlines()
    after = patched.splitlines()
    changed = [i for i, pair in enumerate(zip(before, after), 1) if pair[0] != pair[1]]
    assert changed == [COVER_ASSIGNMENT_LINE], changed
    assert after[COVER_ASSIGNMENT_LINE - 1].strip() == b"E 0 C 1"
    assert after[3001].strip() == b"E 0 C 17"
    assert len(before) == len(after) == 3675
    try:
        patch_cover_camera_program(fixture(bad_target=True))
    except ValueError:
        pass
    else:
        raise AssertionError("unexpected CoverCamera assignment did not fail closed")
    try:
        patch_cover_camera_program(fixture(second_false=False))
    except ValueError:
        pass
    else:
        raise AssertionError("missing passenger false assignment did not fail closed")

    with tempfile.TemporaryDirectory(prefix="rdr-cover-camera-") as temp:
        root = Path(temp)
        game = root / "game-root"
        tool = root / "bridge" / "Rpf6ReadCli.exe"
        generated = root / "project" / ".lexeditor-generated" / "camera"
        archive = game / "game" / "camera.rpf"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"RPF6" + b"source remains immutable")
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"synthetic bridge")
        source_bytes = archive.read_bytes()
        calls = []

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def runner(args, **_kwargs):
            calls.append(args)
            output = Path(args[3]) / "root" / "camera" / "default.ccm"
            output.parent.mkdir(parents=True)
            output.write_bytes(vanilla)
            return Result()

        first = ensure_cover_shoulder_override(game, tool, generated, runner=runner)
        assert not first["cached"] and len(calls) == 1
        result_file = generated / CAMERA_ENTRY_RELATIVE
        assert result_file.is_file()
        assert result_file.read_bytes() == patched
        assert archive.read_bytes() == source_bytes
        second = ensure_cover_shoulder_override(game, tool, generated, runner=runner)
        assert second["cached"] and len(calls) == 1
        result_file.write_bytes(result_file.read_bytes() + b"tamper")
        third = ensure_cover_shoulder_override(game, tool, generated, runner=runner)
        assert not third["cached"] and len(calls) == 2
        assert result_file.read_bytes() == patched
        assert archive.read_bytes() == source_bytes

    print("PASS RDR cover shoulder swap: exact line-only transform, passenger false preserved, generated cache self-repairs")


if __name__ == "__main__":
    main()
