"""Compile the production trigger policy and verify its deployment inputs."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from games.ff8.ffnx_modern_controls import apply_to_ffnx


ROOT = Path(__file__).resolve().parents[1]
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")


class VehicleDriveTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_production_axis_preserves_partial_analog_with_digital_alias(self):
        header = ROOT / "games/ff8/ffnx_modern_controls/vehicle_drive.h"
        code = '#include "' + header.as_posix() + '"\n' + r'''
#include <limits>
int main() {
  using namespace lexeditor_vehicle_drive;
  if (axis(0,0)!=128 || axis(0,0,false,true)!=255 || axis(0,0,true,false)!=0) return 1;
  if (axis(0,0,true,true)!=128) return 2;
  for (int n=1; n<=100; ++n) {
    float pull=n/100.0f;
    if (axis(0,pull,false,true)!=axis(0,pull)) return 3;
    if (axis(pull,0,true,false)!=axis(pull,0)) return 4;
    if (axis(pull,pull,true,true)!=128) return 5;
    if (n<100 && n>2 && (axis(0,pull)>=255 || axis(pull,0)<=0)) return 6;
  }
  if (axis(0,0.5f,false,true)!=192 || axis(0.5f,0,true,false)!=64) return 7;
  if (axis(-1,2)!=255) return 8;
  if (axis(std::numeric_limits<float>::quiet_NaN(),0)!=128) return 9;
  if (axis(0,std::numeric_limits<float>::infinity())!=128) return 10;
  return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="lexeditor-vehicle-test-") as temporary:
            folder = Path(temporary)
            (folder / "check.cpp").write_text(code, encoding="utf-8")
            (folder / "build.cmd").write_text(
                f'@echo off\ncall "{VCVARS}" >nul\ncl /nologo /EHsc /std:c++17 check.cpp /Fe:check.exe\n',
                encoding="utf-8")
            build = subprocess.run(["cmd", "/c", str(folder / "build.cmd")], cwd=folder,
                                   capture_output=True, text=True, timeout=60,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(folder / "check.exe")], cwd=folder, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0)

    def test_patcher_deploys_all_local_runtime_headers(self):
        # Small upstream input fixture exercises the real patcher and its
        # complete dependency output. No FFNx build tree is copied.
        files = {
            "src/cfg.cpp": 'bool enable_devtools;\n\tenable_devtools = config["enable_devtools"].value_or(false);',
            "src/cfg.h": 'extern bool enable_devtools;',
            "misc/FFNx.toml": 'enable_devtools = false',
            "src/ff8_opengl.cpp": '\n'.join([
                '#include "ff8.h"', 'void ff8_init_hooks(struct game_obj *_game_object)\n{',
                'LPDIJOYSTATE2 ff8_update_gamepad_status()\n{',
                '\treturn ff8_externals.dinput_gamepad_state;\n}',
                '+ (FF8_US_VERSION ? 0xE2 : 0xDF), ff8_get_analog_value); // rX',
                '+ (FF8_US_VERSION ? 0xF2 : 0xEF), ff8_get_analog_value); // rY']),
        }
        with tempfile.TemporaryDirectory(prefix="lexeditor-vehicle-patcher-") as temporary:
            folder = Path(temporary)
            for name, content in files.items():
                destination = folder / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
            apply_to_ffnx.apply(folder, check_revision=False)
            for name in ("vehicle_drive.h", "camera_axis.h", "battle_camera.h",
                         "lexeditor_ff8_modern_controls.h", "lexeditor_ff8_modern_controls.cpp"):
                self.assertEqual((folder / "src" / name).read_bytes(),
                                 (Path(apply_to_ffnx.__file__).parent / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
