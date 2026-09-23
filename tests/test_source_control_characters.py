"""No source file holds a raw control character.

A patch written through a shell heredoc turned the `\\b` in Warband's
`/\\bitp_type_/` into a literal backspace byte. The regex still parsed, matched
nothing, and every item's Type and Weight field showed empty for two days. A
tab, a newline or a carriage return is text; anything else below 0x20 is a
lost escape.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("plugins", "ui", "tools", "tests")
SUFFIXES = {".js", ".py", ".css", ".html", ".json"}
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class SourceControlCharacterTests(unittest.TestCase):
    def test_no_lost_escapes(self):
        found = []
        for folder in FOLDERS:
            for path in (ROOT / folder).rglob("*"):
                if path.suffix not in SUFFIXES or not path.is_file() or "node_modules" in path.parts:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for match in CONTROL.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    found.append(f"{path.relative_to(ROOT)}:{line} {match.group()!r}")
        self.assertEqual(found, [], "raw control characters, most likely an escape a shell ate")


if __name__ == "__main__":
    unittest.main()
