# Rebuilding the FF8 FFNx runtime (AF3DN.P)

The shared-Magic runtime Lexeditor ships in `plugins/ff8/ffnx_issue_51/package/`
is FFNx built from a pinned revision with Lexeditor's patch applied. Its files
are hash-pinned in `runtime-manifest.json`; `runtime_package.verify` refuses
anything else. This is the proven recipe (it ran as CI until 2026-09-24; the
bundled `ISSUE51_BUILD_REPORT.md` still names that retired workflow).

1. Source. Clone <https://github.com/julianxhokaxhiu/FFNx> at
   `c056db2783f376a340fcefa6a48cc33618998876`, then `git submodule update --init`.
   Apply Lexeditor's changes with
   `python tools/prepare_ff8_native_build.py <ffnx> --patch-output <out>/ISSUE51_DERIVATIVE_SOURCE.patch`.
2. Toolchain. MSVC x86 (Visual Studio 2026), `pip install cmake==4.2.0 ninja pefile==2024.8.26 unicorn==2.1.4 pillow`,
   `ffnx\vcpkg\bootstrap-vcpkg.bat -disableMetrics`. Use overlay triplets
   `x86-windows-static` / `x64-windows-static` with static CRT and library
   linkage and `VCPKG_BUILD_TYPE release`.
3. Configure from an x86 `vcvarsall` environment:

   ```
   cmake -S ffnx -B ffnx/.build -G Ninja -DCMAKE_BUILD_TYPE=Release
     -D_DLL_VERSION=1.24.3-lexeditor51-runtime
     -DCMAKE_TOOLCHAIN_FILE=<ffnx>/vcpkg/scripts/buildsystems/vcpkg.cmake
     -DVCPKG_OVERLAY_TRIPLETS=<triplets> -DVCPKG_TARGET_TRIPLET=x86-windows-static
     -DFFNX_DEPLOY_TO_GAME_DIRS=OFF
     -DFFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON -DFFNX_LEXEDITOR_LIVE_CONDITIONS=ON
   ```

   Both `FFNX_LEXEDITOR_*` gates must read `BOOL=ON` in `CMakeCache.txt`.
4. Build with `cmake --build ffnx/.build --config Release --parallel 4`.
   `ffnx/.build/bin/FFNx.dll` is `AF3DN.P`.
5. Verify the artifact before packaging it:
   `tests/verify_ff8_linked_runtime.py --verifier ffnx/tools/verify_issue51_runtime_artifact.py --driver AF3DN.P`,
   `tests/verify_ff8_no_magic_consumption.py`, `tests/verify_ff8_modern_controls_binary.py`,
   `tests/verify_ff8_reptile_atb_binary.py` (each `--driver AF3DN.P`),
   `tests/verify_ff8_hp_colors_issue_481.py --compile` and
   `tests/verify_ff8_interaction_indicators_302.py --compile --compiler cl`.
6. Package with `tools/package_ff8_native_driver.py`, which rewrites the pinned
   manifest hashes.

Build outside the checkout (for example `%TEMP%/lexeditor-dev`); a full vcpkg
tree is about 16 GB.
