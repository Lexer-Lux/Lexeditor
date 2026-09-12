# FF7 kernel surface follow-up

This follow-up audits the original Final Fantasy VII editor after PR #423's semantic UI pass and records the source-backed KERNEL.BIN fields completed by PR #434.

## Completed scope

- **Section 1 — CommandData:** 8-byte command records expose initial cursor/menu action, target flags, single-target camera ID, and multi-target camera ID. The two unknown bytes remain preserved and unexposed.
- **Section 2 — AttackData:** 28-byte player attack/magic records expose accuracy, impact/target reaction, MP cost, cameras, targeting, attack effect, damage formula/power, status behavior, additional effects, elements, and inverted special-attack flags. Names/descriptions come from the existing Magic name/description text sections.
- **Character Limit attack references:** Limit 1-1/1-2/2-1/2-2/3-1/3-2/4 attack IDs resolve against Player attacks with the normal searchable reference and click-through behavior.
- **Items:** documented restrictions and inverted special-attack flags are now exposed alongside the previously supported battle-effect fields.
- **Weapons:** documented restrictions, equipment stat bonuses, materia-slot layouts, hit/critical/miss sound selectors, impact effect and high sound-ID mask are exposed; unknown bytes remain untouched.
- **Armor:** documented restrictions, equipment stat bonuses and materia-slot layouts are exposed; unknown bytes remain untouched.
- **Accessories:** documented restrictions are exposed alongside the existing stat, element, status and special-effect controls.

The generic binary-preservation regression edits every exposed core KERNEL field and verifies no other decoded byte changes. A separate pinned layout contract hard-codes the Elena d85e026 offsets, record sizes and text-section associations for Commands, Player attacks, Items, Weapons, Armor and Accessories so a mistaken `CATEGORIES` offset cannot validate itself.

## Safety contract

This work keeps the existing FF7 rules: project-only writes, exact source/active snapshot checks, binary reread verification, preservation of every unedited/unknown byte, explicit unknown/modded enum values, and no claim of installed-game acceptance from synthetic fixtures.

## Format references

- Shojy/Elena `KernelSection.cs`, `CommandData.cs`, `AttackData.cs`, `ItemData.cs`, `WeaponData.cs`, `ArmorData.cs`, and `AccessoryData.cs` at revision `d85e02678670763c663cd058463f7578b957912e`, already cited by `codex/ff7-data.md`.
- petfriendamy/ff7-scarlet command initial-cursor action mapping and KERNEL writer behavior at the revision already cited by `codex/ff7-data.md`.
