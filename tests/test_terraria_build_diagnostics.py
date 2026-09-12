from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.build_diagnostics import parse_build_diagnostics


class TerrariaBuildDiagnosticTests(unittest.TestCase):
    def test_parses_windows_msbuild_error_and_relativizes_project_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "Content" / "Items" / "Sword.cs"
            line = f"{source}(12,34): error CS0103: The name 'missing' does not exist in the current context [{root / 'ExampleMod.csproj'}]"
            diagnostics = parse_build_diagnostics(line, root)
            self.assertEqual(len(diagnostics), 1)
            row = diagnostics[0]
            self.assertEqual(row["path"], "Content/Items/Sword.cs")
            self.assertTrue(row["projectFile"])
            self.assertEqual((row["line"], row["column"]), (12, 34))
            self.assertEqual(row["severity"], "error")
            self.assertEqual(row["code"], "CS0103")
            self.assertIn("missing", row["message"])

    def test_parses_warning_range_and_keeps_external_path_non_navigable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            external = root.parent / "Other.cs"
            diagnostics = parse_build_diagnostics(
                f"{external}(2,4,2,9): warning CS0168: The variable 'x' is declared but never used",
                root,
            )
            self.assertEqual(len(diagnostics), 1)
            row = diagnostics[0]
            self.assertFalse(row["projectFile"])
            self.assertEqual((row["endLine"], row["endColumn"]), (2, 9))
            self.assertEqual(row["severity"], "warning")

    def test_deduplicates_stdout_stderr_style_repetition_and_sorts_errors_first(self):
        text = "\n".join([
            "/tmp/Example/B.cs(5,1): warning CS0219: Assigned but never used",
            "/tmp/Example/A.cs(9,2): error CS1002: ; expected",
            "/tmp/Example/A.cs(9,2): error CS1002: ; expected",
        ])
        rows = parse_build_diagnostics(text, Path("/tmp/Example"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["severity"], "error")
        self.assertEqual(rows[0]["path"], "A.cs")
        self.assertEqual(rows[1]["severity"], "warning")

    def test_ignores_unstructured_build_noise(self):
        text = "\n".join([
            "Building ExampleMod...",
            "Build FAILED.",
            "0 Warning(s)",
            "1 Error(s)",
            "Time Elapsed 00:00:01.00",
        ])
        self.assertEqual(parse_build_diagnostics(text), [])

    def test_accepts_bytes_and_case_insensitive_severity(self):
        rows = parse_build_diagnostics(b"Test.cs(1,2): ERROR cs1001: Identifier expected\n")
        self.assertEqual(rows[0]["severity"], "error")
        self.assertEqual(rows[0]["code"], "CS1001")


if __name__ == "__main__":
    unittest.main()
