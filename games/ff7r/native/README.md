# FF7R native runtime probe

This directory is the native-runtime investigation surface for issues #413 and #414.

## Why this exists

The FF7R DataObject/PAK editor cannot implement either requested behavior by itself:

- cutscene playback speed is runtime event-scene logic;
- tap-versus-hold map input and persistent minimap visibility are runtime input/UI logic.

`LexeditorFF7RRuntimeProbe.dll` is therefore deliberately **not** named
`LexeditorFF7RRuntime.dll`. The normal runtime deployment code must never mistake
this diagnostic binary for an implementation of the requested behavior.

## Loader contract

The DLL exports `extern "C" void __cdecl Init()`, matching the public Native Mod
Loader contract used by current FF7R native mods. Place the probe in the game's
`NativeMods` directory with a compatible loader installed. On startup it scans the
main executable's `.text` section and writes:

`NativeMods/LexeditorFF7RRuntimeProbe.json`

No executable bytes are modified and no hooks are installed by the probe.

## Evidence collected

The report records:

- executable path and size;
- loaded `.text` base and size;
- match addresses for two signatures independently used by the current
  MIT-licensed `TheUnlocked/ff7r-kbm-hook` project (map-control and raw-input
  initialization compatibility probes);
- occurrences of candidate runtime strings including `FastForward`, `EventScene`,
  `Navimap`, `HideNavimap`, and `TimeDilation`.

The two known signatures establish whether the installed executable resembles a
build already supported by a maintained native FF7R mod. They are **not** treated
as the cutscene/minimap patch sites.

## Build

On Windows with Visual Studio C++ tools:

```powershell
cmake -S games/ff7r/native -B out/ff7r-native -A x64
cmake --build out/ff7r-native --config Release
```

The `FF7R native runtime probe` GitHub Actions workflow performs the same build and
verifies that the resulting DLL exports `Init`.

## Completion criterion

The probe is investigation infrastructure, not acceptance for #413/#414. Those
issues remain source-incomplete until the real runtime DLL has validated patch
sites that:

1. apply the configured base multiplier only to eligible event scenes;
2. compound held-R2 native fast-forward on top of that base multiplier;
3. preserve ordinary gameplay speed;
4. distinguish map-button tap from hold without double-triggering;
5. retain the player's minimap choice through the automatic hide/show transitions
   targeted by #414.
