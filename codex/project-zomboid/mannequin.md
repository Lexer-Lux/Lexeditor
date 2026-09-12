# Build 42 `mannequin` boundary

The current `pz-scripts-data` schema defines module-level `mannequin` records with six simple scalar properties suitable for conservative editing:

- `animSet` — non-empty string;
- `animState` — non-empty string;
- `female` — boolean;
- `outfit` — string and explicitly allowed to be empty;
- `pose` — non-empty string;
- `texture` — non-empty string.

`model` is a model-block reference rather than a simple scalar editor surface. Lexeditor therefore exposes the current model reference read-only and preserves it verbatim while editing the six scalar properties above.

The writer only replaces properties already present. Missing or duplicated edited properties, stale files, invalid booleans, empty values where the schema does not allow them, and script punctuation fail closed. Comments, quoted strings, and mannequin-shaped data nested inside another block do not create independent module-level records.

Schema reference: `PZ-Wiki-Modding/pz-scripts-data`, `data/blocks/mannequin.yaml`, Build 42.20.4 dataset used by this plugin.
