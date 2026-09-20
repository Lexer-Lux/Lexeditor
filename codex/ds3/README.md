# Dark Souls III

## Supported parameter path

Lexeditor targets the Steam PC release at App Ver. 1.15.2 / Regulation Ver.
1.35. The editable source is \`Game/Data0.bdt\`. Six PARAM members are currently
integrated: EquipParamWeapon, EquipParamProtector, EquipParamAccessory, Magic,
SpEffectParam, and NpcParam.

The parser validates PARAM type, data version 201, and row size against pinned
Smithbox metadata. A mismatch fails closed.

## Preservation and export

DS3 regulation data is handled as a BND4 payload encrypted with the established
DS3 AES-256-CBC regulation contract. Lexeditor patches only audited fixed-width
PARAM cell bytes in uncompressed target BND4 members. Unknown cells, row data,
other PARAMs, and other archive members are retained byte-for-byte. A compressed
target member is rejected rather than reconstructed.

Save writes an encrypted \`Data0.bdt\` only to the selected Lexeditor project
using an atomic replace. The installed game archive is never written.

## Sources

- Smithbox \`43f9b49a022260b6a76b1adcbe20cc0989ccff95\` — MIT; pinned DS3
  parameter metadata and interoperability behavior.
- SoulsTemplates \`f1d114a3668e3c97a1ace82411158df6b3bc50a4\` — Apache-2.0;
  BND4/PARAM format reference.
- SoulsFormats — GPL-3.0; independent behavior cross-check only, no code bundled.

Maps, 3D editing, text/events, other PARAM tables, managed loader activation,
and real-game acceptance remain outside the demonstrated integration.
