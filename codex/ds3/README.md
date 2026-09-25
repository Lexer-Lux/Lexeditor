# Dark Souls III

## Supported parameter path

Lexeditor targets the Steam PC release at App Ver. 1.15.2 / Regulation Ver.
1.35. The editable source is \`Game/Data0.bdt\`. Six PARAM members are currently
integrated: EquipParamWeapon, EquipParamProtector, EquipParamAccessory, Magic,
SpEffectParam, and NpcParam.

The parser validates PARAM type, the header value each table stores, and row
size against pinned Smithbox metadata. A mismatch fails closed.

## Regulation file layout

`Game/Data0.bdt` is a 16-byte IV followed by AES-256-CBC ciphertext under the
key `ds3#jn/8_7(rsY9pg55GFN7VFL#+3n/)`. The ciphertext holds a DCX container of
type `DCX_DFLT_10000_44_9` — one zlib block whose header starts at 0x4C — and
that block inflates to one BND4 archive. Measured on App Ver. 1.15.2 /
Regulation 1.35 on 2026-09-25: IV `00` × 16, block type `DFLT`, level 9,
compressed length 815,334, and a 13,445,834-byte BND4 with 103 members whose
header carries the text `01350000` at offset 0x18. The container compresses the
BND4, so the DCX block length must be read from the header; the writer's
trailing padding is not part of it.

SoulsFormats writes the same DCX type for DarkSouls3 and pads the ciphertext
with PKCS#7, while the installed build pads with zero bytes. Lexeditor reads
both and writes the installed shape, so an export has the layout the game
ships.

The value at PARAM offset 0x08 is not the pinned paramdef version. Every pinned
DS3 XML declares version 201, and the installed regulation stores a different
value per table: EquipParamWeapon 3, EquipParamProtector 4, EquipParamAccessory
1, Magic 3, SpEffectParam 4, NpcParam 9. Those measured values are the version
check, because they identify the row layout this editor patches.

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
