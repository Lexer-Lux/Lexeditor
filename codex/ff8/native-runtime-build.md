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
   `tests/ff8/verify_ff8_linked_runtime.py --verifier ffnx/tools/verify_issue51_runtime_artifact.py --driver AF3DN.P`,
   `tests/ff8/verify_ff8_no_magic_consumption.py`, `tests/ff8/verify_ff8_modern_controls_binary.py`,
   `tests/ff8/verify_ff8_reptile_atb_binary.py` (each `--driver AF3DN.P`),
   `tests/ff8/verify_ff8_hp_colors_issue_481.py --compile` and
   `tests/ff8/verify_ff8_interaction_indicators_302.py --compile --compiler cl`.
6. Package with `tools/package_ff8_native_driver.py`, which rewrites the pinned
   manifest hashes.

Build outside the checkout (for example `%TEMP%/lexeditor-dev`); a full vcpkg
tree is about 16 GB.

## What belongs in the driver (#671)

Hext first (AGENTS.md, Game patches): driver code only for drawing the game
has no routine for, renderer or frame-rate work, file I/O, or logic too large
to keep correct in hand-written assembly. Every feature the derivative
carries, and why:

| Feature | Driver source | Stays because | Move to Hext? |
| --- | --- | --- | --- |
| Shared Magic Inventory (#51) | `ffnx_issue_51`, `shared_magic_runtime` | 28 hooks plus merge, mirror and save-phase logic | No |
| Party Switch | `ffnx_party_switch` | Event-driven model retire/replace against a task pool, tied to Shared Magic | No |
| Modern Controls | `ffnx_modern_controls` | FFNx owns the gamepad layer and analog axes; FF8 never sees them | No |
| HP / XP / GF HP bars, HP colours | `ffnx_status_bars` | Draws gauges the game has no routine for; colours go through FFNx's renderer | No |
| Interaction indicators | `lexeditor_ff8_interaction_indicators` | Draws field cues the game has no routine for | No |
| Better Targeting | `ffnx_better_targeting` | FFNx replaces the native icon routine `004B75B0` wholesale, so a Hext patch there never runs | No |
| Fast Start | `fast_start_ffnx.py` | Suppresses presented frames in the renderer | No |
| Live conditions / asset lookup | `lexeditor_live_conditions` | File I/O | No |
| Signal Flare (item, shop, menu, encounters) | `lexeditor_ff8_flare*` | The encounter gate sits inside FFNx's own replacement of the battle trigger | Review: item, shop and menu parts may not need the driver |
| GF Spellbooks (#93) | `lexeditor_ff8_gf_spellbooks` | Reads `gf-spellbooks.bin` at run time | Candidate: Lexeditor writes the Hext per mod, so the book can be baked into it |
| Reptile ATB (#323) | `lexeditor_ff8_reptile_atb` | Reads `reptile-atb.toml` at run time | Candidate: same, bake the classification into the Hext |
| In-game Time | derivative patch (`enable_ff8_ingame_time`) | Relabels the native menu counter | Review: likely a Hext text or draw-call change |
| Toasts | `ffnx_toasts` | Draws an imitation box | Retire: messages go through the game's own box (#670) |
| No Magic Consumption | `lexeditor_ff8_stock_tweaks` | - | Moved: `plugins/ff8/no_magic_consumption.py`. The driver copy stays off and is deleted at the next rebuild |

