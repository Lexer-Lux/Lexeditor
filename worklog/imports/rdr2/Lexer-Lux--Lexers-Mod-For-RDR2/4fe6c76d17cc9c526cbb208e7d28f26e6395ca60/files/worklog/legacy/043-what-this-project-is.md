# Worklog: 043 What This Project Is

## What this project is

Lexer's RDR2 overhaul mod, **intended for public release** (Nexus etc.), plus
the tooling to build it. The from-scratch rule is a hard requirement.
STATUS 2026-07-06: vanilla extraction is DONE (via OpenIV) and MyOverhaul is
rebased on vanilla — the old third-party [DEBT]s are resolved except catalog
values for 69 post-1.0 DLC items.
Three parts:

1. **MyOverhaul/** — the LML data mod (prices, item effects, loot, challenges).
2. **editor/** — local web editor (`python editor/server.py`, port 8765, or
   `Start Editor.bat`). Datasets: `mine` (MyOverhaul, editable), `prices1899`
   and `vanilla` (read-only references in `datasets/`). Only `mine` is writable.
3. **Script mods** (C++ .asi) — `CoreVignetteRamp/`, `GameplayTweaks/`.
   Compiled with the
   user's VS2022 BuildTools:
   `cmd /c '"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && cl /nologo /O2 /EHsc /MT /LD main.cpp script.cpp /I C:\RDR2Mod\_downloads\RDR2_SDK\SDK\inc /link C:\RDR2Mod\_downloads\RDR2_SDK\SDK\lib\ScriptHookRDR2.lib /OUT:Name.asi'`
   Installed by copying the .asi (+.ini) into the game root.

Game install: `C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2`
(has LML, ScriptHook RDR2, asiloader, several third-party .asi mods).

