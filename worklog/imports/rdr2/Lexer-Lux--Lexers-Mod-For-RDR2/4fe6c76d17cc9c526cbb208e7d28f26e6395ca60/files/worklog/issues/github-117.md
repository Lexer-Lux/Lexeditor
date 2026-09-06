# GitHub #117 - adjustable pause-map zoom speed

## Root cause of the four previous failures

### 1. Pause-map zoom is not script-reachable at all

Grepped `_downloads/RDR2-Decompiled-Scripts/script_rel/` (1639 scripts):

- `map_app_event_handler.c` (3827 lines) contains **no** `zoom`, **no**
  `PAD::` native of any kind, and **no** `MAP::` zoom native. Its entire native
  surface is `DATABINDING::*`, `MISC::GET_HASH_KEY`, `TXD`, `UIAPPS`, blip
  reads. It only feeds data to the UI app; it does not handle input.
- `pause_menu.c` (27466 lines) likewise contains **no** `zoom` match and **no**
  `PAD::` native.
- The only zoom native used anywhere in Story Mode is `MAP::SET_RADAR_ZOOM`,
  always with `Global_36308[...]`, and always for the in-world minimap radar.
- `joaat("MAP")` + `UIAPPS::_IS_APP_ACTIVE_BY_HASH` is confirmed as the right
  app identity (`doc_newspaper.c:3427`, `map_app_event_handler.c:273`).
  `_IS_APP_ACTIVE_BY_HASH` is `0x25B7A0206BDFAC76`, which is what
  `script.cpp:284 UIAPP_ACTIVE` invokes.

Conclusion: pause-map zoom lives entirely inside the native MAP UIApp and reads
the engine control manager. There is no script global, no script handler and no
native setter to change. Attempts 1-2, which wrote the script-side
control-value override buffer, could never be seen by that code. That matches
the observed result exactly: no effect on mouse **and** no effect on gamepad.

### 2. Attempts 3-4 never delivered anything - the "MAP rejects SendInput"
conclusion was never actually tested

`GameplayTweaks.map-zoom.log` in the game root (1025 bytes, 28 lines, spanning
tick 614200656 to 628551937, i.e. ~28 separate process launches over ~4 hours)
contains **only** `config` lines:

```
622810109 config raw=99 applied=99
622823046 config raw=0.0001 applied=1
622914234 config raw=999 applied=999
624684703 config raw=999 applied=999
... (six more launches at applied=999)
```

Not one `source=`/`requested=`/`sent=` burst line exists, including in the
sessions that ran at 999x. `emitWheelBurst` was the only place that logged
delivery, so its absence proves `update()` never got past its gates:
`UIAPP_ACTIVE(joaat("MAP"))` was false, or neither the PAD wheel-magnitude read
nor the XInput RS-Y read ever fired. Windows delivery and MAP acceptance were
never exercised.

(The repeated identical `config` lines are not a logging bug: `GetTickCount` is
system uptime, and the `logged` static resets on each ASI load, so each line is
one game launch.)

### 3. Independent corroboration: #14 fails at exactly the same gate

`updatePauseMapRecenter` in `modules/collectibles_map.cpp:823` splits on the
same `UIAPP_ACTIVE(joaat("MAP"))` test. Lexer's #14 report:

> "map does seem to open to my location, which is good. there's no prompt for
> the recenter button, nor does it do anything on gamepad nor KBM"

The **ungated** branch (`setPauseMapFocusToPlayer`, run while MAP is *not*
active) demonstrably works. Every statement in the **gated** branch - prompt
visibility, MMB/R3 handling, and its own `GameplayTweaks.map-recenter.log`,
which does not exist in the game root - produces nothing. Two unrelated
features fail identically the moment the pause map is open.

So the prime suspect for #117 was never the zoom mechanism. It is that nothing
on the ASI script thread gated on the open pause map runs, or reports, at all.

## What was changed

`GameplayTweaks/modules/pause_map_zoom.cpp` was rewritten (266 lines) to remove
every dependency on the game's script control layer and to make the log answer
the remaining question.

- **Detection moved off the script control layer entirely.** A `WH_MOUSE_LL`
  low-level mouse hook runs on a dedicated `CreateThread` worker with its own
  `PeekMessageW` pump (`mouseProc`, `hookThread`). Physical wheel notches come
  from Windows, not from `PAD::GET_CONTROL_NORMAL` on
  `INPUT_CURSOR_SCROLL_UP/DOWN`, which never fired in four installed builds.
  Controller RS-Y is polled with `XInputGetState` on the same thread, so
  neither source needs the script thread to be running.
- **Recursion guard is now structural.** Our own `SendInput` bursts return
  through the hook flagged `LLMHF_INJECTED` and are skipped, replacing the
  100 ms time window.
- **Delivery happens on the pump loop, not inside the hook callback**, so a
  30-event burst can never trip Windows' low-level-hook timeout.
- **Gate widened and published as a deadline.** The script thread sets
  `g_gateOpenUntil = now + 1500` when any of `UIAPP_ACTIVE(joaat("MAP"))`,
  `IS_PAUSE_MENU_ACTIVE` (`0x535384D6067BA42E`) or
  `_UI_IS_SINGLEPLAYER_PAUSE_MENU_ACTIVE` (`0x4FFA0386A6216113`) is true. If the
  MAP-app hash is the wrong gate (the #14 signature), the pause-menu natives
  still open it; the short deadline stops a stalled script thread leaving wheel
  multiplication latched on during normal play.
- **Two heartbeats.** The log is truncated at module start and then carries
  `hb script mapApp=/pauseMenu=/spPause=` and `hb hook open=/hook=` once per
  second, capped at 40000 lines. Delivery lines are
  `wheel source=... requested=N sent=N lastError=E`, plus explicit
  `skip ... reason=not-foreground` and `wheel ignored reason=gate-closed`.

The log now distinguishes "we delivered input" from "the map ignored it", and
also from the two upstream failures that actually occurred:

| Log signature while the map is open | Meaning |
|---|---|
| `hb hook` continues, `hb script` stops for the whole duration | The SP script thread is suspended by the pause menu. Nothing script-gated is reachable while the pause map is up; #14 has the same root cause and #117 is **unfeasible from an ASI script thread** and should be relabelled. |
| `hb script` continues with `mapApp=0` | The MAP UIApp hash is the wrong gate; `pauseMenu=`/`spPause=` in the same line say what to gate on. |
| `hb script mapApp=1`, but no `wheel` line on scroll | The low-level hook is not seeing the device (raw/exclusive input path). |
| `wheel ... sent=N` present and zoom is still vanilla | Input **was** delivered and MAP ignores duplicate wheel notches. Only this outcome proves the mechanism itself is dead. |

Also updated: `GameplayTweaks/ini-fragments/github-117.ini` and the `[Misc]`
`MapZoomSpeedMultiplier` comment block in `GameplayTweaks/GameplayTweaks.ini`
(mechanism + diagnostic note; the value Lexer set, 999, was left alone), and
the issue-local static checker
`tools/reverse-engineering/verify_pause_map_zoom_issue_117.py`.

## Static verification

`python tools/reverse-engineering/verify_pause_map_zoom_issue_117.py` - PASS.
It now requires the low-level hook, the physical-wheel message, the
`LLMHF_INJECTED` guard, the pumped thread, direct XInput RS-Y, bounded
foreground-only `SendInput` delivery, all three gate natives, the published gate
deadline, the burst cap, hot reload, the log cap, and both heartbeats plus the
delivery/`lastError`/config evidence lines. It **rejects** every mechanism
already disproven at runtime: script control-value next-frame injection,
`SET_RADAR_ZOOM`, control suppression, and `INPUT_CURSOR_SCROLL` PAD detection.

Brace/paren/bracket balance on the module checks out. No build, link, install or
ASI copy was performed; no shared dispatcher, manifest, generated index, GitHub
state/label change, commit or push.

## Honest feasibility statement

Item 1 above is settled and will not change: the pause map's zoom **rate** is
not a script-visible value. Nothing an ASI can write will change how far one
notch zooms. The only remaining avenue is the one implemented here - delivering
additional genuine input events - and whether that avenue is alive depends
entirely on whether the ASI script thread and an OS-level hook can act while the
pause map owns the screen. That is precisely what the previous four builds never
measured, because they logged only at the point of delivery.

This build is therefore an instrumented implementation, not a fifth guess. If
the next run shows the `hb hook` / `hb script` gap described above, the correct
outcome is to relabel #117 as unfeasible (and revisit #14 with the same
finding), not to try a sixth mechanism.

## Runtime acceptance

Open the pause map for ~20 seconds with `MapZoomSpeedMultiplier=999`, scroll the
wheel several notches in both directions, and push the controller right stick up
and down. Close the map, then attach `GameplayTweaks.map-zoom.log` from the game
root. Read it against the table above before changing any code.

## 2026-08-09 correction from the actual runtime report

Lexer's follow-up already answered the remaining question: the map **did**
accept the injected wheel events. At 999 the first scroll produced an error
beep and one very large zoom, then reverted to vanilla speed; at 5 it produced
more beeps and a longer stall. The previous feasibility statement was therefore
stale. The feature is feasible, but its delivery and lifetime were wrong:

- `SendInput` flooded up to thirty separate wheel events in one call. That was
  the direct source of the beeps/stalls.
- `g_gateOpenUntil = now + 1500` expired while the ScriptHook thread was
  suspended by the map. That exactly explains why acceleration worked only at
  the start and then became vanilla for the rest of the map session.

The source now latches the pause transition open until the script thread resumes
after the frontend closes. Extra notches are capped in a 30-notch queue and
delivered one at a time every 20 ms. Direction changes discard opposite queued
momentum. The hook heartbeat records the current queue plus cumulative delivered
and failed counts, and delivery failures still include `GetLastError`.

The crash bisect's temporary `MapZoomHookEnabled=0` gate was removed: the freeze
persisted with the hook absent and the active crash investigation subsequently
isolated the suspect path to recon. A multiplier of 1.0 leaves the hook purely
observational.

`verify_pause_map_zoom_issue_117.py` now rejects the old bulk burst and requires
the session latch plus paced one-event delivery. It passes, and development ASI
`B6AB21D942A05E930882286F5D3ADECEC10D52D1D77A178244C3B98A3360B9F1`
builds successfully. It is not installed over the pending recon-crash build, so
#117 remains `actionable` and no label was changed.

## Installed handoff

The session-latched, paced delivery shipped in development ASI
`BEBA903A3DFEBC5ED2028297B7B171DFCE48103CA67421139718E7040C7031A5`;
source and game-root hashes match. #117 was manually changed from `actionable`
to `test me` and read back as open with only `test me`. Test 1, 5 and 999 in one
map session: acceleration must persist until the map closes, reverse immediately,
and produce no Windows beep or visible stall.

## Final runtime verdict

Lexer's 1/10 comparison proved the installed mechanism did not change zoom-step
strength. A value of 10 merely queued roughly fifty equally sized native steps,
paused the map, then replayed them with inconsistent hitches; 0.01 and 1 felt
the same. That is not the requested adjustable zoom speed. The MAP UIApp has no
script-visible zoom-strength value, and the only externally reachable path was
synthetic repetition of ordinary input.

The rejected module, dispatcher call, INI fragment, editor setting, hook, and
`SendInput` queue have been removed. The replacement verifier asserts they stay
absent. After the removal is built and installed, #117 is `unfeasible`, not
`test me`.

## Integrated removal

Development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`
is installed with the rejected hook absent; source and game-root hashes match.
Workflow after install: `unfeasible`.
