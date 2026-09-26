# FF8 codex

Canonical game-specific knowledge. No standalone source has been imported for this game yet; this is a routing page, not a completeness claim. Consult the relevant `worklog/<issue>.md` handoffs and live issues.

- [Triple Triad field opponents](triple-triad.md): entity identity, setup variants, and documented argument meanings.

- [Rebuilding the FFNx runtime](native-runtime-build.md): pinned FFNx revision, toolchain, compile gates and artifact checks.
- [Smooth HP-number colours](hp-colours.md): FFNx RGB seam, verified native HP scopes, and acceptance boundary.

- [Timed hits and blocks](timed-hits.md): the `0xAB` trigger opcode, the Renzokuken/Attack trigger task and its ×1.5 bonus, how it is gated to Squall, and why damage is already applied before a hit lands.

- [Audio volumes](audio-volumes.md): vanilla Sound slider scope, FFNx SFX/Music layer gains, and the #498 split.

- [Altered content](altered-content.md): #319 restoration targets, the nunchaku verdict, and the safe rule.

- [SFX, Models, and Textures assets](asset-tabs.md): audio.fmt layout and FFNx external SFX names, battle `.dat` section inventory, and the verified FFNx external texture paths behind the asset tabs.

- [Sky and fog zones](world-sky.md): the section 32 record, the evidence that its third word is a fade distance rather than a coordinate, and what is not established about how the game blends the zones.  
- [World draw points](world-draw-points.md): where a draw point is stored, how the game resolves a standing position to one record through its block and sub-ID, and why its spell lives in the executable.
- [Editability and the older tools](editability.md): what each FF8 file allows here, why the locked bytes stay locked, and how this plugin's coverage compares with Deling, FF8 Ultimate Editor, Rinoa's Toolset, Jumbo Cactuar, IfritAI and Hyne.
- [The game's own name list](namedic.md): where `namedic.bin` lives inside `main.fs`, its proved count/offset/text layout, and the evidence that a rewritten list keeps every untouched name byte-identical.
- [World to field](wm2field.md): the 72-entry table that sends a world-map position to a field, what its four named fields are, and the bytes it must preserve.
- [World-map scripts](world-scripts.md): the script container wmsetus.obj shares across sections 7, 9, 11 and 36, the four vehicle warp scripts read from section 11, and what is not yet proved about their opcodes.
