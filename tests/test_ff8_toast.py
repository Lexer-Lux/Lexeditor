"""Build and run the parts of Lexeditor's in-game message that need no device."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOASTS = ROOT / "plugins/ff8/ffnx_toasts"
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")


class ToastTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_the_queue_and_the_layout_behave(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-toast-") as temporary:
            folder = Path(temporary)
            for name in ("toast_queue.h", "toast_layout.h", "toast_test.cpp"):
                shutil.copyfile(TOASTS / name, folder / name)
            (folder / "build.cmd").write_text(
                f'@echo off\ncall "{VCVARS}" >nul\n'
                'cl /nologo /EHsc /std:c++17 /W4 toast_test.cpp /Fe:toast_test.exe\n',
                encoding="utf-8")
            build = subprocess.run(["cmd", "/c", str(folder / "build.cmd")], cwd=folder,
                                   capture_output=True, text=True, timeout=120,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(folder / "toast_test.exe")], cwd=folder,
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("holds long enough to read", result.stdout)

    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_the_box_compiles_against_the_shapes_it_uses(self):
        """Compile the drawing against stand-ins for FFNx and ImGui.

        The real build needs FFNx's tree and its ImGui package, which this
        machine does not carry. Standing the few shapes it uses up by hand
        still catches what cannot otherwise be caught here - a typo, a wrong
        member, an argument in the wrong place - and leaves only behaviour on
        a real device to the in-game pass.
        """
        stubs = {
            "imgui.h": """#pragma once
#include <cstdint>
#define IM_COL32_A_SHIFT 24
#define IM_COL32_A_MASK 0xFF000000u
#define IM_COL32(r,g,b,a) ((std::uint32_t)((a)<<24|(b)<<16|(g)<<8|(r)))
using ImU32 = std::uint32_t;
struct ImVec2 { float x=0, y=0; ImVec2()=default; ImVec2(float a,float b):x(a),y(b){} };
struct ImFont;
struct ImDrawList {
  void AddRectFilledMultiColor(const ImVec2&,const ImVec2&,ImU32,ImU32,ImU32,ImU32) {}
  void AddRect(const ImVec2&,const ImVec2&,ImU32,float=0,int=0,float=1) {}
  void AddText(const ImFont*,float,const ImVec2&,ImU32,const char*) {}
};
struct ImGuiIO { ImVec2 DisplaySize; };
namespace ImGui {
  inline ImGuiIO &GetIO() { static ImGuiIO io; return io; }
  inline ImDrawList *GetForegroundDrawList() { static ImDrawList list; return &list; }
}
""",
            "common.h": "#pragma once\n",
            "globals.h": "#pragma once\n#include <cstdint>\nextern std::uint32_t game_width;\nextern std::uint32_t game_height;\n",
            "renderer.h": """#pragma once
#include <array>
struct Renderer {
  std::array<float, 2> projectGamePointToScreen(float, float) const { return {0.0f, 0.0f}; }
};
extern Renderer newRenderer;
""",
        }
        with tempfile.TemporaryDirectory(prefix="lexeditor-toast-build-") as temporary:
            folder = Path(temporary)
            for name, body in stubs.items():
                (folder / name).write_text(body, encoding="utf-8")
            for name in ("toast_queue.h", "toast_layout.h"):
                shutil.copyfile(TOASTS / name, folder / name)
            for name in ("lexeditor_ff8_toast.h", "lexeditor_ff8_toast.cpp"):
                shutil.copyfile(TOASTS / "ffnx-src" / name, folder / name)
            (folder / "build.cmd").write_text(
                f'@echo off\ncall "{VCVARS}" >nul\n'
                'cl /nologo /c /EHsc /std:c++17 /I. lexeditor_ff8_toast.cpp\n',
                encoding="utf-8")
            build = subprocess.run(["cmd", "/c", str(folder / "build.cmd")], cwd=folder,
                                   capture_output=True, text=True, timeout=120,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

    def test_the_drawing_stays_out_of_the_testable_part(self):
        """The two headers must not need a device, or none of the above runs."""
        for name in ("toast_queue.h", "toast_layout.h"):
            source = (TOASTS / name).read_text(encoding="utf-8")
            for forbidden in ("imgui", "windows.h", "renderer.h", "d3d"):
                self.assertNotIn(forbidden, source.lower(), f"{name} reaches for {forbidden}")


if __name__ == "__main__":
    unittest.main()
