# Build and installation

Compile ASIs with VS2022 Build Tools and `RDR2_SDK`:

Use the project's own `GameplayTweaks/build.bat` (invoke it by ABSOLUTE path).
Do not hand-write the compile line: the command previously documented here
omitted `user32.lib xinput.lib` and fails at link with six unresolved externals
(`GetAsyncKeyState`, `GetCursorPos`, `XInputGetState`, ...). The working line is:

`cl /nologo /O2 /EHsc /MT /LD main.cpp script.cpp /I C:\RDR2Mod\_downloads\RDR2_SDK\SDK\inc /link C:\RDR2Mod\_downloads\RDR2_SDK\SDK\lib\ScriptHookRDR2.lib user32.lib xinput.lib /OUT:Name.asi`

`GameplayTweaks/script.cpp` owns shared native wrappers, configuration/runtime
state, and `ScriptMain`. Topic implementations live under
`GameplayTweaks/modules/` and are included by `script.cpp` in dependency order,
so the project still compiles as one translation unit and produces one ASI.
Do not also pass `modules\*.cpp` to `cl`; they are not independent translation
units until their shared `static` state is promoted behind explicit headers.

`vcvars64.bat` prints a harmless `vswhere.exe is not recognized` line on this
machine; it still sets up the toolchain. Exit code 0 is the signal, not silence.

- Copy a rebuilt ASI to the game root immediately. A loaded ASI may be renamed
  to `.asi.loaded` and replaced for the next launch.

- `Install-When-RDR2-Closes.ps1` installs each payload independently and hash-
  verifies it, writes a per-file report to `install-when-closed.log`, and exits
  non-zero if anything required failed. It used to run under
  `ErrorActionPreference Stop` with one `Copy-Item` per line, so the missing
  optional `CoreVignetteRamp\CoreVignetteRamp.ini` aborted the script BEFORE the
  `GameplayTweaks.asi` copy — every deferred install silently shipped nothing and
  left a stale ASI loaded. Never trust a deferred install without reading its
  report or comparing source and installed hashes.

- ASI changes require a complete game restart.
- Data/localization changes require a complete game restart unless explicitly
  known to hot-reload.
- `GameplayTweaks.ini` is hot-reloaded approximately every two seconds. The
  project and game-root copies are currently separate files; synchronize them
  after edits and verify their hashes before testing.

- `Install-When-RDR2-Closes.ps1` copies the project `GameplayTweaks.ini` over
  the game-root copy and hash-verifies it. The game-root copy is also where the
  in-game camera editor writes Lexer's live tuning, so a deferred install
  silently reverts any value he changed in-game to whatever the project file
  holds. Before queuing an install, diff the two INIs, carry his game-root
  values into the project file, and tell him about anything not carried over.
  Editing only the game-root copy does not survive the next install either.
- Lexer's normal preference is vanilla-ish data; enable `MyOverhaul` only for
  explicit testing. Verify source/install hashes when editor and game differ.
- Never launch Online with LML, ScriptHook, `dinput8`, or ASIs active. The mode
  switch scripts exist, but moving the stack also disables all Story mods and
  requires Lexer's explicit permission.

### Do not make Lexer babysit the loop (he has asked for this explicitly)

Every avoidable "relaunch the game / edit this ini / press this key / send me the
log" round-trip costs him real time. Minimise them:

- **Never leave a diagnostic behind an ini switch he has to flip.** Default new
  probes/logging to ON while in the dev phase; they should work the moment he
  loads the game. (This was gotten wrong repeatedly with `[CollectibleProbe]`.)
- **Never ask him to install a build.** If `RDR2.exe` is running the `.asi` is
  file-locked, so start a background watcher that waits for exit, copies, and
  hash-verifies — do not tell him to close the game or do it himself.
- **Log everything a probe could plausibly need in ONE pass**, not one fact per
  launch. Guessing one control/native at a time and asking him to relaunch each
  time is the main way rounds get burned.
- **Grep the decompiled scripts BEFORE probing in-game.** The full decompiled
  script set is at `_downloads/RDR2-Decompiled-Scripts/` (`script_rel/` = SP).
  Most script-side questions (coordinates, entity names, stat IDs, native usage)
  are answerable there with no game launch at all. Likewise use
  `python _downloads/grep_natives.py PATTERN`, not `natives.h`, which is
  incomplete and omits whole native families.
- Prefer changes that hot-reload (`.ini`) over ones needing a restart when both
  can achieve the goal, and say clearly which a change requires.


