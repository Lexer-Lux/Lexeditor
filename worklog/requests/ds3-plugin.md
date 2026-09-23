# Dark Souls III plugin handoff

Branch: \`codex/ds3-plugin\`  
PR: #493

## Current evidence

- Six DS3 PARAM schemas and every enum they reference are pinned from the
  audited Smithbox revision.
- Source regressions prove AES regulation roundtrip, real row identity,
  bitfield preservation, enum rejection, edit/export/reopen, and exact
  preservation outside the edited storage.
- The local service writes only project \`Data0.bdt\`; installed source is read-only.
- Shared Table+Detail UI covers Weapons, Armor, Rings, Spells, Effects, Enemies,
  plus Info and Data Map.

## Remaining acceptance

Rendered browser CI and screenshots must pass on the live head. An isolated
candidate must then be delivered with reproducible steps. Only a real DS3
offline run can establish in-game acceptance; until that happens, managed mod
loading remains false and the PR stays draft.
