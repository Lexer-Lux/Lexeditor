# Final Fantasy VII Rebirth third-party credits

Lexeditor's Rebirth plugin bundles the pinned Shader Injector release and was built against the following references. The injector's MIT license is quoted in full below.

## Attributions

- **David Matos (frostbone25) / Shader Injector** — The D3D12 shader-replacement mod Lexeditor bundles for Rebirth, pinned to the 2.2.1 Maximum quality release. <https://github.com/frostbone25/ShaderInjector>
- **Microsoft / DirectX Shader Compiler** — dxc, dxcompiler and dxil, shipped inside the Shader Injector release to recompile its shaders. <https://github.com/microsoft/DirectXShaderCompiler>
- **Yoraiz0r / FF7RebirthDataObjectEditor** — MIT-licensed Rebirth editor used as a public behavior cross-check for editing extracted DataObject .uasset files in original IoStore state. No code is vendored. <https://github.com/Yoraiz0r/FF7RebirthDataObjectEditor>
- **Synthlight / FF7R2-DataObject-Parser** — CC BY-NC 4.0 Rebirth format documentation used to independently verify IoStore-state DataObject layout and public table/row/property names across PlayerParameter and the unresolved Rebirth gameplay areas. Lexeditor does not vendor or adapt this implementation. <https://github.com/Synthlight/FF7R2-DataObject-Parser>
- **trumank / retoc** — MIT-licensed IoStore CLI reviewed as the pinned DirectoryIndex extraction route. It is not automatically invoked because its Oodle dependency may be acquired when absent. <https://github.com/trumank/retoc>
- **matyamod / UnrealReZen (ff7r branch)** — GPL-3.0 FF7R2 packaging reference used to verify UE4.26, End/Content mounting and the Rebirth dependency-manifest workaround. Lexeditor can invoke only a separately supplied local executable through its candidate-only packaging route; no UnrealReZen code or binary is bundled. <https://github.com/matyamod/UnrealReZen>
- **nikolaybutnik / FFVII-Rebirth-Mesh-Patcher** — MIT-licensed public Rebirth tooling used to cross-check that native IoStore mod triples are discovered under End/Content/Paks/~mods. No code is vendored or adapted. <https://github.com/nikolaybutnik/FFVII-Rebirth-Mesh-Patcher>
- **f80h / FF7 Rebirth Load ordering** — August 2026 public UE4.26/Rebirth load-order analysis used to implement read-only native package precedence reporting. No article text, mod assets or code are bundled. <https://www.nexusmods.com/finalfantasy7rebirth/articles/46>
- **Gantz79 / 100 Percent Steal and Drop Rate** — Public Rebirth behavior evidence for #471: a packaged rate edit works and the author reports the 25% rate data is shared between steals and enemy drops. Used for semantic boundary research only; no mod assets are copied or redistributed. <https://www.nexusmods.com/finalfantasy7rebirth/mods/157>
- **TheWolfster / Refreshed Chocobo Rest Stops (Static Mesh)** — Public Rebirth evidence for #472 that Chocobo rest-stop meshes can be replaced and that the blue bench is a separate asset among multiple bench models. Used for research only; no mod assets are copied or redistributed. <https://www.nexusmods.com/finalfantasy7rebirth/mods/2048>
- **DaniRBT / FF7 Rebirth Accessibility - Visibility Overhaul** — Public Rebirth evidence for #473 separating pak-based minimap position/size changes from the optional UE4SS HUD mover. Used to avoid conflating HUD layout with world-minimap zoom; no mod assets are copied or redistributed. <https://www.nexusmods.com/finalfantasy7rebirth/mods/2357>
- **narknon / FF7R2UProj** — Public generated Rebirth type declarations used only as reverse-engineering/schema evidence for #470/#471/#472/#473/#477: Chocobo ride-legality/location seams; the concrete BattleItemPossession TArray<FName>/TArray<uint8>/int32 schema; bench mesh/cushion actor members; navimap scale option categories; and Queen's Blood field/pass/turn types. No root repository license file was found in the audited snapshot, so no source is copied, adapted, vendored or redistributed. <https://github.com/narknon/FF7R2UProj>

## License notices

### Shader Injector — MIT License

MIT License

Copyright (c) 2026 David Matos

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
