---
name: help-text
description: Writing Lexeditor's question-mark help bubbles, Data Map descriptions and setting notices. Use before adding, changing or reviewing any help text, and when deciding whether a field needs a bubble at all.
---

# Help text

The reader is a player, not a programmer. A bubble tells them what the value is
and what to set it to, in short plain sentences.

## When a field gets a bubble

- **No bubble** when the label and the control already say everything. "Name",
  "Price" or "Enabled" with a checkbox needs nothing. A bubble that repeats its
  label is noise, and noise teaches the reader to skip every bubble.
- **A bubble** when the reader cannot guess the gameplay effect, the unit, a
  limit, or a trap (for example, "0 disables the drop").
- Tabs and sections get a bubble only when their purpose is not obvious from
  the name.

## One property, one text

The help belongs to the property's definition in code, not to the screen that
draws it. Every screen that shows the property uses the same text. Two
different bubbles for one value is a bug.

## What to write

1. What it is, in game terms: what the player sees change.
2. How to set it, if that is not obvious: unit, range, what the extremes do.
3. Known limits or traps, if any.

Leave out file offsets, byte layouts, encodings and parser behaviour unless
they change what the reader should do. The choices in a select do not need
repeating in the bubble; explain what they *do* instead.

Keep it short. A field bubble is three sentences at most. A tab or section
bubble may run to about six short ones when it explains how the screen is laid
out. Past that it is documentation, not help. A bubble that scrolls is a bug.

## Style: Simplified Technical English

Adapted from [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)
(MIT), which applies ASD-STE100 rule categories to agent-written text. Help
text uses its "STE-flavoured" mode: the structural rules in full, plain words
as a direction of travel, not a dictionary check.

- Active voice: "The enemy drops this item", not "This item is dropped".
- Simple tenses. "Has" or "had" forms only when they carry meaning.
- One idea per sentence. No semicolons. Split instead.
- About 20 words per sentence at most.
- No phrasal verbs: "start", not "kick off"; "remove", not "take off".
- Verbs, not nouns made from them: "Sets the drop chance", not "Provides
  configuration of the drop chance".
- Noun stacks of three words at most.
- One name for one thing across the whole editor. Do not rotate "slot",
  "entry" and "record" for the same row.
- No marketing words (seamless, powerful, robust).
- **Keep the hedge.** If the effect is only suspected, say "may" or "probably".
  Never upgrade a guess to a fact to make the sentence shorter, and never add a
  cause or effect nobody has shown. An unknown field says it is unknown.

## Common failure modes

Each example is real help text from this codebase. Check a new bubble against
every one of them.

### 1. Storage instead of effect

FF7, starting battle mood:
> **Bad:** Initial battle mood. FF7 stores this as one enum byte: None, Sadness,
> or Fury.

> **Good:** The mood this character has when a battle starts. Fury fills the
> Limit gauge faster but lowers accuracy. Sadness fills it slower but reduces
> damage taken.

It repeated the label, listed the choices the select already shows, and
described the byte. The reader needs to know what each choice does.

### 2. Encoding jargon

FF7, status change:
> **Bad:** Inflict/cure/swap mode and chance encoded in one byte.

> **Good:** Whether this attack adds, removes or toggles the chosen status, and
> the chance that it works.

### 3. Raw units instead of player units

FF7, starting Limit gauge:
> **Bad:** Raw 0–255 Limit gauge fill used at initialization.

> **Good:** How full the Limit gauge is when a new game starts. 255 is full.

"Raw" and "initialization" are the parser talking. Say what the numbers mean
on screen.

### 4. A magic number the control already hides

FF7, starting materia slot:
> **Bad:** Materia stored in this initial stock slot; 255 means empty.

> **Good:** no bubble.

The picker already offers **None** for 255, so the reader never sees the
number. Explain a special value only where the reader types it.

### 5. A special value the reader does type

RDR, shop stock:
> **Bad:** -1 is reserved for records that use unlimited stock

> **Good:** How many of this item the shop has. -1 means unlimited.

This is the best reason a bubble exists: a value that behaves differently from
the rest. State it plainly, in the reader's terms.

### 6. A wall of text in internal names

RDR2, Shops tab:
> **Bad:** The selected shop is in the middle. BUYS controls the global
> SELL_SHOP_DEFAULT payout plus explicit per-merchant Accept or Reject
> overrides. An item absent from sparse buyer PDATA remains engine-default
> unknown, not proven rejected. SELLS controls this shop's stock membership,
> listing-specific availability groups, and global COST_SHOP_DEFAULT price. […]

> **Good:** Pick a shop in the list to see it in the middle. Buys sets what
> this shop buys from you. Each item has one sale price for every shop. You can
> make one shop accept or refuse an item. With no rule, the game decides, and
> we do not know yet whether it buys that item. Sells sets what the shop
> stocks, when, and at what price.

Game-file names (`SELL_SHOP_DEFAULT`, `PDATA`) mean nothing to a player. Note
that the rewrite **keeps the hedge**: the original said "not proven rejected",
so the good version still says "we do not know yet". Shorter must never turn a
guess into a fact.

### 7. A bubble that repeats its label

> **Bad:** "Item name": The item's name.

> **Good:** no bubble.
