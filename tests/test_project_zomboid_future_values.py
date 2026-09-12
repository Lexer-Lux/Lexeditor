from __future__ import annotations

from pathlib import Path
import unittest

from games.project_zomboid import core
from games.project_zomboid.server import _guard_known_select_values


class ProjectZomboidFutureValueTests(unittest.TestCase):
    @staticmethod
    def reader_with(value: str):
        def reader(_root: Path) -> dict:
            return {
                "rows": [{
                    "path": "42/media/scripts/future.txt",
                    "module": "Future",
                    "id": "Record",
                    "fields": {"mode": value},
                }],
                "errors": [],
            }
        return reader

    @staticmethod
    def payload(edits: dict) -> dict:
        return {
            "path": "42/media/scripts/future.txt",
            "module": "Future",
            "id": "Record",
            "sha256": "unused-by-guard",
            "edits": edits,
        }

    def test_unknown_current_select_value_fails_closed(self):
        with self.assertRaisesRegex(core.ProjectZomboidError, "mode=FutureMode"):
            _guard_known_select_values(
                Path("."),
                self.payload({"mode": "KnownA", "other": "changed"}),
                self.reader_with("FutureMode"),
                {"mode": ("KnownA", "KnownB")},
            )

    def test_unknown_select_is_ignored_when_request_does_not_submit_it(self):
        _guard_known_select_values(
            Path("."),
            self.payload({"other": "changed"}),
            self.reader_with("FutureMode"),
            {"mode": ("KnownA", "KnownB")},
        )

    def test_known_current_values_are_compared_case_insensitively(self):
        _guard_known_select_values(
            Path("."),
            self.payload({"mode": "KnownB"}),
            self.reader_with("knowna"),
            {"mode": ("KnownA", "KnownB")},
        )


if __name__ == "__main__":
    unittest.main()
