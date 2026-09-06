# GitHub #10 — Customizable Minimap Zoom

## Requirement

The `[Minimap] ZoomLevel` setting had to visibly change the live minimap and
hot-reload after saving the INI. The deliberately extreme negative and positive
test values had both produced no change.

## Diagnosis

The implementation called native `0xCAF6489DA2C8DD9E` (`SET_RADAR_ZOOM`) every
frame with an arbitrary integer. RDR2's native database inherited that name and
signature from GTA, but the shipped Story Mode scripts pass it a live blip
handle immediately before removing that blip. It was therefore not evidence of
a continuous live-minimap scale control, and huge INI values were meaningless.
`GetPrivateProfileIntA` also could not safely represent the user's test values.

Story Mode's `medium_update` changes the live minimap scale with native
`0x9C113883487FD53C` (`_SET_RADAR_CONFIG_TYPE`). The engine exposes discrete
`RADAR_CONFIG_*` records with authored scale values from 1.1 through 10.0, not
an arbitrary continuous scalar.

## Implementation handed to integration

`GameplayTweaks/modules/collectibles_map.cpp` added
`updateCustomMinimapZoom(DWORD now)`. It reads `Minimap/Enabled` and
`Minimap/ZoomLevel` as strings every two seconds, safely parses very large
values, clamps them to 1.1–10.0, selects the nearest real Rockstar preset, and
reasserts that preset every frame so Story Mode's normal movement/location
config switching cannot overwrite it. Changes are recorded only when the INI
is reread in `GameplayTweaks.minimap.log`.

Integration must make these shared-file changes:

1. In `GameplayTweaks/script.cpp`, replace the per-frame block
   `if (g_minimapEnabled) SET_RADAR_ZOOM(g_minimapZoom);` with
   `updateCustomMinimapZoom(now);`.
2. Remove the obsolete `SET_RADAR_ZOOM` wrapper, `g_minimapEnabled`,
   `g_minimapZoom`, and their two assignments in `loadConfig` once no other
   references remain.
3. In `GameplayTweaks/GameplayTweaks.ini`, describe `ZoomLevel` as a requested
   scale from 1.1 (most zoomed in) to 10.0 (most zoomed out), with nearest-preset
   selection, and change the shipped default from the obsolete `1100` value to
   `5.0`.

No dispatcher, INI, editor, generated index, build, install, GitHub state,
commit, or push was performed by the feature agent.

## Static evidence and runtime acceptance

Static inspection found 485 Story Mode calls to `SET_RADAR_ZOOM`: 483 receive a
handle from the `Global_36308` blip registry, and the remaining two receive the
stagecoach blip immediately before `REMOVE_BLIP`. `medium_update` instead uses
`_SET_RADAR_CONFIG_TYPE` for ordinary riding, walking, town, wilderness,
indoor, wanted, and scripted radar scale changes.

After integration builds and installs the ASI:

1. Set `Enabled=1`, `ZoomLevel=1.1`, save, and wait at least two seconds. The
   minimap must visibly zoom in without restarting the game.
2. Change only `ZoomLevel` to `10.0`, save, and wait at least two seconds. The
   minimap must visibly show substantially more area.
3. Repeat with the user's huge negative and positive values. The log must show
   clamping to 1.1 and 10.0 respectively, and the minimap must switch between
   the same two visible limits.
4. Walk, run, ride, and cross a town boundary. The selected zoom must remain
   stable instead of reverting when Story Mode changes its own radar config.
5. Set `Enabled=0` and confirm the ASI stops asserting its custom config; then
   cross a movement/location state boundary and confirm vanilla dynamic zoom
   resumes.

## Runtime rejection

The installed per-frame preset assertion visibly oscillated between the chosen
config and Story Mode's `medium_update` config: the minimap continually zoomed
out and snapped back in. The override was disabled in both the installed and
source INI, and release code hard-gated it off, pending a proven ownership
mechanism.

## Ownership mechanism found — `Global_1911667`

`_downloads/RDR2-Decompiled-Scripts/script_rel/medium_update.c`, `func_330`
(lines 9360–9447) is the radar-config selector that beat the old
implementation. Its structure is the answer:

```
if (Global_1911667 == 0) { ...wanted / mounted / speed / interior selection... }
else                     { iVar1 = Global_1911667; }
if (iVar1 == iLocal_39) return;          // native only fires on a CHANGE
iLocal_39 = iVar1;
MAP::_0x9C113883487FD53C(iLocal_39, 0);
```

`Global_1911667` is Rockstar's own sanctioned radar-config override slot. While
it is non-zero the game performs no selection at all and simply uses the value.
Shipped writers confirm the protocol — write a `RADAR_CONFIG_*` hash to force,
write `0` to release:

- `mudtown3b.c:57826` (`func_1533`) — per frame: inside the area, set
  `RADAR_CONFIG_INDOOR` only if not already set; outside, reset to 0 **only**
  `else if (Global_1911667 == RADAR_CONFIG_INDOOR)`.
- `mob5.c:18226, 36800, 56062`, `winter1.c:18681, 35952, 73627`,
  `winter4.c:18841, 66657`, `saint_denis1.c:14765, 37448, 79021, 111764` —
  one-shot set/clear on state transitions.

Every literal `func_330` selects joaats back to a `RADAR_CONFIG_*` name,
independently confirming the record set: `2080113112` WANTED, `-1986542417`
WANTED_WITNESSED, `-1943724816` RIDE_FAST_WILDERNESS, `347777538`
FOOT_FAST_WILDERNESS, `-2024960240` FOOT_FAST_TOWN, `-280612398`
RIDE_SLOW_TOWN, `-189036996` FOOT_SLOW_WILDERNESS, `455950385`
RIDE_SLOW_WILDERNESS, `-117986897` FOOT_SLOW_TOWN, `642254004` RIDE_FAST_TOWN,
`-789269373` CARAVAN, `-547506804` INDOOR.

## Rewrite (this pass)

`GameplayTweaks/modules/collectibles_map.cpp`:

- `updateCustomMinimapZoom` no longer invokes `0x9C113883487FD53C` at all. It
  publishes the chosen config hash into `*getGlobalPtr(1911667)` and lets
  `medium_update` apply it.
- Writes only when the slot differs from the desired value, so the steady state
  is zero writes per frame.
- Yields the slot to any foreign value (mission-forced config) and refuses to
  write for 3 s afterwards (`kMinimapZoomBackoffMs`).
- On `Enabled=0` it writes `0` back, but only if the slot still holds our own
  value, so vanilla dynamic zoom resumes and no mission override is stomped.
- `kCustomMinimapZoomRuntimeEnabled` back to `true`; `GameplayTweaks.ini`
  `[Minimap] Enabled=1`, `ZoomLevel=1.1`.
- Diagnostics: `GameplayTweaks.minimap.log` gets one line per *transition*
  (`applied` / `yielded to script` / `released`) with both the previous and new
  slot value decoded to `RADAR_CONFIG_*` names, plus a `settings` line only when
  the parsed INI values actually change. Nothing is logged per frame, so any
  oscillation would appear as an obvious repeating pair in one file.

Why it cannot oscillate: there is now exactly one writer of the live radar
state (`medium_update`), we are not it; while our hash sits in the slot the
game skips selection and its `iVar1 == iLocal_39` guard suppresses the native;
we write only on difference; and a script that reclaims the slot forces a 3 s
back-off, bounding even a pathological conflict to one change per three seconds.
No per-frame zeroing writer of `Global_1911667` exists in the shipped scripts.

Integration note: no shared-file change is required for this pass — `script.cpp`
already calls `updateCustomMinimapZoom(now)`. Not compiled, installed or
committed by the feature agent.

## In-game acceptance for this pass

1. `Enabled=1`, `ZoomLevel=1.1`, save, wait 2 s — minimap zooms in and stays
   put while walking, sprinting, riding, and crossing a town boundary. No throb.
2. `ZoomLevel=10.0`, save, wait 2 s — visibly more area, again stable.
3. Enter an interior/mission that forces its own radar zoom — the game's zoom
   wins, and the log shows a single `yielded to script` line, not a stream.
4. `Enabled=0` — vanilla dynamic zoom resumes; log shows one `released` line.

## Current actionable pass

LEXEDITOR now represents `ZoomLevel` as the real 1.1-10.0 range and clamps both
the visible input and server-side save to that schema. This prevents a value
such as 1 from being displayed even though runtime clamps it to 1.1. JSON,
Python, settings, and minimap verifiers pass. Runtime acceptance remains the
stable 1.1/10 comparison and mission-yield checks above.

## Integrated release

Installed in development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Source and game-root hashes match. Workflow after install: `test me`.

## 2026-08-10 actionable correction: expose vanilla expanded radar

Lexer's observation that the radar shows more area while the radar control is
held is correct. Extracted control data identifies a separate binary action,
`INPUT_EXPAND_RADAR`; it is not another `RADAR_CONFIG` numeric preset. The local
native reference exposes `SET_CONTROL_VALUE_NEXT_FRAME` at
`0xE8A25867FBA3B05E`.

`[Minimap] Expanded=1` now drives that exact vanilla action while the selected
base config is owned, and `Expanded=0` leaves it normal. The setting hot reloads
on the existing two-second poll, is represented in LEXEDITOR, and is logged only
when settings change. The 1.1-10.0 numeric range remains truthful rather than
pretending the binary expansion is a continuous value. The #10 verifier and
release build pass. In-game confirmation is still required after the combined
hash-verified install, so #10 remains `actionable` until then.
