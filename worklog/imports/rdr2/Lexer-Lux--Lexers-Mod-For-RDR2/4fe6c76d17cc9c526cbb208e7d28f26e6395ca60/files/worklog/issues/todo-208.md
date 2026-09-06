# Worklog: Todo 208

## #208 dodge roll — engine task confirmed, clip DICTIONARY still unknown 2026-08-05

What the game actually ships, from static evidence only:

- `mech_weapons_core@base@dive@{pistol,rifle,unarmed}@{launch,prone,getup}` is the
  dive Lexer wants replaced — a three-part launch/prone/getup sequence, not a roll.
- `CTaskCombatRoll` is real and resident: `anim/move_networks/move_networks.xml`
  has `<Item key="TaskCombatRoll">` with `SP_SINGLEPLAYER_RESIDENT`, and
  `action/special_conditions.meta` uses an `IsDoingCombatRoll` condition.
- `PED::GET_PED_IS_DOING_COMBAT_ROLL` (`0xC48A9EB0D499B3E5`) exists in the native
  DB. There is NO task native to start one; the only script entry point is
  `DEPRECATED_SCRIPT_TASK_COMBAT_ROLL`, and no shipped script calls it.
- The clip names ship as archive entries: `COMBATROLL_FWD_P1_{00,45,90,135}`,
  `COMBATROLL_BWD_P1_{135,180}`, the same set as `P2`, plus the bare prefixes
  `COMBATROLL_FWD_P1_` / `COMBATROLL_BWD_P1_` — so the signed (right-hand)
  spellings are composed by the engine at runtime and cannot be confirmed
  statically. So Lexer is right that the animation is already in the files.
- NO dictionary name containing a combat roll appears anywhere in ArchiveItems,
  DataLines or MemberNames, and no `/ANIM/INGAME/CLIP_*` folder is roll-specific.
  The previous version of this feature hardcoded `mech_strafe@generic@roll@base`,
  which appears in no dump in any casing — it never streamed, so the function
  returned at the `HAS_ANIM_DICT_LOADED` guard on every frame and the feature had
  never once run. That is why "readd it" was correct even though code existed.

What was built instead of another guess: the dictionary is resolved at RUNTIME.
`STREAMING::DOES_ANIM_DICT_EXIST` (`0x537F44CB0D7F150D`) answers for a name
without streaming it, so a wide candidate list is tested for existence in one
pass, each existing name is streamed, and one is accepted only when
`GET_ANIM_DURATION` reports a real length for at least one combat-roll clip.
Everything — the full existence table, the accepted dictionary, the clip subset
that exists, every played roll, and any time the engine reports a combat roll on
its own — goes to `GameplayTweaks.roll.log`. `[CombatRoll] AnimDict=` names a
dictionary directly and retries resolution on hot-reload with no restart.

Until a dictionary resolves the Dive control is NOT disabled, so a miss degrades
to Rockstar's vanilla dive rather than deleting the move.

Direction: `INPUT_MOVE_LR/UD` plus `GET_GAMEPLAY_CAM_RELATIVE_HEADING` give an
Arthur-relative angle; the nearest clip that actually exists is chosen. Travel is
velocity-driven for the clip's own duration (`AssistMetersPerSecond`, default
4.5) because authored displacement is uneven — the same trap that made prone
crawl slide.

Climbing (#169) safety: the roll takes `INPUT_DIVE` only, never `INPUT_JUMP`, and
`RequireAiming=1` restricts it to a gun being up, which is when the vanilla dive
happens anyway and is never true during a direction+Jump climb.

Built clean (two pre-existing C4838 warnings at script.cpp:1977, unrelated),
source hash `65BA83FEA02D8E210BB4D7C996BC69D2B118D895FA185996A251650DC614F1D9`.
`GameplayTweaks.ini` copied to the game root live (hash-verified). The `.asi` is
installed and hash-verified in the game root as of 2026-08-05 08:26.

The deferred install exposed a second defect, now fixed: with
`ErrorActionPreference Stop`, `Install-When-RDR2-Closes.ps1` aborted on the
missing optional `CoreVignetteRamp\CoreVignetteRamp.ini` at line 9, one line
BEFORE the `GameplayTweaks.asi` copy — so it had been shipping nothing while
reporting nothing. Each payload is now copied and hash-verified independently,
a per-file report is written to `install-when-closed.log`, and a required
failure exits non-zero.

Next step is decided by the log, not by another guess: if the existence table is
all `missing`, the clips live in a dictionary whose name is not in any dump and
OpenIV / a `.ycd` listing of `CLIP_MECH_WEAPONS_CORE` and `CLIP_MECH_STRAFE` is
required to read it. If the engine line ever appears without ours, vanilla still
enters `CTaskCombatRoll` and finding that trigger beats playing a clip by hand.

