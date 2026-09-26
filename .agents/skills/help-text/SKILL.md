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

Keep it short. If a bubble needs more than three sentences, it is doing the job
of documentation, not help. A bubble that scrolls is a bug.

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

## Examples from this codebase

**Bad** (FF7, `characterFlags`, starting battle mood):
> Initial battle mood. FF7 stores this as one enum byte: None, Sadness, or Fury.

It repeats the label, lists the choices the select already shows, and explains
storage instead of effect.

**Good:**
> The mood this character has when a battle starts. Fury fills the Limit gauge
> faster but lowers accuracy. Sadness fills it slower but reduces damage taken.

**Bad** (FF7, `statusChange`):
> Inflict/cure/swap mode and chance encoded in one byte.

**Good:**
> Whether this attack adds, removes or toggles the chosen status, and the
> chance that it works.

**Bad:** a bubble on a field labelled "Item name" that says "The item's name."
**Good:** no bubble.
