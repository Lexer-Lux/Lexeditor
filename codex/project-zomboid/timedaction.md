# Build 42 `timedAction` boundary

The current `pz-scripts-data` schema independently types one useful module-level timed-action property that can be edited without interpreting reference or array grammar:

- `actionAnim` — non-empty string.

Other timed-action fields remain read-only. `completionSound`, `prop1`, and `prop2` are block references; `muscleStrainParts` is an array; `soundTime` is explicitly marked useless by the current schema; and several remaining fields are not typed strongly enough to justify a writer. Lexeditor preserves all of them verbatim while editing an existing top-level `actionAnim`.

The writer never inserts a missing animation or resolves duplicates by guesswork. Missing or duplicated `actionAnim` properties, stale files, empty values, and script punctuation fail closed. Comments, quoted strings, and timedAction-shaped data nested inside another block do not create independent module-level records.

Schema reference: `PZ-Wiki-Modding/pz-scripts-data`, `data/blocks/timedAction.yaml`, Build 42.20.4 dataset used by this plugin.
