# Lexeditor issue 51 FFNx derivative build report

## Source and artifact identity

- FFNx source commit: `c056db2783f376a340fcefa6a48cc33618998876`
- Supported `FF8_EN.exe` SHA-256: `064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`
- Runtime identity: `Lexeditor issue 51 shared magic core; base=c056db2783f376a340fcefa6a48cc33618998876; runtime=on; hooks=28`
- Configuration contract: `Lexeditor issue 51 config: <basedir>/<direct_mode_path>/lexeditor/gameplay.toml; schemaVersion=1; sharedMagicInventory=bool; magicStockLimit=int[1,255]; missing=false; invalid=false; unknown=false`
- Function-entry hooks: 28
- Exact call-site patches: 4
- Total transactional patch sites: 32
- Driver: `.build/bin/FFNx.dll`
- Driver SHA-256: `655ca256e95bfc48e6d5a8d1e969ca75276f278d6d830d9d573142eee607a473`
- Driver size: 38,537,728 bytes
- Driver format: PE32, x86, machine `0x014C`
- PDB: `.build/bin/FFNx.pdb`
- PDB SHA-256: `760bb4e93c9f4259e4bfc53ea430931702ba24eaf0a2fe2ef97e020d43af222f`
- Source patch SHA-256: `e7f2a705f6ce7ee0fa034d82ecd77a22af9aba170b509293691554bf983d4e7b`
- GPL license SHA-256: `230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`

## Toolchain

- CMake 4.2.0, Windows x86_64 distribution
- CMake archive SHA-256: `cf35a516c4f5f4646b301e51c8e24b168cc012c3b1453b8f675303b54eb0ef45`
- Ninja 1.12.1 from Visual Studio 2022 Build Tools
- MSVC 19.44.35221, x86 target
- vcpkg commit: `c3867e714dd3a51c272826eea77267876517ed99`
- vcpkg triplet: `x86-windows-static`
- vcpkg manifest SHA-256: `ff34f66eb8a4a5102878ce64edc0533eac25ea50a26f36e4d623d81943a3ca4e`
- vcpkg configuration SHA-256: `ee2d7834ff24b12ace82ec2469a9f78bfd3755c889aefb849cda65176556eaf1`

## Reproducible configuration and build

From an exact checkout of the source commit, apply `ISSUE51_DERIVATIVE_SOURCE.patch`. Then use an x86 MSVC environment:

```text
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86
cmake -S . -B .build -G Ninja -DCMAKE_BUILD_TYPE=Release -D_DLL_VERSION=1.24.3-lexeditor51-runtime -DCMAKE_TOOLCHAIN_FILE=vcpkg/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x86-windows-static -DCMAKE_MAKE_PROGRAM="C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" -DFFNX_DEPLOY_TO_GAME_DIRS=OFF -DFFNX_LEXEDITOR_SHARED_MAGIC_RUNTIME=ON
cmake --build .build --parallel 13
```

Both feature and deployment options default to OFF in source. This reviewed derivative explicitly enables the runtime and explicitly keeps deployment OFF.

## Verification

- Strict C++ configuration parser matrix: PASS.
- Missing, false, invalid, malformed, unknown, wrong-type, unreadable, and invalid-UTF-8 inputs fail closed.
- Runtime source verifier: PASS, 150 source mutations rejected.
- MSVC x86 object checks: PASS for runtime, core, FF8 data, and changed common code.
- Linked artifact verifier: PASS, 11 binary mutations rejected.
- Export bodies prove hook count 28, compile gate 1, core linked 1, config version 1, compiled call-site count 4, and total patch-site count 32.
- The runtime-requested export remains dynamic.
- Identity and config exports return their exact strings. The strict config passes one `magicStockLimit` value from 1 through 255 to the runtime and the native overstock warning renders that configured cap.
- The source patch applies cleanly to the exact base commit.
- Final `verify-issue51-build.ps1`: PASS.
- Recursive game-root manifest: 733 files compared, zero changes.
- Top-level game-root hashes: zero changes.
- No driver was installed and the game was not launched.

## Integration deviations from the hook worktree

- The derivative keeps the proven standalone `lexeditor_shared_magic_config` parser and removes the hook worktree's duplicate parser.
- `common.cpp` resolves `<basedir>/<direct_mode_path>`, records the exact config path, applies the strict parser once, and sets the runtime request before FF8 hook initialization.
- The pure core uses the `lexeditor_shared_magic_core` filename but is behavior-identical to the tracked issue-51 core.
- Required package-name exports are compile-gated wrappers. Dynamic runtime diagnostics remain separate.


## 2026-09-05 tweak repair build

Latest follow-up: Party Switch resolves native saved character names and uses
the four-argument menu renderer plus a native panel. Fast Start masks only
startup publisher/credits presentation, with a one-way gate ending at the
main menu or gameplay. The native transition remains deferred and unchanged.
The prior native HUD HP capture and yellow inset XP bars remain included.
Name-renderer execution and compiled startup-gate tests pass. Live appearance
of these latest repairs remains unverified. Shared Magic with Party Switch
still requires integration and stays blocked for this test.

Rebuilt with MSVC x86 Release. Corrected XP result-state ownership and result-page gating, resolved HP/menu driver modes, added the FF8-only Fast Start logo flag, captured native EXP result panel geometry with the active viewport and FFNx output transform, and added guarded native Modern Controls and Party Switch modules. Modern Controls separates right-stick camera input from native movement/zoom and automatic follow. Party Switch uses separately scheduled generic replacement primitives rather than the special encounter callback. Compiled camera policy/native follow and three-slot replacement execution tests passed. Shared Magic with Party Switch remains blocked pending combination validation. The linked runtime verifier and native result-state execution checks passed. The source patch matches the build tree. In-game appearance and startup acceptance remain unverified.
