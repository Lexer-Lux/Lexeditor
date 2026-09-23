# Skills system: alternative interface and progression proposal

Issue: [#225](https://github.com/Lexer-Lux/Lexeditor/issues/225).

This proposal is ready for review. It is not installed. No menu, save
format, or progression record is changed. The hardcoded vanilla pause
menu cannot accept arbitrary new pages through data alone, so this
design does not add one.

## Constraints from evidence

- Data-only pages are blocked: the vanilla menu structure is hardcoded,
  so no catalog, meta, or text edit creates a working skills page.
- The existing Lexeditor pages (Items, Challenges, Crime, Settings) edit
  supported data records; a skills system needs live counters and a live
  surface, which no current page provides.
- Vanilla challenge and progression records must not be repurposed: skill
  ranks must never corrupt challenge progress, Dead Eye XP, or core
  maximums.

## Proposed interface

A key-bound standalone runtime panel, not a pause-menu page:

1. The panel opens on its own input binding while on foot in free roam.
   It never inserts a link into the vanilla pause menu or the nine-link
   challenge menu.
2. It shows one screen: named skills, current rank per skill, progress
   toward the next rank, and the effect each rank grants. All wording
   comes from the mod's own text resources, not vanilla labels.
3. It stays closed during missions, cutscenes, loading, and wanted
   pursuit until each state is proven safe. Fail closed: an unknown game
   state means no panel, never a forced open.
4. An editor-side planning page in Lexeditor (rank tables, thresholds,
   effect mapping) is the design-approval artifact and ships first; the
   in-game panel follows only after approval.

Rejected: a data-only pause-menu page (blocked by the hardcoded menu),
and a journal-appended page (same data-only block, unproven).

## Proposed progression

- Named skills with event-counted experience (for example: hunts,
  crafts, clean kills by range band). Counters accrue only from observed
  game events, never from time passing.
- Fixed rank thresholds per skill, stored in one versioned table with a
  supported-build fingerprint. Unknown builds refuse to load it.
- Rank effects map only onto already-supported scalar paths (core drain
  rates, accuracy and damage scalars the AI/Mobs editors already write).
  No effect writes vanilla progression or challenge records.
- Counters persist per Story profile in the mod's own store, separate
  from engine saves. A changed profile, mission replay, or Online
  session suspends accrual rather than mixing data.
- The whole system ships disabled behind one master switch until the
  design is approved and the panel passes review.

## What still needs proof

- A supported runtime surface for the key-bound panel on the installed
  build (input binding, draw path, safe open/close states).
- An event-observation path for each proposed XP source that cannot
  double-count or fire during missions.
- A persisted-counter store with profile binding and corruption
  recovery.
- Lexer design approval of the skill list, thresholds, and effects.

## Decision needed from Lexer

Approve, amend, or reject the interface (key-bound panel plus
editor planning page) and the progression model (event counters,
fixed thresholds, scalar-only effects) before any prototype is built.
