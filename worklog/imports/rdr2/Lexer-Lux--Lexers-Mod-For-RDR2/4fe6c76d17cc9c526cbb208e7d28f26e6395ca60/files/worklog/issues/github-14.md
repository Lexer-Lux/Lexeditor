# Worklog: GitHub 14

## Map Auto Center & Recenter

The live issue required the full map to open centered on the player and a
bottom-right `Recenter` prompt driven by middle mouse or controller R3/RS.

The earlier legacy investigation in `worklog/issues/todo-150.md` was obsolete.
The current native database names two direct MAP calls:

- `_SET_PAUSEMAP_COORDS_WITH_RADIUS` (`0xE0884C184728C75B`), taking player XYZ
  and a radius;
- `_CLEAR_PAUSEMAP_COORDS` (`0x7C9F4CDF402CA82A`).

Story Mode's `map_app_event_handler.c` confirmed that the full-map UI app is
named `MAP`. Its `MapFocus` databinding contains hovered-card presentation
state, not view coordinates, so the native was used instead of mutating UI
data or globals.

Implemented `updatePauseMapRecenter(Ped ped)` in
`GameplayTweaks/modules/collectibles_map.cpp`. It is deliberately a standalone
per-frame function for the integration dispatcher. While `MAP` is inactive it
keeps the native focus synchronized to the player's current coordinates; on
the opening edge it reapplies that focus. While the map is active, middle mouse
(`INPUT_CURSOR_SCROLL_CLICK`) or R3/RS (`INPUT_FRONTEND_RS`) reapplies it.

A native UiPrompt named `Recenter` is registered once, with middle mouse as its
control action and R3/RS as an allowed alternate action. It is enabled and
visible only while the MAP UI app is active. No custom HUD overlay was drawn.

Integration handoff: call `updatePauseMapRecenter(ped);` once per main-loop
frame after the current `Ped ped` has been resolved. Do not put it behind the
250 ms train-map timer: frontend just-pressed input and prompt presentation are
frame-sensitive.

Issue-local static checks confirmed the function, both input actions, MAP app
guard, focus native hash, and balanced source braces. No compile, ASI install,
GitHub state change, commit, or push was performed by the feature agent.

Runtime acceptance still required:

1. Move away from the last browsed map area, open the full map, and confirm the
   view is centered on the player at an ordinary usable zoom.
2. Pan away, press MMB, and confirm an immediate recenter.
3. Repeat with controller R3/RS.
4. Confirm `Recenter` joins the existing bottom-right map prompt collection and
   swaps to the correct glyph for the active input device.
5. Confirm the zero-radius point focus neither changes the ordinary opening
   zoom nor restricts panning. The native's center behavior is known, but those
   UI/zoom details cannot be established by static inspection.

## Integration

The integration dispatcher now calls `updatePauseMapRecenter(ped)` every frame.
GameplayTweaks built and installed with matching ASI SHA-256
`7E414A0625EC216CDD7147ADABEC6BFE7E7452EBCA95C42CE66FFCB2689E654A`.

The installed follow-up still failed unchanged in-game. The precise gap was
twofold:

- `_SET_PAUSEMAP_COORDS_WITH_RADIUS` is consumed when `MAP` launches. Calling
  it again while the app is already active did not pan the live map canvas.
  Rockstar's `doc_newspaper.c`, `doc_coach_robbery_note.c`, and
  `generic_document_inspection.c` all establish the real lifecycle: set the
  focus, then launch `MAP`.
- The custom prompt was assigned to and activated under a private prompt group.
  The active MAP frontend already owns the menu prompt collection, so that
  competing group prevented `Recenter` from joining it.

The source now makes the opening lifecycle explicit for an on-demand recenter.
An MMB or R3 edge primes the player focus and immediately closes only the MAP
app; on the following inactive frame it refreshes the player coordinates and
relaunches MAP. This replaces the proven-inert live-map native call with the
same focus-before-launch order used by Rockstar scripts. Ordinary opening
centering remains unchanged.

The `Recenter` UiPrompt is now an ungrouped, priority-2 standard prompt with
attribute 34 (manual-resolved coexistence), matching the pattern used for
frontend prompt collections. It no longer creates or activates a competing
prompt group. MMB remains the primary action and R3 remains an allowed action;
physical MMB and enabled/disabled group checks remain as input fallbacks.
The event-only `GameplayTweaks.map-recenter.log` records which input path
requested the relaunch and the MAP launch result, so a failed runtime test is
diagnosable instead of another unevidenced retry.

`python tools/reverse-engineering/verify_pause_map_recenter_issue_14.py`
passed eleven source contracts, rejects reintroducing a private/active prompt
group, and confirms the decompiled Rockstar focus-before-launch ordering.

No compile, install, GitHub state/label change, commit, or push was performed in
this source pass. Runtime acceptance still requires confirming that MMB and R3
perform the one-app relaunch and return centered, that the relaunch does not
escape the pause-map flow, and that the ungrouped prompt joins the existing
bottom-right collection with the correct active-device glyph.

## 2026-08-06 — resolved: auto-center ships, on-demand Recenter is unfeasible

Both prior attempts were wrong about the failure mode, and the correction did
not require another guess — the evidence was already sitting in the game folder.

### The script thread does not run while the pause map is open

`GameplayTweaks.map-zoom.log` (game root, written by the installed #117
instrumented build, truncate-once-per-launch, one `module start`) carries two
independent 1 Hz heartbeats:

- `hb hook` from a dedicated `WH_MOUSE_LL` thread — `pause_map_zoom.cpp:165`
  installs the hook, `:201-208` emits the line. 1454 samples.
- `hb script` from the ScriptHook script thread — `pause_map_zoom.cpp:255-263`,
  unconditional. 468 samples.

Findings:

1. Over `631539328 → 631609328` ms the hook thread logged **69** heartbeats with
   no gap above 1.1 s. The script thread logged **zero**. Seventy seconds of open
   pause map with not one script frame. The same log holds script gaps of 203 s,
   156 s and 125 s while the hook thread never misses a beat, and the script
   heartbeat stops for the final 140 s of the session entirely.
2. In **all 468** `hb script` samples, `mapApp` (`UIAPP_ACTIVE(joaat("MAP"))`),
   `pauseMenu` (`IS_PAUSE_MENU_ACTIVE`, natives.h:2242) and `spPause`
   (`_UI_IS_SINGLEPLAYER_PAUSE_MENU_ACTIVE`, natives.h:3274) read **0**.

So `UIAPP_ACTIVE(joaat("MAP"))` is not the wrong gate. There are no frames on
which to evaluate any gate. This is outcome 1 of the four `pause_map_zoom.cpp`
enumerated at `:44-47`, and it closes #117 and the gated half of #14 together.

The one and only event line the old build ever produced —
`631525000 requested middleMouse=1 rightStick=0 prompt=0`, then
`631525015 relaunch result=0` — sits in a sub-second sliver between two script
heartbeats that both read `mapApp=0`. It was a launch/teardown transition frame,
not an in-map press. `result=0` is the relaunch failing.

### Consequences

- A UiPrompt renders only while something sets it visible every frame. With zero
  frames, the `Recenter` prompt could never appear. Matches the report exactly.
- `PAD::` reads and `GetAsyncKeyState` on the script thread cannot observe a
  press that happens during a window in which the thread is suspended.
- The close-and-relaunch state machine was worse than dead: firing
  `_CLOSE_APP_BY_HASH_IMMEDIATE` (natives.h:7771) on a spurious transition frame
  would eject the player from the frontend they had just opened.
- No Rockstar script recenters a live map either. `grep -rin recenter` over
  `script_rel/` returns one unrelated volume name. All three users of the focus
  native (`doc_newspaper.c`, `doc_coach_robbery_note.c`,
  `generic_document_inspection.c`) use it only before launching MAP —
  `doc_newspaper.c:3425` then `:3427`. `map_app_event_handler.c` has no view
  state at all; its only databinding is `MapFocus` at `:100`, hovered-card
  presentation.

### Naming correction

The native is unnamed in the SDK: `natives.h:2898` declares it as
`MAP::_0xE0884C184728C75B`. The earlier entries above called it
`_SET_PAUSEMAP_COORDS_WITH_RADIUS`; that name appears nowhere in `natives.h` and
should not be repeated. Same for `_CLEAR_PAUSEMAP_COORDS` /
`0x7C9F4CDF402CA82A` (`natives.h:2899`, also unnamed). Every other hash used by
this feature did resolve: `_LAUNCH_APP_BY_HASH` natives.h:7777,
`_CLOSE_APP_BY_HASH_IMMEDIATE` :7771, `_UIPROMPT_SET_ALLOWED_ACTION` :2266,
`_UIPROMPT_IS_JUST_PRESSED` :2338.

### What changed

`GameplayTweaks/modules/collectibles_map.cpp:913-1030` — the whole #14 block was
replaced.

- Removed: `ensureMapRecenterPrompt` and the prompt globals, the in-map
  `PAD::`/`GetAsyncKeyState` polling, `_UIPROMPT_IS_JUST_PRESSED`, the
  close-app/relaunch-app state machine and `g_pauseMapRecenterRelaunchPending`.
- Kept unchanged: the focus write on every map-closed frame, which is the path
  Lexer confirmed working ("map does seem to open to my location").
- Added `logMapRecenter` (`:978`): truncates `GameplayTweaks.map-recenter.log`
  once per launch, caps at 20000 lines, and emits an **idle heartbeat**
  `hb mapApp=… frames=… focusWrites=…` once per second plus an unconditional
  `mapApp edge active=…` line on every transition. A silent stretch is now
  positive evidence the script thread stopped, and any future `hb mapApp=1`
  would be the new evidence required to reopen the gated half.

`tools/reverse-engineering/verify_pause_map_recenter_issue_14.py` rewritten: 7
source contracts plus 7 guards that fail if the prompt, the pad polling or the
close/relaunch machinery is reintroduced. Passes.

Not compiled, linked, installed or committed in this pass — static checks only
(verify script green, block and file braces balanced, both removed globals now
absent from the file).

### Verdict

Current release classification: the working pre-open auto-center remains. The
requested in-map prompt and MMB/R3 recenter cannot be implemented because the
ScriptHook thread does not tick while MAP is open. The verifier continues to
reject the dead prompt/input/relaunch machinery. After the combined build lands,
the issue is classified `unfeasible`; it is not another runtime test request.

Auto-center: shipped and working. On-demand Recenter (prompt + MMB/R3 while the
map is up): **unfeasible from an ASI script**, on the evidence above. Any future
attempt must first produce a `map-recenter.log` showing heartbeats continuing
with `mapApp=1` while the map is open; without that, the code cannot run.

## Integrated classification

Development ASI `696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`
is installed with the working pre-open center and without the unreachable
prompt/relaunch machinery. Workflow after install: `unfeasible`.

## 2026-08-09 periodic-focus startup abort

The 4 Hz focus refresh retained after the original per-frame freeze was not a
safe ownership boundary. On development ASI `1F20...`, the startup quarantine
held all gameplay updates for 14 seconds, then released. `map-recenter` wrote
the focus eight times over the following two seconds (`focusWrites=4`, then
`focusWrites=8`), after which Rockstar raised the same asynchronous
`ERROR:FFFFFFFF`. No vectored exception, Windows crash event, or minidump was
created, and the independent watchdog stopped with the script yielded at
`WAIT`. This reproduces the same symptom already attributed to the earlier
per-frame focus loop; reducing its cadence did not make the mutation owned.

The periodic refresh is removed completely. The focus native now runs once
only when `INPUT_MAP`, `INPUT_FRONTEND_PAUSE`, or
`INPUT_FRONTEND_PAUSE_ALTERNATE` is just pressed, before the frontend consumes
the input. That matches Rockstar's document scripts: one focus write directly
before launching MAP. It never writes merely because MAP is closed.

The on-demand in-map portion remains `unfeasible`; this repair does not reopen
the issue or change its workflow classification. The #14 verifier rejects any
periodic focus timer and requires the input-edge gate. Development ASI
`144FDA14CFF5426F1406FB8909E89A0399C50F7C6A952F7F722E2A3ADAD24E19`
was installed after RDR2 exited; source/game-root ASI and project/game-root
manifest hashes match.
