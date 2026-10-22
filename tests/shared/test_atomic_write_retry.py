"""atomic_write rides out transient file locks on the final replace.

Switching a mod on failed with access denied on the mod.json replace:
Windows lets antivirus, search indexing and cloud sync hold a file
briefly after it changes. The replace retries briefly instead of
failing at once, then says what to close. A destination extracted
read-only (mod zips arrive that way) is made writable first: no
retry window would ever help that one.
"""
import os
import time
from unittest import mock

from core.plugin_files import atomic_write


def test_replace_retried_then_succeeds(tmp_path):
    target = tmp_path / "mod.json"
    target.write_text("{}", encoding="utf-8")
    real_replace = os.replace
    attempts = []

    def flaky(source, destination):
        attempts.append(time.monotonic())
        if len(attempts) < 3:
            raise PermissionError(13, "Permission denied", str(destination))
        return real_replace(source, destination)

    with mock.patch("core.plugin_files.os.replace", side_effect=flaky):
        atomic_write(target, b'{"a": 1}')
    assert target.read_bytes() == b'{"a": 1}'
    assert len(attempts) == 3
    assert list(tmp_path.iterdir()) == [target]


def test_replace_gives_up_with_the_original_error(tmp_path):
    target = tmp_path / "mod.json"
    target.write_text("{}", encoding="utf-8")
    with mock.patch("core.plugin_files.os.replace",
                    side_effect=PermissionError(13, "Permission denied")) as replace:
        try:
            atomic_write(target, b'{"a": 1}')
        except PermissionError:
            pass
        else:
            raise AssertionError("expected PermissionError")
    assert replace.call_count > 1
    assert target.read_bytes() == b'{}'
    assert list(tmp_path.iterdir()) == [target]


def test_give_up_names_the_file_and_what_to_close(tmp_path):
    target = tmp_path / "later-game-ammunition" / "mod.json"
    target.parent.mkdir()
    target.write_text("{}", encoding="utf-8")
    with mock.patch("core.plugin_files.os.replace",
                    side_effect=PermissionError(13, "Permission denied")):
        try:
            atomic_write(target, b'{"a": 1}')
        except PermissionError as error:
            message = str(error)
        else:
            raise AssertionError("expected PermissionError")
    assert "later-game-ammunition/mod.json" in message, message
    assert "Close any program" in message, message


def test_read_only_destination_is_overwritten(tmp_path):
    target = tmp_path / "mod.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o444)
    try:
        atomic_write(target, b'{"a": 1}')
    finally:
        try:
            target.chmod(0o666)
        except OSError:
            pass
    assert target.read_bytes() == b'{"a": 1}'
    assert list(tmp_path.iterdir()) == [target]
