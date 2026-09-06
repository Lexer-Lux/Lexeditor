# FF7 dataset boundaries

Both `ff7` and `ff7-2013` use `games.ff7.server` and `games/ff7/editor.html`.
Keep FF7-specific fixes here rather than editing FF8 or the shared runtime.

## Character records

`datasets.Kernel` extends the existing lossless container. Source layouts are
from MIT-licensed Shojy/Elena, pinned at
`d85e02678670763c663cd058463f7578b957912e`:

- https://github.com/Shojy/Elena/blob/d85e02678670763c663cd058463f7578b957912e/Shojy.FF7.Elena/Sections/CharacterData.cs
- https://github.com/Shojy/Elena/blob/d85e02678670763c663cd058463f7578b957912e/Shojy.FF7.Elena/KernelSection.cs

Section numbers in this document are one-based. Section 4 starts with nine
132-byte initial-character slots; section 3 starts with nine 56-byte growth
slots. Inline names occupy initial-record offsets 0x10..0x1B. The UI row ID is
the slot index, not the stored character ID. Slots 6/7 also represent Young
Cloud/Sephiroth in the relevant context.

Only 21 initial numeric fields and five kill/use limit-learning thresholds
are writable. Threshold offsets in each growth slot are 0x18, 0x1A, 0x1C,
0x20 and 0x24 (little-endian u16). Unexposed equipment, flags, materia,
initial inventory, curves, AI, other sections and trailer are preserved.
These are initial values, not a save editor. Recruitment scripts may override
starting values; storage bounds are not game-balance or semantic validation.
Characters is deliberately marked **partial** in Data Map.

## Availability and saves

The five older kernel categories and Characters are loaded independently.
Bad category text/records produce a blocked card, not invented replacement
rows. A corrupt container/project blocks its kernel datasets but not Tweaks,
Info or Data Map. Never silently fall back from a corrupt project to vanilla.

Saves require exactly the currently readable categories. New page clients
supply active/source SHA-256 snapshots; older installed smoke clients without
these keys remain compatible. Validate before writing, verify temporary binary
readback, back up an existing project, and replace only the project file.
The installed source cannot be selected as the write target. Compression may
change; preservation assertions concern decoded bytes, file types and trailer.

Enemies, encounter composition/placement and shops still have no connected
writers. Their cards describe the missing source work separately. KERNEL.BIN
names/help remain read-only; this is not a kernel2.bin text editor.

## FFNx

Use `load_config(..., game="FF7")` for reads. Reject FF8-only keys on the FF7
save endpoint, and filter the shared writer's response too. Do not change the
shared parser just to implement this plugin's game filter.

Refresh absent configurations while Tweaks is visible and on focus/navigation.
A response started before an edit must not overwrite that edit. Explicit
reload asks before discarding changed settings. Refresh the cached Data Map
configuration row when availability changes. Runtime settings are installed
configuration edits; kernel saves remain project-copy edits.
