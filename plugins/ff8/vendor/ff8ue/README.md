# FF8 Ultimate Editor source

The LZS decoder retains its existing attribution in `plugins/ff8/credits.md`.
The model files below are from HobbitDur/FF8UltimateEditor, revision
`97772fffe4c8a8df6e483a68804497958c6bc095`, under GPL-3.0 (`LICENSE`).

| Local file | Upstream path |
| --- | --- |
| monsterdata.py | FF8GameData/monsterdata.py |
| interpolation.py | FF8GameData/dat/interpolation.py |
| rotation3d.py | FF8GameData/dat/rotation3d.py |
| glbbuilder.py | FF8GameData/gltf/glbbuilder.py |
| gltfexporter.py | Ifrit/Ifrit3D/gltfexporter.py |

Local adaptations: package-relative imports; the exporter's Qt PNG conversion
accepts PNG bytes already decoded by Lexeditor, preserving the TIM alpha rules.
The animation bit reader rejects truncated streams instead of zero-filling them.
Parsing limits and application transport belong in `plugins/ff8/model_geometry.py`.
No game files are distributed with this source.

The cinematic decoder and simulator in `magcine/` are from revision
`57de22415858d625af6fd3d03d21d4d58365bb14` of the same GPL-3.0 project:
`FF8GameData/magcine/cinescript.py`, `FF8GameData/magcine/cinesim.py`, and
`FF8GameData/Resources/json/gf_cinematic_opcodes.json`.
The sole adaptation is resolving the opcode JSON beside the decoder.
Lexeditor's execution limits live in `plugins/ff8/effect_timeline.py`.
The simulator documents its approximations in its module docstring; it does
not reproduce battle-dependent behavior exactly.
