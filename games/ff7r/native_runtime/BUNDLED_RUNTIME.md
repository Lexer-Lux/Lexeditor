# Bundled FF7R native runtime

`LexeditorFF7RRuntime.dll.zlib.b85` is an offline bundle of the Windows x64
`LexeditorFF7RRuntime.dll` built by this repository's **FF7R native loader scaffold**
workflow.

The text payload is `Base85(zlib(DLL bytes))`. Lexeditor decodes it only when a
project does not provide an explicit `runtime/LexeditorFF7RRuntime.dll` developer
override, and verifies the decoded bytes before deployment.

Bundle provenance:

- source/head commit: `a62be77588e71dd5f4e62ad7be4c59aeecf6c6a9`
- source PR: `#449` (`Load FF7R native runtime config and scan known signatures`)
- workflow run: `34193142668`
- workflow artifact: `LexeditorFF7RNativeRuntime` / artifact id `10042917860`
- workflow artifact ZIP SHA-256: `14b2fe0a37f61dcb82833328b0dd88018b0946768d413c26efc5e20dadd60b8c`
- decoded `LexeditorFF7RRuntime.dll` size: `91136` bytes
- decoded DLL SHA-256: `ed9c7f252e517473d181e29e3d4b2fcc4856f8beb4794b6a5779df696977a071`

The DLL exports the NativeMods `Init()` entry point and passed the repository's
Windows `/W4 /WX` native build and export checks before bundling.

A bundled DLL is **not** hook-validation evidence. Runtime deployment still
requires a hook-validation manifest for the installed executable build. A
manifest may additionally pin `runtimeDllSha256`; when present, Lexeditor refuses
to deploy a different DLL even if the executable timestamp and hook flags match.

When native runtime source changes, update this bundle from a green Windows
artifact and update the pinned digest/provenance together. Do not hand-edit the
Base85 payload.
