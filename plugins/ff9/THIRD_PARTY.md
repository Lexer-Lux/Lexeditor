# Final Fantasy IX third-party sources

Lexeditor's FF9 plugin uses the following external projects as runtime or format references.
No proprietary game data is included here.

## Memoria

- Project: https://github.com/Albeoris/Memoria
- Pinned helper/data release: `v2025.07.04`
- Pinned source revision used for format/runtime verification: `d8df6e69ddb618adc753a27d9424409d66216a35`
- License: MIT (`LICENSE` in the Memoria repository).
- Use: FF9 runtime/helper, CSV schemas and serialization behavior, battle-scene field semantics, BGI field-walkmesh layout/runtime floor-active semantics, launcher update-setting behavior.
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
- No Hades Workshop source file or binary is vendored or invoked by Lexeditor.

## Dream World IX / ff9mapkit

- Project: https://github.com/GameJawnsInc/Dream-World-IX
- Reference revision audited: `8c7a5b48e9041110dad9e06b69d47c0eecc7b010`
- License: MIT for toolkit source code; FF9-derived game bytes are explicitly excluded from that grant.
- Use: public interoperability evidence for FF9 field-scene bundles and loose BGI override paths, compiled event scripts, p0data4 model prefabs, p0data5 animation clips, world-map authoring and other Memoria loose-override paths.
- No Dream World IX source, binary, generated game asset, or FF9-derived byte is bundled or invoked by Lexeditor.

