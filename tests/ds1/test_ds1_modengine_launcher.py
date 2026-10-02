"""Pinned-source patch tests and a compiled, game-independent launcher path test."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ds1_modengine_source_patch", ROOT / "tools" / "prepare_ds1_modengine.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
FIXTURE = Path(__file__).parent / "fixtures" / "modengine2_launcher.cpp"

NATIVE_TEST = r"""
#include "lexeditor_launcher_paths.h"
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using lexeditor_ds1::application_root;

int main() {
    // UTF-8 source with Windows /utf-8; no locale-dependent wide conversion.
    const auto install = fs::absolute(
        fs::u8path(u8"Steam Library/jeux é/日本/Dark Souls")).lexically_normal();
    const std::vector<fs::path> targets = {
        "DarkSoulsRemastered.exe", "Game/DarkSoulsIII.exe",
        "Game/eldenring.exe", "Game/armoredcore6.exe"
    };
    for (const auto& relative : targets) {
        if (application_root(install / relative, relative) != install) {
            std::cerr << "incorrect application root\n";
            return 1;
        }
    }
    // Relative manual paths resolve against the launcher's actual working directory.
    if (application_root("moddir/DarkSoulsRemastered.exe", "DarkSoulsRemastered.exe")
        != fs::absolute("moddir").lexically_normal()) {
        return 2;
    }
    if (application_root(install / "unused/../DarkSoulsRemastered.exe",
                         "DarkSoulsRemastered.exe") != install) {
        return 3;
    }
    // Static launch-table values must be relative and cannot traverse parents.
    const std::vector<fs::path> invalid = {
        fs::path{}, fs::absolute("Game/invalid.exe"), "Game/../invalid.exe", "./invalid.exe"
    };
    for (const auto& relative : invalid) {
        bool rejected = false;
        try { application_root(install / "invalid.exe", relative); }
        catch (const std::invalid_argument&) { rejected = true; }
        if (!rejected) return 4;
    }
    std::cout << "10 native path cases passed\n";
    return 0;
}
"""


class LauncherPatchTests(unittest.TestCase):
    def setUp(self):
        self.original = FIXTURE.read_bytes()

    def test_fixture_matches_reviewed_git_blob(self):
        self.assertEqual(patcher.git_blob_hash(self.original), patcher.LAUNCHER_BLOB)

    def test_both_root_derivations_use_target_layout(self):
        result = patcher.patch_launcher(self.original).decode()
        self.assertEqual(result.count("lexeditor_ds1::application_root("), 2)
        self.assertNotIn(".parent_path().parent_path()", result)
        self.assertIn('#include "lexeditor_launcher_paths.h"', result)
        # A missing target must be rejected before indexing the target table.
        manual = result.split("if (!target_path_option->empty())", 1)[1].split(
            "// If the game target was not set", 1)[0]
        self.assertLess(manual.index("return E_APP_NOT_FOUND;"),
                        manual.index("launch_targets.at(target)"))

    def test_failed_process_creation_returns_failure_before_closing_handles(self):
        result = patcher.patch_launcher(self.original).decode()
        failure = re.search(r"if \(!success\) \{(.*?)\n    \}", result, re.S).group(1)
        self.assertIn("return E_OS_ERROR;", failure)
        self.assertLess(result.index("if (!success)"), result.index("CloseHandle(pi.hProcess)"))
        self.assertIn("STARTUPINFOW si = {};\n    si.cb = sizeof(si);", result)

    def test_windows_crlf_checkout_is_supported(self):
        self.assertEqual(patcher.patch_launcher(self.original.replace(b"\n", b"\r\n")),
                         patcher.patch_launcher(self.original))

    def test_changed_or_already_patched_source_is_refused(self):
        for data in (b"", self.original + b"\n", self.original.replace(b"E_OK = 0", b"E_OK = 1"),
                     patcher.patch_launcher(self.original)):
            with self.subTest(size=len(data)), self.assertRaisesRegex(ValueError, "pinned"):
                patcher.patch_launcher(data)

    def test_oversized_input_is_refused(self):
        with self.assertRaisesRegex(ValueError, "size limit"):
            patcher.patch_launcher(b"x" * (patcher.MAX_SOURCE_BYTES + 1))

    def test_preparation_preserves_input_and_records_exact_output_hashes(self):
        before = hashlib.sha256(self.original).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "prepared"
            manifest = patcher.prepare_launcher(FIXTURE, target)
            self.assertFalse(manifest["nativeBuildVerified"])
            self.assertEqual(manifest["sourceRevision"], patcher.SOURCE_REVISION)
            self.assertEqual(json.loads((target / "source-patch.json").read_text()), manifest)
            self.assertEqual(set(path.name for path in target.iterdir()),
                             set(manifest["files"]) | {"source-patch.json"})
            for name, expected in manifest["files"].items():
                self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), expected)
            self.assertEqual((target / "launcher.cpp").read_bytes(),
                             patcher.patch_launcher(self.original))
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "prepared"
            target.mkdir()
            keep = target / "keep"
            keep.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                patcher.prepare_launcher(FIXTURE, target)
            self.assertEqual(keep.read_bytes(), b"preserve")
            self.assertEqual(list(target.iterdir()), [keep])

    def test_invalid_input_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "bad.cpp", Path(tmp) / "prepared"
            source.write_bytes(b"not the pinned source")
            with self.assertRaises(ValueError):
                patcher.prepare_launcher(source, target)
            self.assertFalse(target.exists())

    def test_native_path_helper(self):
        compiler = shutil.which("g++") or shutil.which("clang++")
        cmake = shutil.which("cmake")
        if sys.platform == "win32" and cmake:
            compiler = None  # CMake discovers Visual Studio without a developer shell.
        elif not compiler:
            self.skipTest("No native C++ compiler; launcher-path acceptance not established")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            shutil.copyfile(patcher.ASSETS / "lexeditor_launcher_paths.h",
                            work / "lexeditor_launcher_paths.h")
            source = work / "path_check.cpp"
            source.write_text(NATIVE_TEST, encoding="utf-8")
            if compiler:
                executable = work / ("path_check.exe" if sys.platform == "win32" else "path_check")
                subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                                str(source), "-o", str(executable)],
                               check=True, capture_output=True, timeout=120)
            else:
                (work / "CMakeLists.txt").write_text(
                    "cmake_minimum_required(VERSION 3.20)\n"
                    "project(DS1LauncherPathCheck LANGUAGES CXX)\n"
                    "add_executable(path_check path_check.cpp)\n"
                    "target_compile_features(path_check PRIVATE cxx_std_17)\n"
                    "target_compile_options(path_check PRIVATE "
                    "$<$<CXX_COMPILER_ID:MSVC>:/utf-8>)\n", encoding="utf-8")
                subprocess.run([cmake, "-S", str(work), "-B", str(work / "build")],
                               check=True, capture_output=True, timeout=120)
                subprocess.run([cmake, "--build", str(work / "build"), "--config", "Release",
                                "--parallel", "2"],
                               check=True, capture_output=True, timeout=120)
                options = (work / "build" / "Release" / "path_check.exe",
                           work / "build" / "path_check.exe")
                executable = next((path for path in options if path.is_file()), None)
                self.assertIsNotNone(executable, "Native path-check executable was not produced")
            cwd = work / "répertoire 日本"
            cwd.mkdir()
            completed = subprocess.run([str(executable)], cwd=cwd, check=True,
                                       capture_output=True, text=True, timeout=15)
            self.assertIn("10 native path cases passed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
