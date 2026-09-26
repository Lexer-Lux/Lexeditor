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
