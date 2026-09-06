# GitHub #22 — Custom Crafting Menu

## Requirement read from the live issue

The custom presentation must appear at every vanilla crafting entry, show
vanilla and custom recipes together, preserve Rockstar's recipe/system data,
store an unlimited number of custom runtime recipes separately, and expose
those custom recipes to LEXEDITOR. The issue also calls for jewellery/valuable
breakdown into gold, silver, and platinum crafting materials.

## Reference evidence

- The installed `UCMO.asi` is **Ultimate Crafting Menu Overhaul 1.0**. Its INI
  configures a native-drawn menu, keyboard/controller controls, independent
  ingredient rows and yields. It implements multiple recipes by numbered INI
  names, but hard-limits each recipe to four `Requirement` fields. That storage
  format was therefore treated as presentation/interaction prior art, not
  copied as the new recipe schema.
- `_downloads/NativeMenuBase` is Halen84's MIT-licensed RDR2 Native Menu Base.
  It demonstrates Rockstar text/sprite drawing, scrolling, controller input,
  disabled gameplay controls and native prompts. Its README explicitly lists
  mouse support as unfinished. The #22 module uses the project's already-proven
  direct native-drawing style instead of importing the framework or adding a
  second menu runtime.
- `interactive_campfire.c` launches and closes the `CRAFTING` UI app and uses
  the `player_crafting_active` decorator. `simple_crafting.c` and
  `player_camp.c` share the underlying crafting machinery. Therefore observing
  the active `CRAFTING` UI app covers the presentation entry from portable and
  campfire contexts without taking ownership of their scenario/script state.
- The untouched `datasets/vanilla/catalog_sp.ymt` contains 275
  `COST_TYPE_CRAFT` rows. Those are exported to a read-only runtime snapshot;
  `catalog_sp.ymt` itself is not rewritten.

## Implemented isolated vertical slice

- Added `editor/custom_crafting.py`:
  - structured `Recipe` / `Ingredient` load and save;
  - atomic replace on save;
  - duplicate-ID, quantity, ingredient and optional catalog-key validation;
  - no recipe-count or ingredient-count ceiling;
  - deterministic vanilla snapshot export from catalog and localization data.
- Added `GameplayTweaks/custom_crafting_recipes.tsv`, the independent editable
  custom store. It now contains the reusable-canteen recipe plus 19 jewellery
  breakdown rows. Rings/earrings yield 1 unit, bracelets/buckles/lockets yield
  2, and necklaces/pocket watches yield 3.
- Added `GameplayTweaks/vanilla_crafting_recipes.tsv`, a generated read-only
  snapshot of all 275 shipped vanilla craft-cost rows.
- Added unregistered `GameplayTweaks/modules/custom_crafting.cpp`:
  - detects every active `CRAFTING` app and presents one unified, scrollable,
    full-screen list of vanilla plus custom recipes;
  - shows category/context, output, all required ingredients and live owned
    counts;
  - hot-reloads the two TSV files every two seconds and keeps the last-known-good
    pair if either file is malformed;
  - custom recipes preflight aggregated costs, remove ingredients, add output,
    and restore removed ingredients if a removal/output grant fails. Execution
    checks observed item counts rather than trusting native return values, and
    duplicate ingredient rows are aggregated for both availability and debit;
  - vanilla recipe selection hands input back to the already-running Rockstar
    app. This preserves the original station, recipe execution, animations,
    challenges and script events rather than faking them through inventory
    writes.

## Static evidence

- `python editor/custom_crafting.py export-vanilla ...` wrote 275 recipes from
  `datasets/vanilla/catalog_sp.ymt`, not from the modded output catalog.
- Catalog-aware validation passed all 275 snapshot recipes.
- A temporary round-trip fixture preserved 12 ingredients on one recipe,
  proving the storage/API has no four-ingredient ceiling.
- All 275 exported IDs were unique.
- A disposable integration copy including `modules/custom_crafting.cpp` built
  successfully with MSVC. Only the two existing C4838 warnings in
  `world_economy.cpp` appeared. No repository ASI was linked, installed or
  copied.
- `git diff --check` passed the issue-owned files.

## LEXEDITOR integration

- `GET /api/custom-crafting` returns the profile-resolved custom and vanilla
  paths, 275 read-only vanilla rows, editable custom rows, availability, and
  validation errors.
- `PUT /api/custom-crafting` validates the complete replacement document and
  atomically saves it. Invalid documents return HTTP 400 without changing the
  prior file. The older POST save path remains as compatibility only; the UI
  uses PUT.
- Profile resolution follows `LEXEDITOR_GAMEPLAY_INI` by default and supports
  explicit `LEXEDITOR_CUSTOM_CRAFTING_FILE` and
  `LEXEDITOR_VANILLA_CRAFTING_FILE` overrides.
- Crafting now has paired Vanilla and Custom modes. Vanilla is read-only and
  sourced from the shipped snapshot. Custom supports search; add/remove/reorder
  recipes; add/remove/reorder unlimited ingredients; recipe ID, name,
  description, category, context/station, unlock, output item and positive
  numeric output/ingredient quantities; catalog-ID datalists; inline duplicate,
  missing-field, unknown-item and quantity validation; global unsaved-change
  protection; and header-save participation.
- If the runtime files are absent for the active profile, Custom reports
  unavailable without breaking the rest of LEXEDITOR. Vanilla shows the
  profile's snapshot when present and otherwise reports an empty source.
- Static/API checks passed: Python compilation, inline JavaScript compilation,
  `git diff --check`, GET returning 275 vanilla rows, valid PUT round-trip, and
  invalid-item PUT returning HTTP 400.

## Remaining integration-owned steps

1. Include `modules/custom_crafting.cpp` after the common wrappers/module
   includes in `GameplayTweaks/script.cpp`.
2. Call `updateCustomCraftingMenu(now);` before other menu or
   hotkey consumers. While it returns true, suppress other custom menu input.
3. Install the ASI plus all three TSV files together and hash-verify them before
   changing #22 to `test me`.

## Remaining acceptance boundary

This slice is compile-proven but is not installed or in-game tested. Vanilla
selection currently performs a safe handoff to Rockstar's still-open crafting
page; seamless one-click vanilla execution inside the replacement UI remains
unproven and should not be implemented with raw inventory writes because that
would skip vanilla crafting animations, challenges, recipe events and station
logic. Gold and silver material records and breakdown yields are now authored;
the project's catalog had already deliberately renamed all six vanilla
platinum valuables to brass, so those live brass records break down into the
existing `LEX_BRASS` material instead of reintroducing unreachable platinum
inputs. Runtime tests must
cover portable crafting, campfire crafting, cooking/grill context, locked
recipes, full output capacity, a forced rollback, and returning cleanly from
both the replacement and handed-off vanilla UI.

## Readability and exit repair

- The in-game screenshot showed raw catalog/category keys overflowing their
  columns and obscuring adjacent text. Display-only formatting now removes
  common internal prefixes, replaces underscores with spaces, and bounds list,
  title, context, output, and ingredient strings. Stored recipe data and all
  275 vanilla rows remain untouched.
- Exit now accepts the normal and disabled variants of game-menu cancel,
  frontend cancel, frontend keymapping cancel, pause-alternate, and an explicit
  Windows Escape edge. The footer states `ESC / B exit`.
- The close path now enters the same bypass latch used for vanilla handoff
  before asking Rockstar's app to close. This prevents the still-active
  asynchronously closing app from reopening the replacement on the next frame.
- Static verification still cannot prove the exact in-game font/layout or that
  each station's owning script responds cleanly after its UI app closes. Those
  remain integration/install and in-game acceptance boundaries.
- Added `custom_crafting_item_labels.tsv`, generated from the vanilla catalog
  and localization, with 3,590 player-facing item names plus the four custom
  outputs. The HUD now shows these names instead of raw `PROVISION_*`, `LEX_*`
  and hexadecimal catalog IDs; unknown future IDs retain a readable fallback.
- Backspace and the physical XInput B button are explicit exit fallbacks, and
  descriptions are wrapped into bounded lines instead of running off-panel.
- The empty/error state now prints the exit footer too, and cancellation is
  evaluated before navigation/craft debounce. ESC, Backspace, and controller B
  therefore remain immediately available even after a failed initial TSV load
  or a just-processed menu action.
- A follow-up audit found 40 vanilla snapshot rows containing literal OpenIV
  `0x########` identifiers. The runtime had been applying JOAAT to that text,
  which yields a different item/cost/unlock hash. The module now parses exact
  literal hashes for outputs, ingredients and unlocks while retaining JOAAT for
  symbolic keys; the issue verifier asserts all three call sites.

## Remaining seamless-vanilla blocker

The live issue still requires the replacement UI to execute vanilla recipes in
one action. Rockstar's `CraftingDatastore` proves the owning script/UI app holds
real recipe contexts, and the SPACTIONPROXY native surface can only consume and
approve a *pending* crafting action. There is no exposed enqueue function. Raw
inventory writes are deliberately not substituted: they would omit the
station-owned animation, challenge/stat/event updates, special cooking behavior
and other script-side effects. `SHOOT`-style synthetic input also cannot select
an arbitrary output/cost context without a proven CraftingDatastore selection
and event-injection contract. The current safe handoff remains until that UI
action enqueue/selection path is identified and observed in-game.

The Story scripts make the missing boundary more precise: `simple_crafting`,
`interactive_campfire`, and `player_camp` consume recipe selection events from
UI event channel `-813979060`, then resolve the chosen binding context before
their normal Make prompt drives animation and transaction state. The public
`UIEVENTS` native surface contains only pending/get/peek/pop operations; it has
no event-post operation. The datastore API also exposes list count and mutation
but no supported arbitrary-list-item selection call. Consequently this module
cannot safely select a snapshot row in the live Rockstar list and enqueue the
same event from issue-local code. Blind accept input would craft whichever row
Rockstar currently selected, not necessarily the row selected in this overlay.

## Swarm re-audit

- The issue-local verifier passed all 18 menu contracts against 3,590 runtime
  item labels.
- The current profile API loaded without errors and returned 20 editable custom
  recipes plus all 275 read-only vanilla recipes.
- Catalog-aware validation passed the 20 custom rows against
  `MyOverhaul/catalog_sp.ymt` and the 275 vanilla rows against
  `datasets/vanilla/catalog_sp.ymt`. Validating custom rows against the vanilla
  catalog correctly rejected the mod-owned material/output records.
- Python bytecode compilation and issue-owned `git diff --check` passed.
- No further issue-local source change could remove the seamless-vanilla
  blocker: it needs either a proven Rockstar list-selection/event-enqueue
  contract or an integration/runtime redesign, followed by in-game evidence.

## Campfire softlock correction

The first attempted correction was wrong. Keeping the overlay alive for 750 ms,
closing `CRAFTING` directly, clearing `player_crafting_active`, and forcibly
clearing Arthur's task did not return ownership to the `simple_crafting` script;
Lexer confirmed the campfire still flashed and softlocked.

Decompiled `simple_crafting.c` identified the precise race. In state 8 the
owning script disables all controls and waits for both an active `CRAFTING` app
and `UISTATEMACHINE::_0xF7C180F57F85D0B8(CRAFTING)` before advancing to its
interactive state 10. Closing the app externally during state 8 makes that wait
impossible to satisfy, so clearing the ped's scenario/task cannot repair the
script state and can leave the player staring at the fire indefinitely.

The issue module was changed so it:

- ignores an active-but-not-ready `CRAFTING` app and requires 100 ms of stable
  ready state before displaying or taking input;
- never closes Rockstar's app, changes its crafting decorator, or clears the
  player's tasks;
- detects cancel before disabling controls, hides itself, and returns input to
  the already-interactive Rockstar script so the same cancel press/release can
  drive its own quit prompt and normal scenario cleanup;
- treats disappearance of the app as authoritative cleanup by the owning
  script and only resets its own local presentation state.

The updated issue verifier passed 23 static contracts, including the readiness
gate, cancel-before-disable ordering, and explicit rejection of direct app
close, decorator mutation, and forced task clearing. `git diff --check` passed
the issue-owned source and verifier. This correction was not compiled,
installed, or runtime-tested in this worktree; #22 therefore remained
`actionable` for integration and campfire/portable/grill acceptance.

## Live deployment conflict found during re-audit

The game-root `asiloader.log` from the reported run showed both
`GameplayTweaks.asi` and `UCMO.asi` loaded in the same process. UCMO is itself a
complete custom crafting-menu ASI and consumes overlapping menu controls. The
installed GameplayTweaks artifact had SHA-256
`F1A98C615AB3D0B4D1DB0BD4520144D789F51CF5F84C495C2E595D5452CF3B96`, timestamped
before this issue-local readiness/handoff correction, and no
`GameplayTweaks.custom-crafting.log` existed. Therefore Lexer's latest
"nothing has been fixed" report did not exercise this correction; this is a
deployment fact, not a claim that the untested correction works in-game.

The module now detects `UCMO.asi` at runtime, logs the conflict once, and
declines crafting-menu ownership. Integration must obtain Lexer's explicit
permission to disable/remove that loader file before #22 can be tested as the
replacement menu. This worktree did not move or modify UCMO.

The seamless vanilla-selection boundary was rechecked against the full SDK
native surface. `UIEVENTS` exposes only pending/get/peek/pop, SPACTIONPROXY can
only process an already-pending craft, and the ordinary `CraftingDatastore`
list exposes read/write/list operations but no supported selection/event-post
operation. `_VIRTUAL_COLLECTION_SET_INTEREST_INDEX` does not apply because
Rockstar creates `recipes` as a regular `_DATABINDING_ADD_UI_ITEM_LIST`.
Consequently no issue-local, deterministic one-action handoff can safely choose
an arbitrary vanilla recipe. The module retained the explicit Rockstar-menu
handoff instead of crafting the wrong selected row or bypassing animations,
challenges, stats, and recipe events with raw inventory mutation.

## 2026-08-10 vanilla-menu misidentification and hidden overlay

- I misidentified Lexer's screenshot of Rockstar's vanilla crafting page as
  the custom menu and falsely described the canteen as merely buried. The
  screenshot's category tabs, Rockstar recipe card, and native ingredient
  panel prove that statement was wrong. The false GitHub comment was deleted
  and #22 was returned from `test me` to `actionable`.
- The custom renderer kept Rockstar's `CRAFTING` app open to avoid the already
  observed Story-script softlock, but drew its full-screen replacement at the
  default script graphics order. The opaque vanilla scaleform renders over
  that layer. The supplied screenshot also shows unrelated script text behind
  the vanilla page, corroborating this exact layer-order failure.
- `customCraftingDraw` now selects authoritative script graphics draw order 7
  before its background and text. The vanilla app remains alive underneath for
  lifecycle ownership; the custom replacement is rendered above it.
- While the crafting app or overlay is active, a bounded two-second owner
  heartbeat now records app-active, ready, overlay-open, bypass, conflict,
  recipe count, and draw order. Opening also logs the recipe count and draw
  order. Future acceptance requires the visible `VANILLA + CUSTOM RECIPES`
  header and a matching `overlay=1 drawOrder=7 recipes=295` log; seeing only
  Rockstar category tabs is a failure, not proof of the custom UI.

## Unrequested recipe-order change reverted

I incorrectly treated Lexer's question about where the canteen recipe was as
permission to reorder the entire unified menu and make the canteen the default
selection. He did not request either behavior. The loader is restored to its
original vanilla-then-custom order. Recipe ordering/navigation remains a design
decision for Lexer; no further ordering change is authorized by that question.

## Underlying-input safety failure

The overlay's `customCraftingDisableControls` disables navigation, accept,
cancel, craft, and eat actions in groups 0-2, then reads disabled-control edges
for its own navigation. That is not proof of isolation. Decompiled
`simple_crafting.c` state 10 consumes its Make prompt through
`_UIPROMPT_IS_PRESSED` and also directly tests `INPUT_GAME_MENU_ACCEPT` while
the Rockstar app remains alive underneath. Script-thread ordering is not an
accepted guarantee that our per-frame disable happens first.

Because the installed implementation had no prompt-disable readback or
transaction readback, it could not rule out an accept press reaching both
menus. #22 was returned to `actionable`. A non-configurable safety latch now
keeps the custom overlay entirely disabled and logs that reason once; ordinary
Rockstar crafting remains untouched. Re-enabling requires a proven exact input
isolation mechanism plus runtime evidence that native selection and inventory
do not change during custom navigation/accept.

## Recurrence audit before the current repair

- **Primary evidence/reference:** the live issue body and every current user
  comment are authoritative for requested presentation and ordering. The latest
  returned-test complaint says the overlay cannot own input while Rockstar's
  live crafting script can consume the same prompt/control; it also explicitly
  rejects the earlier inference that custom recipes or the canteen should be
  moved first. `simple_crafting.c`, `interactive_campfire.c`, and
  `player_camp.c` own the actual Story crafting lifecycle and must be opened at
  the cited states before any ownership claim is made.
- **Sanctioned path:** preserve the vanilla script/app as lifecycle owner unless
  an authoritative interface proves that it can be suspended and resumed.
  Custom navigation/accept may be enabled only if the underlying prompt and
  direct-control paths are isolated with a readback or authoritative
  postcondition. Recipe order remains vanilla-then-custom until Lexer requests
  a different order; the canteen receives no implicit priority.
- **Execution proof:** an owner heartbeat must distinguish disabled, app not
  ready, overlay visible, input isolated, handoff, and conflict states. An
  overlay draw/open line does not prove isolation. A future enabled path must
  record selected custom row, the exact accepted edge, pre/post ingredient and
  output counts, and that Rockstar's selected recipe/transaction did not move
  during custom navigation or acceptance.
- **Rendered/player-visible acceptance:** seeing Rockstar category tabs alone
  is failure. When safely enabled, the custom header/list must visibly render
  above the vanilla app at portable camp, authored campfire, and grill entries;
  the displayed ordering must match the live issue rather than the rejected
  custom-first/canteen-first assumption. Cancel must return through the owning
  Story script without a flash, double action, or softlock.
- **Per-frame mutation audit:** drawing and control isolation may run only while
  the verified crafting owner is active. File reload remains bounded to two
  seconds; inventory mutation occurs only on one accepted custom-recipe edge;
  no per-frame app close, decorator write, task clear, prompt mutation, or
  inventory write is permitted.

## 2026-08-10 safe-isolation conclusion

No Story-native, issue-local input takeover with an authoritative postcondition
was found, so the custom overlay remains safe-off. This is deliberate rather
than another attempted runtime mechanism:

- `simple_crafting.c:617` creates the Make prompt on
  `INPUT_GAME_MENU_ACCEPT`. State 10 accepts that prompt at lines 706-709 and
  separately drains the CRAFTING UI event queue at lines 743-764; event
  `-1203660660` calls the same craft path at lines 756-760.
- Disabling the shared prompt record is not an atomic ownership transfer.
  `simple_crafting.c:2022-2041` owns `func_49`; its enabled branch clears flag 4
  and enables the prompt. Selection/update paths call `func_58` from the same
  state (for example line 671), so Story can re-enable Make and then consume a
  later accept event from the same queue before this ASI receives another tick.
  A prompt-enabled readback immediately after our write would therefore prove
  only that write, not isolation for the remainder of Story's tick.
- `PAD::SET_INPUT_EXCLUSIVE` is resolved as native
  `0xEDE476E5EE29EDB1` in `_downloads/RDR2_SDK/SDK/inc/natives.h:4359`, but the
  SDK supplies no ownership or readback contract. Story call sites invoke it
  inside active frame loops (`camera_photomode.c:192-195` and
  `benchmark.c:1717-1720`). That is not evidence that it can suspend another
  script's prompt and UI-event consumers, so it was not shipped as a guess.

The issue module now emits a two-second, non-mutating heartbeat while the
Rockstar CRAFTING app is active:
`safe-disabled heartbeat app=1 ready=<0|1> overlay=0 isolation=0
promptMutations=0 inventoryWrites=0`. This distinguishes a loaded but idle
module from a module that reached the live/ready crafting owner. The safe-off
branch returns before recipe reload, overlay drawing, control suppression,
prompt mutation, or inventory work. Vanilla recipe order followed by custom
recipe order remains unchanged; the reusable canteen was not promoted.

Runtime acceptance remains unmet by construction: this pass does not display
the replacement menu and does not claim #22 is implemented. Enabling it still
requires a proven way to suspend/resume Rockstar's crafting input ownership,
then in-game checks at portable camp, authored campfire, and grill proving the
visible unified list, unchanged ordering, single-action custom transactions,
and cancel without vanilla activity or softlock.

## 2026-08-10 sanctioned Story-thread isolation repair

The previous safe-off conclusion missed a resolved Rockstar-native ownership
path. `_downloads/RDR2_SDK/SDK/inc/natives.h:192-193` defines native
`0x37C1257849DEF24A` as `_PAUSE_SCRIPT_THREADS(BOOL)` and states that it pauses
all script threads except the caller. This is not an inferred prompt-order
trick: Rockstar uses balanced true/false ownership in
`camera_photomode.c:1899-1905` and `camera_item.c:2288-2294`.

The replacement now waits for the existing CRAFTING app to be ready and stable,
then calls `_PAUSE_SCRIPT_THREADS(TRUE)` before opening the overlay or accepting
any input. The calling GameplayTweaks script continues; the underlying
`simple_crafting`, `interactive_campfire`, or `player_camp` Story owner cannot
consume its Make prompt, direct accept, or recipe event while paused. The
native is invoked only on the ownership transition, not per frame.

Pausing Story alone would still permit the native UI app to queue an event that
Story could consume after resume. All three authoritative crafting owners drain
the same channel `-813979060`:

- `simple_crafting.c:743-764`
- `interactive_campfire.c:18119-18140`
- `player_camp.c:28532-28553`

While Story is paused, the replacement therefore disables its owned controls
and drains that channel with the same SDK pending/peek/pop natives. Draining is
bounded to 64 events per frame. If the queue remains non-empty, ownership is
retained and a two-second warning is emitted; Story is never resumed with a
replacement-owned event still queued.

Cancel and vanilla-row selection now arm a release-gated handoff. Story remains
paused, controls remain disabled, and the queue remains drained until every
accept/cancel keyboard, PAD, and controller source is physically released.
Only then is the event queue checked empty again, `_PAUSE_SCRIPT_THREADS(FALSE)`
called, the overlay hidden, and Rockstar's still-running app returned to its
normal owner. This deliberately may require the next intentional input in the
Rockstar page; it does not replay the overlay's accept/cancel edge. The module
still never closes CRAFTING, mutates `player_crafting_active`, or clears player
tasks.

Custom-row transactions execute only with `threadsPaused=1` and an empty
Rockstar crafting event queue. Logs now record the selected row and exact
accept edge, pre-transaction output/ingredient counts, committed post-counts,
the balanced acquire/release transitions, handoff reason, and cumulative
discarded events. The two-second owner heartbeat distinguishes app readiness,
overlay ownership, paused state, pending handoff, bypass, conflict, recipe
count, draw order, and discarded-event count.

The safe-off latch was removed because the exact isolation mechanism is now
source-resolved. Recipe ordering remains the requested vanilla 275 followed by
custom 20; no canteen or custom-first priority was introduced.

Scoped evidence passed:

- `python tools/reverse-engineering/verify_custom_crafting_issue_22.py`
  checked 47 contracts, including the SDK native/hash/comment, both Rockstar
  balanced pause/resume call sites, the event-channel consumers in all three
  crafting owners, acquire-before-open, drain-before-resume, physical-release
  handoff, transaction logs, and rejection of direct app close/decorator/task
  mutation.
- `python -m py_compile tools/reverse-engineering/verify_custom_crafting_issue_22.py`
- issue-owned `git diff --check`

No build, install, shared dispatcher/INI, manifest, GitHub state, or recipe data
was changed. Static evidence establishes an authoritative isolation design, not
player-visible acceptance. #22 must remain actionable until a combined build is
installed and portable camp, authored campfire, and grill tests prove: the
custom overlay is visible above CRAFTING; underlying vanilla inventory does not
change during custom navigation/accept; a custom transaction changes exactly
the logged counts once; vanilla handoff resumes normally; and cancel/exit does
not flash, double-act, or softlock.

## Recurrence audit before the returned vanilla-page repair

- **Returned evidence:** the latest player screenshot still shows Rockstar's
  recipe card and category tabs after the thread-pause candidate was installed.
  Therefore a balanced pause call, event drains, a draw call, or a source-level
  draw-order setting cannot be treated as proof that the replacement became the
  visible owner.
- **Required primary evidence:** re-open every pause/resume use in
  `camera_photomode.c` and `camera_item.c`, and every CRAFTING event consumer in
  `simple_crafting.c`, `interactive_campfire.c`, and `player_camp.c`. Resolve
  the native declarations from the SDK. Do not infer lifecycle ownership from
  a nearby call or from the native name alone.
- **Required safety proof:** the replacement may accept input only after the
  other Story threads are paused. Before resume it must consume only the exact
  CRAFTING event channel used by all three owners, wait for every custom
  accept/cancel source to be physically released, and prove that the queue is
  empty. No custom navigation, accept, or cancel edge may reach the hidden
  Rockstar menu or consume ingredients there.
- **Required presentation and order:** the custom full-screen layer must cover
  the opaque Rockstar page. The 275 vanilla snapshot rows remain first and the
  20 custom rows remain after them. The canteen gets no default or priority
  treatment. A headless render must show the actual layer, not a substitute
  mockup, before integration.
- **Runtime boundary:** issue-local checks may establish call order, data order,
  event isolation, and rendered layout only. #22 remains `actionable` until the
  integrated build visibly replaces the page and survives portable camp,
  authored campfire, and grill tests without hidden-menu input, double craft,
  ingredient loss, or softlock.

## Returned vanilla-page cause and repair

The current game log proves the replacement reached its owner gate; it was not
hidden by another missing include or an inactive module. At `+5558000 ms` it
logged `isolation acquired` and `overlay opened`, then logged `handoff armed
reason=cancel` at the same timestamp. It resumed Story 15 ms later. The source
checked cancel before its input debounce and before its first draw. The button
edge inherited from opening the CRAFTING app therefore removed the replacement
in its acquisition frame, leaving the still-running Rockstar page on screen.

The repair adds an explicit opening-input state. After Story is paused and the
CRAFTING queue is drained, the custom layer is drawn, but navigation, accept,
and cancel remain disabled until every menu-owned PAD, keyboard, and controller
source is physically released. That physical-state sample also clears stale
Windows key edges. The module then logs `input armed ... threadsPaused=1
queueEmpty=1`, waits another 100 ms, and only then permits custom input. The
layer now draws before every handoff/cancel check, so even an intentional exit
cannot reveal Rockstar's page for an intermediate frame.

The isolation re-audit kept the evidence-backed owner contract unchanged:
`_PAUSE_SCRIPT_THREADS` is the SDK-resolved balanced native used by
`camera_photomode.c:1899-1905` and `camera_item.c:2288-2294`. The exact channel
`-813979060` and pending/peek/pop sequence remain present in all three crafting
owners at `simple_crafting.c:743-764`, `interactive_campfire.c:18119-18140`,
and `player_camp.c:28532-28553`. The replacement pauses before touching that
queue and drains it before any resume. Custom transactions remain inside paused
ownership after an empty-queue result.

The recipe files still load in their authored order: 275 vanilla rows, then 20
custom rows. Opening selection remains row 1, the first vanilla row. The
Reusable Canteen remains the first custom row at position 276 and was not
promoted.

`render_custom_crafting_issue_22.py` rendered the actual source/data-bound
custom layer at 2560x1440. The inspected output
`worklog/issues/github-22-custom-layer.png` was fully opaque, showed the
`VANILLA + CUSTOM RECIPES` header, displayed the original vanilla first row and
1/295 position, covered the full frame, and contained no Rockstar category-tab
page. This headless render checks the authored layer only; it does not prove
RDR2 composited it.

No shared dispatcher, INI, build, install, manifest, GitHub comment, label, or
state changed. #22 remains `actionable` until the integrated artifact passes
the portable camp, authored campfire, and grill player-visible and input-safety
checks.
