# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5201525844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/6

Created: 2026-08-20T08:50:21Z; updated: 2026-09-04T12:24:29Z

Exact metadata: [source record](sources/issue-5201525844-60e552bd661c2181c5452675167e3417d6c057aa3c0a8ff1ea8806576844a84a.json).

## Request

Add a **Quick-select slots** field to the RDR2 Item Details panel. It edits the selected item's assignments in `quickselectitems.ymt`.

The file permits zero, one, or several assignments per item, so the interface must not pretend this is always one value.

## Interface

- Show every current assignment as its own row.
- Use a proper dropdown containing only slot IDs proved by the active `quickselectitems.ymt` group. Never use a free-entry slot field or browser datalist.
- Let the user add another assignment and remove an assignment.
- Do not permit duplicate slots for one item.
- Preserve the assignment's existing sort order when its slot changes.
- Give a new assignment the next sort order after the entries already in that target slot. Do not require a raw sort-order input.
- Use the existing file structure to select the item group: preserve an existing entry's group; new `WEAPON_*` entries use the proved weapon group and other catalog items use the proved satchel-item group.

## Saving

- The normal Lexeditor Save action writes `MyOverhaul/quickselectitems.ymt` in the same transaction as other Item edits.
- Preserve unrelated entries and optional fields such as texture overrides byte-for-byte in XML meaning.
- Undo, redo, dirty-state protection, and Exit prompts must include these edits.
- Show `quickselectitems.ymt` in the Items file context and mark the file integrated in the RDR2 Data Map.

## Acceptance

- An existing one-slot item displays its real slot.
- An existing multi-slot item displays every slot without data loss.
- An unmapped item can receive a valid slot through the controlled selector.
- A mapping can be removed.
- Save and reload reproduce the edited assignments and preserve unrelated quick-select entries.
- No quick-select slot can be free-typed.


## issue 5201525844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/6

Created: 2026-08-20T08:50:21Z; updated: 2026-09-06T12:44:52Z

Exact metadata: [source record](sources/issue-5201525844-cafb2bf7ee3768b0202dd5503364b2f8b6a2c91287b418fa2722a732108d77a3.json).

Items now supports multiple quick-select assignments with valid slot dropdowns, add/remove, undo and saving. Editor checks passed; your check remains.

- [ ] Restart Lexeditor and use a test RDR2 mod. Open an item's Quick-select slots, add a permitted slot, then remove it; duplicate slots must be refused.
- [ ] Save an assignment change and reopen the item. Confirm every assignment is retained and other items are unchanged; report the item and failed step.

## comment 5353768959 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/6#issuecomment-5353768959

Created: 2026-08-20T09:05:12Z; updated: 2026-08-20T09:05:12Z

Exact metadata: [source record](sources/comment-5353768959-3431db0b49534395c13d8b5ca49d45d8dee39022b38ccaac53439e015d413ccc.json).

Implemented.

`quickselectitems.ymt` does not map every catalog item. It contains only quick-select-eligible items plus a few special action records, and an item can have several slot assignments. Item Details now reflects that real structure:

- **Quick-select slots** shows every current assignment.
- Every assignment is a real dropdown limited to slot IDs already used by that file's matching item group.
- **+ Slot** opens the controlled searchable picker. There is no free-entry slot field or datalist.
- Removing the final row makes the item unmapped.
- Existing sort order is preserved. New assignments get the next order automatically, so there is no raw sort-order field either.
- Normal Save, Undo, Redo, dirty-state protection, and unsaved-exit prompts include the change.
- `quickselectitems.ymt` now appears as Integrated in the Data Map.

The temporary-file writer test and hidden rendered RDR2/Warband suite pass. The render proved one-slot, three-slot, unmapped, add, remove, and unknown-slot rejection cases. The render also hash-verified that the live `quickselectitems.ymt` stayed unchanged.

