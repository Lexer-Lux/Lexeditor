# RDR1 standalone-worklog consolidation

Source repository: `Lexer-Lux/Lexers-Mod-For-RDR`
Source commit: `0a26c8a4fd530178fe998b660b7fcb2218109d08`
Consolidated: 2026-09-06

This is a sanitized historical consolidation of the useful implementation notes that were still living in the standalone RDR1 mod repository after that repository was declared storage-only. The source issue numbers below belong to the standalone repository and are **not** Lexeditor issue numbers. Live Lexeditor issues/comments and the current central per-issue handoffs remain the canonical task state.

No GitHub issue bodies/comments, API snapshots, screenshots, attachment caches, or private download paths were copied here. Absolute local paths from the old worklogs were intentionally omitted.

## Source issue 1 — RDR1 managed plugin and RPF6 preparation

- Established the RDR1 managed-plugin path separately from RDR2, using read-only RPF6 extraction rather than the RPF8 reader.
- Prepared vanilla data outside Git and confined editable overrides to the RDR1 project tree; installed RPFs were hash-checked before/after preparation and left unchanged.
- Added the RDR managed Lexeditor plugin, RPF6 bridge, editable-file listing/save route, and later WTD export with CRN payload preservation.
- Static/API/plugin smoke checks passed; native WebView2/game acceptance remained separate.

## Source issue 2 — RedHook runtime, development mode, and packaging

- Selected the RDR-specific RedHook SDK ABI rather than copying RDR2 hooks/natives.
- Added compile-time release/development gating, keyboard edge handling, runtime heartbeat logging, development-mode plumbing, dispatcher registration, and release/development builds.
- Added prerequisite checking/installation for the supported RedHook runtime and verified packaged/installed hashes where installation was possible.
- Runtime load, heartbeat, development toggle, and unload behavior required game-side acceptance.

## Source issue 3 — weapon radial time scale and vertical centering

- Resolved the RDR radial-open signal and RedHook time-scale extensions from RDR scripts/headers.
- Initial immediate getter postcondition was shown to be invalid; the implementation moved to bounded deferred readback and preserved/restored the previous scale.
- Resolved HUD movie values used for centering and added guarded read/write/readback/restore handling.
- Later runtime evidence showed a radial crash recurrence; crash root cause still required a real crash-context diagnosis rather than speculative native replacement.

## Source issue 4 — persistent horse blip and RDR2-style horse icon

- Resolved the vanilla horse-blip lifecycle and added a transition-owned persistent player-horse blip that does not overwrite mission/vanilla-owned blips.
- Identified the RDR2 `blip_horse_owned` art candidate and inspected RDR `sharedflash.wtd`/CRN payloads.
- The exact RDR WSF-symbol-to-WTD texture mapping and a safe whole-WTD writer remained unresolved, so no guessed texture replacement was shipped.

## Source issue 5 — shop mouse-wheel quantity

- Resolved the active shop predicate and proved the exposed shop quantity setter owns remaining stock, not pending buy/sell quantity.
- Pending quantity is private UI-event state and no sanctioned wheel-only preemption + pending-quantity setter was found.
- Kept only a bounded fail-closed shop observer; no raw-input hook, global accept remap, or unsafe shop mutation was added.

## Source issue 6 — development camera

- Implemented a development-only F4 camera using the vanilla/RedHook camera layout/channel lifecycle.
- Added configurable movement/rotation/boost, frame-step clamping, heartbeat state, and cleanup in the correct channel-remove → camera-destroy → layout-destroy order.
- Avoided persistent actor freeze/player-control writes; rendered motion and camera restoration still required in-game acceptance.

## Source issue 7 — RDR1 Lexeditor data tabs

- Extended RDR1 preparation to inventory data and added structured Items editing with full-document preservation of unsupported XML content.
- Added Settings editing against the single project INI with comment/unknown-key/line-ending preservation.
- Defined an ASI-owned loot override schema for the proven corpse-loot fields rather than pretending a vanilla loot-table XML existed.
- API/smoke/readback checks passed while installed archives remained unchanged; WebView2 layout and runtime consumption remained acceptance boundaries.

## Source issue 8 — automatic carriage rest

- Resolved the vanilla passenger-coach rest state machine and its private use-context handle.
- RedHook exposes no sanctioned way to press that existing private context or request the exact owner transition safely.
- Kept a bounded fail-closed observer only; no synthetic input, context mutation, or player-control manipulation was added.

## Source issue 9 — startup-logo skipping

- Resolved the official RedHook `SkipIntroLogos` setting as the correct path instead of replacing installed Bink movies.
- Lexeditor/installer logic preserves unrelated INI content and enables the setting while leaving both movie files hash-identical.
- A cold launch remained the player-visible proof that the logos are skipped and normal loading still works.

## Source issue 10 — persistent money/ammunition HUD

- Resolved the money global and RDR ammo natives, then added a right-aligned RedHook text HUD with bounded diagnostics.
- Runtime evidence corrected the money address to element 0 (`54087`) and exposed RedHook draw-text pointer-lifetime requirements; the implementation switched to plugin-lifetime text storage and stricter HUD/player visibility gates.
- Correct values, stable glyphs, and placement still required live rendering acceptance.

## Source issue 11 — Shops tab

- Resolved real `ShopInventory` data in Gringo WGD resources rather than misusing inventory XML as store stock.
- Added WGD unpack/repack support, enumerated the real shop entries, and exposed price modifier, quantity per purchase, and total available quantity with source provenance.
- Save changes only the resolved bytes into a project override and validates packed readback; installed `gringores.rpf` remains unchanged.

## Source issue 12 — shoulder swap while in cover

- Resolved `allowCameraSideSwitch` in the installed cover camera program and created an archive-relative project override changing only the cover-camera boolean from false to true.
- Verified a one-line diff and unchanged installed camera archive; no raw keyboard hook or per-frame camera-offset hack was used.
- In-game cover/aim/exit behavior remained the acceptance boundary.

## Source issue 13 — V-toggle first person

- Inspected the supplied first-person camera-data reference against installed vanilla camera files and documented the exact arc changes.
- The reference is a permanent tuning replacement, not a reversible runtime toggle; no sanctioned on-foot first-person selector or complete safe custom-camera ownership path was resolved.
- No guessed toggle or permanent camera replacement was shipped; the issue remained actionable research/engineering work.

## Source issue 14 — mission reward editor

- Resolved the 57 Story mission identity map and mission-specific cash/fame/honor reward table from the RDR scripts.
- Added a schema-versioned project override and runtime consumer that applies only configured fields on the resolved one-shot completed-deed transition with duplicate suppression/readback.
- Generated table/build/install checks passed; real mission-completion reward behavior still required in-game acceptance.

## Source issue 15 — cutscene/campsite key remaps

- Resolved the campsite Travel-to prompt owner and the cutscene stop APIs.
- Proved that globally remapping `@UI.ACCEPT`, synthetic Return input, prompt-text-only changes, or unconditional cutscene stop would violate ownership/safety requirements.
- No unsafe remap was shipped; a supported camp-local action replacement and cutscene skippability/input-owner path remained unresolved.

## Source issue 16 — reported performance regression

- Identified synchronous per-log-line open/write/`FlushFileBuffers`/close behavior as a real avoidable script-thread stall path and retained a persistent-handle logging improvement.
- A temporary per-stage performance probe was removed after Lexer confirmed RDR1 was running normally before that diagnostic build was installed.
- Therefore the reported recovery was **not** attributed to the logging change and the original slowdown root cause remains unproved.

## Consolidation result

The standalone RDR1 repository no longer needs its own `worklog/` tree. Future implementation notes belong in Lexeditor's central `worklog/`; durable RDR1 mechanics/format knowledge belongs in `codex/rdr/`. The standalone repository's `AGENTS.md` directs agents back to Lexeditor and forbids recreating local Worklog/Codex/project-memory stores.
