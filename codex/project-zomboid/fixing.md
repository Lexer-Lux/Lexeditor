# Build 42 `fixing` boundary

The current `pz-scripts-data` schema defines repair records with several compound properties and one independently typed primitive suitable for conservative editing:

- `ConditionModifier` — finite float.

`Require` is an item array, `GlobalItem` is an item-to-integer object, and `Fixer` may be repeated and carries its own repair-material/skill grammar. Lexeditor therefore leaves those structures read-only and preserves them verbatim while editing an existing top-level `ConditionModifier`.

The writer never inserts a missing modifier or resolves duplicates by guesswork. Missing or duplicated `ConditionModifier` properties, stale files, non-finite or malformed numeric values, and script punctuation fail closed. Comments, quoted strings, and fixing-shaped data nested inside another block do not create independent module-level records.

Schema reference: `PZ-Wiki-Modding/pz-scripts-data`, `data/blocks/fixing.yaml`, Build 42.20.4 dataset used by this plugin.
