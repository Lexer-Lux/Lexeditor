# GitHub #62 — Honor Action Editor

## Audit

- Story Mode routes shared honor changes through a hard-coded 19-value tier
  function: `-640, -480, -320, -160, -40, -20, -10, -5, -2, -1, 0, 1, 2,
  5, 10, 20, 40, 160, 640`. Individual scripts select a tier per call site;
  event names do not own a single editable amount.
- The common honor function checks `Global_36616` against 21 exact event bits.
  Those are legitimate independent disable controls.
- `short_update.c` treats `REL_BOUNTY_HUNTER` as hostile, but its animal branch
  classifies every dog type as a farm animal. Bounty responses spawn the
  `PoliceDog` dispatch preset, whose model is `A_C_DogHound_01`, so an attacking
  bounty dog reaches `HONOR_EVENT_KILL_FARM_ANIMAL` unless its ped is explicitly
  honor-blocked. This is the human/dog inconsistency.

## Built in this slice

- Added a strict editor model containing the 21 event toggles and 19 shared
  magnitude tiers. Unknown IDs, duplicates, and event-specific amount edits are
  rejected rather than silently accepted.
- Added a static round-trip verifier.
- Added profile-resolved `GET /api/honor-actions` and strict
  `POST /api/honor-actions/save` routes plus an alphabetical Honor Actions
  Crime & Law subtab. The UI presents event enables separately from shared
  tier amounts and participates in global dirty/save handling.
- Added the unregistered runtime module. It hot-reloads the canonical CSV,
  applies only the 21 audited bits to `Global_36616` while preserving every
  unowned bit, and remaps observed exact vanilla honor deltas through the 19
  shared tiers. Disabled tiers restore the pre-change honor value.

## Remaining integration/runtime work

- Include `modules/honor_actions.cpp` after common wrappers and call
  `updateHonorActions(now)` every frame.
- Install `honor_actions.csv` beside the ASI after it has been authored/saved by
  LEXEDITOR.
- Bounty-dog mutation remains deliberately unimplemented. `PoliceDog` proves
  the dispatch preset/model, but the extracted data does not prove a runtime
  relationship/decorator unique to bounty bloodhounds. Model-only matching
  would also exempt ordinary `A_C_DogHound_01` pets. Add the farm-animal
  `honor_block` bit only after a bounty-specific runtime identity is observed.
- Delta remapping must be tested for same-frame aggregation, honor-cap clipping,
  and Chapter 6's eligible 1.5 multiplier. Exact event toggles do not share
  those observational limitations.

## Runtime checks

1. Kill an attacking human bounty hunter: no honor loss.
2. Kill an attacking bounty bloodhound: no farm-animal honor loss.
3. Kill a non-hostile town/farm dog: the configured farm-animal rule still
   applies.
4. Disable one standard event in the editor and verify only that event class is
   suppressed; restore it and verify the vanilla change returns.
5. Change one shared tier and test two actions known to select that same tier,
   including a Chapter 6 save if tier scaling is implemented.

## 2026-08-10 returned editor correction

The returned test was accurate: the visible honor-action rows only offered
enable/disable controls. Replacement amounts did exist, but their table was
buried below all 21 event rows, so the page presented as a toggle-only editor.

LEXEDITOR now puts the 19 editable honor amounts first, beside the 21
independent event toggles on wide screens. The heading, inline explanation,
input title, and accessibility label all say that each field replaces one
vanilla amount for every action that uses it. This preserves the proven engine
boundary: `Global_36616` provides independent event blocking, while Story
scripts choose shared magnitude tiers; the UI does not invent event-specific
amounts the runtime cannot enforce.

The #62 verifier now requires the editable amount table to precede the event
toggle table and verifies both tables remain present. No build, install,
runtime claim, or GitHub label change was made in this issue-local pass.

## `fuckups.txt` recurrence audit after the failed editor test

- The live API was inspected and does expose all 19 amount tiers and 21 event
  toggles, so this is not evidence that the amount data is absent.
- The failure is player-visible presentation. Static ordering assertions did
  not establish that the browser actually loaded the changed page or that the
  amount controls were visible and understandable at Lexer's viewport size.
- The existing Honor API/CSV is the sanctioned data path; no independent
  per-event amount model may be invented because the engine supplies shared
  tiers.
- Acceptance requires a rendered wide and narrow view in which `Editable honor
  amounts` is visible before the event toggles, every amount has an editable
  control, and no stale/undefined content appears. Source/API checks alone are
  not completion evidence.

## 2026-08-10 amount-first rendered acceptance

- The amount and event tables now form one vertical `honor-stack`; the complete
  19-row `Editable honor amounts` card is the first control surface at every
  viewport width, and the 21 independent event toggles follow it. This removes
  the prior 430px minimum grid track that overflowed narrow screens.
- The narrow card uses fixed semantic columns with full-width number inputs.
  Missing event/tier presentation values are normalized before DOM creation,
  so stale data cannot render literal `undefined`.
- `python tools/reverse-engineering/verify_honor_actions_issue_62.py` passed.
  `python tools/reverse-engineering/render_crime_editors_55_62.py` exercised the
  real server/page in headless Chrome and read back: first card `Editable honor
  amounts`, 19 number inputs; second card `Independent event toggles`, 21
  checkboxes; strict vertical order; no literal `undefined`.
- Rendered evidence:
  `worklog/issues/rendered/github-62-honor-wide.png` and
  `worklog/issues/rendered/github-62-honor-narrow.png`. Both visibly show the
  editable replacement amounts before any event toggles, and the narrow render
  keeps the full signed numbers inside their controls.
- This was editor-only presentation work. It changes no runtime honor cadence
  and adds no per-frame mutation. No build, install, or GitHub label change was
  performed.

## Recurrence audit — amount editor absent in the rendered page

- **Primary visual evidence:** the latest 2282x1184 screenshot was inspected. It
  begins with `Independent event toggles` and renders all 21 toggle rows across
  a mostly empty two-column table; there is no `Editable honor amounts` card
  above it. This directly disproves the prior rendered-acceptance claim for the
  page Lexer actually received.
- **Sanctioned path:** retain the proven shared 19-tier amount model and 21 event
  bits. Normalize legacy/current API payloads at the page boundary so the amount
  editor cannot disappear merely because a running backend uses an older key or
  omits presentation metadata. Do not invent per-event amounts.
- **Execution proof:** render from the same server/page route used by LEXEDITOR,
  assert the first card is the amount editor with 19 editable number controls,
  then the event card with 21 toggles. Include a legacy-payload fixture matching
  the failure, not only a current direct-module response.
- **Rendered acceptance:** wide and narrow captures visibly show the full amount
  editor first, no giant empty toggle-only surface before it, readable signed
  values, no `undefined`, and no page overflow.
- **Per-frame mutation:** editor normalization/layout only; honor gameplay
  cadence and runtime tier/event application are unchanged.

## 2026-08-10 corrected scroll-retention diagnosis and rendered acceptance

- The current API and renderer already contained the amount card. The actual
  failure was retained document scroll: switching from a long Crime subtab to
  Honor Actions preserved the previous deep scroll position, placing the
  viewport directly on `Independent event toggles`. The earlier headless test
  hid this by calling `window.scrollTo(0,0)` after direct rendering, so its
  acceptance claim did not reproduce the real navigation path. No legacy
  amount-key rewrite was needed.
- Crime subtab switching now awaits the target render and resets the document
  scroll after layout. The verifier reproduces the failure by scrolling the
  long Crime page to its bottom and then invoking the same Honor subtab switch;
  it no longer performs a verifier-only scroll reset.
- The Honor stack is capped at 980 px on wide screens, so the event checkbox is
  not stranded at the far edge of a 2282 px surface. It remains fluid at narrow
  widths.
- Fresh real-page readback found `Editable honor amounts` first with 19 number
  controls, `Independent event toggles` second with 21 checkboxes, `scrollY=0`,
  a 980 px wide stack in a 1440 px viewport, and a 370 px stack in a 390 px
  viewport with no overflow. Rendered evidence is retained at
  `worklog/issues/rendered/github-62-honor-wide.png` and
  `worklog/issues/rendered/github-62-honor-narrow.png`.
- This pass changed editor navigation/layout only. It did not build, install,
  change GitHub state, or alter honor runtime cadence.

## Recurrence audit — verify the actual running LEXEDITOR session

- Read `fuckups.txt` again. Lexer's latest report rejects the fresh-server
  fixture as proof of what he sees. The running server on port 8765 was started
  before the latest Python metadata changes; its bounty payload confirms that
  version skew, although its Honor endpoint currently returns 21 events and
  19 tiers.
- The next check must load the real page from that running server and use the
  real Honor subtab navigation. A new verifier-only server cannot establish
  that the current session displays the amount controls.
- Keep the existing shared-tier model. The engine does not provide independent
  per-event honor amounts, so no event-specific amount fields may be invented.
- Acceptance requires DOM and rendered evidence from the running server:
  `Editable honor amounts` first, 19 visible number inputs, then 21 event
  checkboxes, with scroll at the amount card. If the live page fails, record
  the exact API/DOM mismatch and repair that path.

## Actual running-server verification

- Loaded `http://127.0.0.1:8765/#crime` in a separate headless browser against
  the already-running LEXEDITOR backend. This did not start a replacement test
  server and did not reuse the earlier fresh-server acceptance shortcut.
- Real DOM readback after the real Honor subtab transition reported
  `Editable honor amounts` first with 19 number inputs, `Independent event
  toggles` second with 21 checkboxes, `scrollY=0`, width 980 in a 1440 viewport,
  and width 370 with no overflow in a 390 viewport.
- Fresh wide and narrow screenshots were written through the existing render
  harness. The current checked-in page therefore contains and displays the
  amount editor against the live backend. The existing user browser tab still
  requires a page reload to replace its already-loaded older JavaScript/DOM.
