# Final Fantasy IX third-party sources

Lexeditor's FF9 plugin uses the following external projects as runtime or format references.
No proprietary game data is included here.

## Memoria

- Project: https://github.com/Albeoris/Memoria
- Pinned helper/data release: `v2025.07.04`
- Pinned source revision used for format/runtime verification: `d8df6e69ddb618adc753a27d9424409d66216a35`
- License: MIT (`LICENSE` in the Memoria repository).
- Use: FF9 runtime/helper, CSV schemas and serialization behavior, battle-scene field semantics, BGI field-walkmesh layout/runtime floor-active semantics, launcher update-setting behavior.
- Battle-attack and scene-flag layouts additionally verified against these pinned-revision files: `Assembly-CSharp/Global/BTL_SCENE.cs` (`a6e9e21e`), `AA_DATA.cs` (`e8a081ec`), `BTL_REF.cs` (`ef2a164b`), `BattleCommandInfo.cs` (`53f7a989`), `BitUtil.cs` (`88928800`), `BTL_SCENE_INFO.cs` (`9bf6ccb2`), `SB2/SB2_HEAD.cs` (`b8af40db`), `Memoria/Data/Battle/TargetType.cs` (`9128a3c0`), `TargetDisplay.cs` (`673b80b2`), `StatusSetId.cs` (`c4409fa6`). No Memoria source file is vendored; Lexeditor's reader is a clean-room struct codec citing those offsets.
- Lexeditor verifies the official `Memoria.Patcher.exe` SHA-256 published by that release before execution.

## UnityPy

- Project: https://github.com/K0lb3/UnityPy
- License: MIT.
- Use: permissively licensed interoperability reference for Unity serialized-file and UnityRaw/container structure.
- No UnityPy source file or binary is vendored or invoked by this plugin.

## Hades Workshop

- Project: https://github.com/Tirlititi/Hades-Workshop
- Reference revision audited: `7bd24784cbb5099f678a78275af366104efb386d`
- License: GNU GPL v3 (`LICENSE` in the Hades Workshop repository).
- Use: additional FF9-specific reverse-engineering provenance for Steam Unity archive structure.
- `Source/Enemies.h` was audited for enemy-attack category/type semantics at the reference revision; its abstracted spell model does not map onto the Steam `AA_DATA` battle record, so no Hades-derived attack semantics were adopted.
- No Hades Workshop source file or binary is vendored or invoked by Lexeditor.

## Dream World IX / ff9mapkit

- Project: https://github.com/GameJawnsInc/Dream-World-IX
- Reference revision audited: `8c7a5b48e9041110dad9e06b69d47c0eecc7b010`
- License: MIT for toolkit source code; FF9-derived game bytes are explicitly excluded from that grant.
- Use: public interoperability evidence for FF9 field-scene bundles and loose BGI override paths, compiled event scripts, p0data4 model prefabs, p0data5 animation clips, world-map authoring and other Memoria loose-override paths.
- No Dream World IX source, binary, generated game asset, or FF9-derived byte is bundled or invoked by Lexeditor.

## Theme provenance

- Colours are CSS values sampled locally from the game's own window atlases
  ("Gray Atlas", the default window colour, and "Blue Atlas") in the installed
  `x64/FF9_Data/sharedassets2.assets`: stone fill `#575a59`, bevel `#707878` /
  `#383840`, outline `#202830`, slot `#383c3c`, cursor bar `#cccccc` at about
  60% alpha, and the blue window bevel `#4060b0` as the accent. The atlases
  were read once for research; no texture is bundled or extracted at runtime,
  and the stone grain is approximated with CSS gradients.
- Fonts are copied at serve time from the player's installed Memoria bundle
  `FF9_Data/EmbeddedAsset/FA/p_fa.mpc` into the private game-data cache
  (`plugins/ff9/game_font.py`). The bundle is decrypted with Memoria's
  block swap (`Assembly-CSharp/Global/Byte/ByteEncryption.cs`, MIT): the last
  1024 bytes move to the front and the first 1024 are dropped, leaving an
  uncompressed UnityRaw bundle whose embedded TrueType fonts are located by
  their table directories. No Memoria source is vendored.
  - "Alexandria" by Teaito (2019, FontStruct Non-Commercial License,
    https://fontstruct.com/fontstructions/show/1666931/alexandria-2), a
    recreation of the PlayStation FF9 lettering, is the body and tab face.
  - "Garnet", the heavier pixel face bundled beside it, is the heading face.
  - The bundle's "TBUDGothic Std B" (Morisawa, commercial) is not used.
- Tetra Master card faces are cut at serve time from the player's installed
  `x64/FF9_Data/sharedassets2.assets` into the private game-data cache
  (`plugins/ff9/card_art.py`): the ARGB32 texture `quadmist_image1` is cropped
  to the rectangles the NGUI atlas drawn with "QuadMist Image Atlas 1" gives
  for `card_00`..`card_99`. The Texture2D field order follows the UnityPy
  reader (MIT); the sprite record follows NGUI's `UISpriteData`. Nothing is
  vendored, and no card image is bundled.
- No FF9 font, image, or audio asset is bundled, downloaded, or redistributed.
  Without an install the editor falls back to system fonts. Game-derived
  interface sounds are never shipped: they require local extraction from an
  installed copy when redistribution is not permitted.

