# FF7 kernel surface follow-up

This follow-up audits the original Final Fantasy VII editor after PR #423's semantic UI pass. It tracks source-backed KERNEL.BIN fields that are documented by the same public format references already used by Lexeditor but are not yet exposed as first-class editor controls.

## Confirmed gaps

- **Section 1 — CommandData:** 8-byte command records. Documented fields are initial cursor/menu action, target flags, single-target camera ID, and multi-target camera ID. The two unknown bytes remain preserved and unexposed.
- **Section 2 — AttackData:** 28-byte player attack/magic records. Documented fields cover accuracy, impact/target reaction, MP cost, cameras, targeting, attack effect, damage formula/power, status behavior, additional effects, elements, and inverted special-attack flags. Names/descriptions come from the existing Magic name/description text sections.
- **Character Limit attack references:** the existing raw Limit attack IDs can resolve against Section 2 once AttackData is integrated.
- **Core item/equipment records:** the current editor still omits some documented Item/Weapon/Armor/Accessory fields such as restrictions, equipment stat bonuses, materia-slot layouts, and selected effect/sound IDs. These should be exposed only where the public layout is authoritative; unknown/unused bytes stay untouched.

## Safety contract

This work must keep the existing FF7 rules: project-only writes, exact source/active snapshot checks, binary reread verification, preservation of every unedited/unknown byte, explicit unknown/modded enum values, and no claim of installed-game acceptance from synthetic fixtures.

## Format references

- Shojy/Elena `KernelSection.cs`, `CommandData.cs`, `AttackData.cs`, `ItemData.cs`, `WeaponData.cs`, `ArmorData.cs`, and `AccessoryData.cs` at the revision already cited by `codex/ff7-data.md`.
- petfriendamy/ff7-scarlet command initial-cursor action mapping and KERNEL writer behavior at the revision already cited by `codex/ff7-data.md`.
