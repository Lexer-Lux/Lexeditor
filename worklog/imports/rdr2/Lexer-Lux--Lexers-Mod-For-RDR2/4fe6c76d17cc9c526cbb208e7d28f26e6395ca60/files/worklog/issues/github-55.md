# GitHub #55 — Bounty Hunters editor

## Implemented

- Added a Crime & Law / Bounty hunters subtab backed by Rockstar's dedicated
  `LAW_BOUNTY_HUNTERS_CSI` response graph.
- Editable, source-owned controls cover minimum bounty, response weight and
  spawn distances; the named global cooldown tables; per-phase fixed/random
  shotgun, sniper and police-dog counts; dog chance; and group weights.
- The exact inherited weapon loadouts, combat profiles and mounted chasing
  profiles are displayed read-only. Those `WILDERNESS`, `SHOTGUN` and `SNIPER`
  dispatch specs are shared with ordinary law response, so presenting them as
  bounty-only editable settings would silently retune unrelated lawmen.
- Staged the current update-layer vanilla `bountyhunters.meta`, including
  Rockstar's `NoFollowUpIncidentIfLeftRegion` flag, and registered its exact
  update-layer game path in `install.xml`.

## Evidence and boundaries

- `bountyhunters.meta` owns the five escalation phases, group sizes, random
  group weights and dog chances. `dispatch.meta` owns
  `BountyHuntersGlobalCooldown`, dispatch-preset-to-combat-spec bindings,
  loadout selection and mounted chase profiles.
- The editor rejects unknown setting IDs, nonnumeric/negative values, chances
  outside 0..1, and group minima greater than maxima.
- `python tools/reverse-engineering/verify_bounty_hunters_issue_55.py` passes
  the source schema and a three-file-field temporary round trip. Static XML/API
  validation also passed. Runtime field units, whether an
  already-running response hot-loads, and encounter behavior still require an
  in-game test after integration build/install.

## 2026-08-10 returned editor usability repair

The returned screenshots showed that the dedicated subtab bypassed
LEXEDITOR's normal value presentation: it rendered bare number inputs, never
loaded the vanilla dataset for comparison badges, exposed internal phase and
preset names, omitted each phase's editable `GroupMultiplier`, and offered no
field-level help. The backend's `Wanted 4+` label was not an invented tier:
the exact `dispatch.meta` rows are commented `WANTED_CLEAN`, `WANTED_LEVEL1`,
`WANTED_LEVEL2`, `WANTED_LEVEL3`, and `WANTED_LEVEL4+`.

The editor now uses the standard `refField` presentation with exact update-layer
vanilla `V` values, human-readable event/phase/responder labels, and `?` explanations for
all encounter-trigger fields, cooldown events and tiers, fixed/random pools,
chance, relative weight, and the raw group multiplier. The help stays explicit
where the data does not prove an engine formula: `MaxLocationOverrideRadius`
and `GroupMultiplier` are named and scoped, but their exact calculations are
not claimed. The empty tier-1 phase is now visible as reusing available
hunters instead of silently disappearing from the five-phase table.

The existing writable IDs and XML round trip are unchanged. Static verifier
coverage now requires the help metadata, vanilla comparison path, wanted-tier
explanation, and phase multiplier presentation. No browser was opened and no
runtime acceptance is claimed.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.

## `fuckups.txt` recurrence audit after the failed editor test

- **Visual evidence first:** the latest 297x809 and 341x1110 screenshots were
  inspected. They show literal `undefined` labels and a narrow layout consisting
  almost entirely of empty labelled rows; prior API/schema checks did not prove
  that the screen was usable.
- **Execution/version proof:** the live `/api/bounty-hunters` response omitted
  every newly-added `label`, `help`, and vanilla-reference property, while a
  direct invocation of the current `editor/bounty_hunters.py` returned those
  properties. The live page and backend were therefore version-skewed. This is
  not an unexplained CSS defect and must not be reported as repaired from source
  inspection alone.
- **Sanctioned path:** the page must use LEXEDITOR's existing `refField` value
  presentation and responsive table/setting-row rules. No new parallel value UI
  should be invented.
- **Acceptance boundary:** a rendered wide and narrow viewport must contain no
  `undefined`, expose every value with its human label and `?` help, show vanilla
  comparison values, and keep the escalation table readable. API and syntax
  checks remain necessary but are insufficient.

## 2026-08-10 version-skew repair and rendered acceptance

- Root cause was the observed live process skew, not the XML parser: the
  already-running server retained an older imported bounty module while its
  static route served the current `editor.html` from disk. The page therefore
  consumed records with missing presentation keys and passed JavaScript
  `undefined` directly to DOM text nodes.
- `ensure_bounty_hunter_metadata()` now versions and backfills the response
  schema, and `server.py` applies it explicitly at the HTTP boundary. JSON and
  HTML responses are no-store, and `LEXEDITOR_PORT` permits a clean parallel
  verifier server instead of reusing the stale live process.
- The page now normalizes an older payload before rendering. Known Rockstar
  fields recover their human labels/help; all remaining display paths use an
  explicit fallback, so an absent property cannot become literal
  `undefined`. The current response still supplies every exact update-layer
  vanilla value, shown beside the input through the existing `refField` path.
- `python tools/reverse-engineering/verify_bounty_hunters_issue_55.py` passed,
  including a reconstructed legacy payload with all label/help fields removed.
  `python tools/reverse-engineering/render_crime_editors_55_62.py` then launched
  the real server and current `editor.html` in headless Chrome. DOM readback
  found 25 help controls, 86 visible vanilla references, the expected human
  labels, no literal `undefined`, and no page-level horizontal overflow.
- Rendered evidence:
  `worklog/issues/rendered/github-55-bounty-wide.png`,
  `worklog/issues/rendered/github-55-bounty-narrow.png`, and
  `worklog/issues/rendered/github-55-bounty-narrow-right.png`. The two narrow
  captures prove both sides of the sanctioned horizontally scrollable tuning
  tables; the encounter-trigger controls stack at full width.
- This was editor/API work only. It adds no gameplay loop and no per-frame
  mutation. No build, install, or GitHub label change was performed.

## Recurrence audit — unexplained Clean and wanted tiers

- **Primary visual evidence:** the latest 2377x397 screenshot was inspected. It
  shows an `Encounter spacing` table repeating `After bounty acquired` beside
  tiers `Clean`, `Wanted 1`, etc., but gives no visible explanation of how a
  clean wanted state can coexist with bounty debt or what selects a tier. The
  complaint is about meaning, not missing metadata or table overflow.
- **Sanctioned path:** use the existing Bounty Hunters renderer and authoritative
  dispatch/bounty metadata. Explain that the tier is current wanted-level state,
  not a bounty-dollar band; `Clean` means no active wanted level and does not
  mean the regional bounty balance is zero. Explain cooldown event and min/max
  as a randomized real-time delay only to the extent supported by the data;
  do not invent an engine formula.
- **Execution proof:** the current API must carry the explanations, but the real
  wide/narrow page must also visibly place them beside/above the table. A `?`
  property hidden from the screenshot is not sufficient.
- **Rendered acceptance:** the page itself answers why `Clean` can appear after
  bounty acquisition, says whether tiers are bounty amounts or wanted level,
  and keeps every cooldown value readable at wide and narrow widths without
  `undefined` or clipping.
- **Per-frame mutation:** editor help/presentation only; no dispatch-data write,
  gameplay poll, or frame mutation.

## 2026-08-10 visible wanted-tier explanation and rendered acceptance

- A visible explanation now precedes `Encounter spacing`: the wanted tier is
  Arthur's current wanted/search state, not a bounty-dollar range. `Clean`
  means no active wanted/search level and does not imply that the regional
  bounty balance is zero. Min/max remain the stored randomized delay bounds in
  in-game hours; no unsupported scheduling formula is claimed.
- The same distinction is present in the tier help metadata, but acceptance no
  longer depends on opening a help control.
- `render_crime_editors_55_62.py` exercised the real page at wide and narrow
  widths. It found the visible explanation, 25 help controls, 86 vanilla
  references, no literal `undefined`, and no page-level horizontal overflow.
- Fresh rendered evidence is retained at
  `worklog/issues/rendered/github-55-bounty-wide.png`,
  `worklog/issues/rendered/github-55-bounty-narrow.png`, and
  `worklog/issues/rendered/github-55-bounty-narrow-right.png`.
- This pass changed editor presentation only. It did not build, install, change
  GitHub state, or add any gameplay mutation.

## Recurrence audit — each wanted tier still lacked its own explanation

- Read `fuckups.txt` again before changing the editor. The latest narrow
  screenshot shows that the table-level explanation does not answer the
  question at the row where Lexer must choose values.
- Primary evidence is
  `_downloads/extract/update_1_common/common/data/dispatch.meta`:
  `SinglePlayerWantedLevelThresholds` defines Clean=0, level 1=1,
  level 2=5000, level 3=15000, level 4=25000, and level 5=100000. The same
  file names the five cooldown rows `WANTED_CLEAN` through
  `WANTED_LEVEL4+`.
- The sanctioned repair is presentation-only: put one existing `?` help
  control beside every visible tier name and state its exact internal wanted
  score range. Do not describe those scores as bounty dollars.
- Acceptance requires the live API and a rendered table to expose distinct
  help for Clean, Wanted 1, Wanted 2, Wanted 3, and Wanted 4+, including that
  the last row also covers Rockstar level 5. A shared header tooltip is not
  sufficient.

## Per-tier help repair and live-page render

- Added distinct `levelHelp` metadata to every cooldown row. The visible tier
  cell now has its own `?` control, including the special `Wanted 3+` row.
- The help uses the exact single-player thresholds from Rockstar's data:
  Clean 0; Wanted 1 is 1–4,999; Wanted 2 is 5,000–14,999; Wanted 3 is
  15,000–24,999; Wanted 4+ begins at 25,000 and includes level 5 at 100,000.
  It explicitly says that these are internal wanted scores, not bounty dollars.
- The browser normalizer carries the same help, so an older running backend
  cannot remove the `?` controls. The issue verifier and real live-server
  wide/narrow render passed with 16 tier help controls and no overflow.
- The running backend still omits current vanilla-reference metadata because
  its Python imports predate that repair. The checked-in server/API is correct;
  a backend restart is required for those `V` references. No gameplay state or
  dispatch values changed.
