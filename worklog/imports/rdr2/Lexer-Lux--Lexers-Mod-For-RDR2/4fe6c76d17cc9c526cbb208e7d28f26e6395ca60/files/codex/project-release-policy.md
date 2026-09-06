# Project and release policy

This is Lexer's public-release RDR2 overhaul plus LEXEDITOR.

- `MyOverhaul/`: LML data replacement mod.
- `editor/`: local web editor, normally at `http://127.0.0.1:8765/`.
- `GameplayTweaks/`: C++ ScriptHook ASI containing every custom gameplay
  runtime feature. The dropped Core Ramp source/configuration has been removed
  from the active project; never rebuild or install it.
- `_downloads/extract/`: Lexer's vanilla OpenIV extracts.
- `datasets/`: read-only reference datasets.

Game root:
`C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2`

The project is private and intended for public release. Build from vanilla
extracts. Other mods may be inspected to learn schemas and mechanisms, but do
not ship their files, code, or wholesale values. Record actually used
references in `CREDITS.txt`.

`CREDITS.txt` is public-facing and organized as Required, Included, Research &
Reference (grouped by subject), Tools & Resources, Compatibility, and
Supersedes. Do not include internal TODO numbers, planned-but-unused mods, or
long research essays. Add a mod to Supersedes only after its relevant
functionality is implemented and confirmed.

When researching a game change, first inspect an existing mod that implements
it when one is available, then reproduce the mechanism from vanilla data and
public native documentation. Nexus login-gated files must be requested from
Lexer; never use his account.

Treat public RedM UIApp examples and Cfx's RDR3-specific source as first-class
research for Story Mode, including features previously marked Dropped. Port
underlying Rockstar DataBinding/UIApp/native mechanisms and useful hook or
graphics discoveries when technically and legally portable; do not assume a
Cfx-runtime feature can be pasted directly into a ScriptHook ASI.


