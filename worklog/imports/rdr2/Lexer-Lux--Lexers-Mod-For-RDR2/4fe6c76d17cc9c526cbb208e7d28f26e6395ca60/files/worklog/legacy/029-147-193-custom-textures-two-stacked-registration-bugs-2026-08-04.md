# Worklog: 029 147 193 Custom Textures Two Stacked Registration Bugs 2026 08 04

## #147 + #193 — custom textures: TWO stacked registration bugs, 2026-08-04

Build `25458C426E74BA9604DA8EB502E4E5152E25EA6E0FB0B8158F19CC741D566EC6`.
Full restart required (data + streamed textures + ASI).

The art was never the problem. Verified the six custom blip PNGs against the 321
vanilla ones: same 32x32, same greyscale range, same 0-255 alpha, comparable
opaque pixel counts. Identical DXT5 path for both. Two separate registration
bugs were stacked on top of each other.

BUG 1 — wrong texture dictionary named per blip.
`blipdata.ymt` gives every blip its own `<TextureDictionary>`. Counts in our
file: `blips` 343, `blips_mp` 320, `blips_tu` 1. Our six LEX entries pointed at
`blips` — Rockstar's RESIDENT dictionary, which of course does not contain our
textures. The blip record resolved, its texture did not, and the map drew an
empty square. The earlier "fix" attempted to override the resident `blips`
dictionary wholesale, which also displaced ordinary icons; that is why it ended
up disabled and the categories were repointed to unrelated vanilla sprites.
The correct pattern is what vanilla already demonstrates: `blips_mp` (320) and
`blips_tu` (1) prove several dictionaries resolve side by side. Built
`lex_blips.ytd` containing only the six custom textures and repointed the six
entries to `<TextureDictionary>lex_blips</TextureDictionary>`.
Backup of the previous blipdata at `MyOverhaul/blipdata.ymt.pre-lexblips`.

BUG 2 — the stream folder was never loaded. THIS ALSO EXPLAINS #193.
LML streams from the TOP-LEVEL `lml\stream` folder, not from a `stream`
subfolder inside a mod. Evidence: `lml\stream` already contained
`PDOR_ICONS.ytd` from the third-party PDO Reloaded mod (whose icons work) and a
stale `LEX_MAP_ICONS.ytd`; `MyOverhaul\stream` was the only per-mod stream
folder in the whole install and nothing in it had ever loaded. `install.xml`
declares no stream resource either.
So `LEX_INVENTORY_ITEMS.ytd` — which correctly contains `LEX_ICON_EMPTY_BOTTLE`,
the six `LEX_CASING_*` and the material icons, and which the catalog correctly
references as dict `LEX_INVENTORY_ITEMS` — was never in memory. That is why the
Empty Bottle and the casings have no icon at all, and it is the leading
candidate for their missing acquisition feed too.
Both dictionaries are now installed to `lml\stream` and the stale
`LEX_MAP_ICONS.ytd` removed.

RELEASE PACKAGING NOTE: shipping into the shared `lml\stream` folder is fine
locally but is not self-contained for a public release. Before release, confirm
whether LML supports declaring a stream resource in `install.xml`; if not, the
installer must place these two files in `lml\stream` itself.

Precedent worth remembering: the catalog already references `INVENTORY_ITEMS_TU`
and `INVENTORY_ITEMS_MP` alongside `INVENTORY_ITEMS`, so extra inventory texture
dictionaries are a supported vanilla pattern, exactly like `blips_mp`.

