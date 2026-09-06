# Worklog: Todo 203

## #203 core writes — previous fix DISPROVEN by measurement 2026-08-05

Measured the earlier "symmetric tick" fix against Lexer's own post-fix session
(GameplayTweaks.reserve.log, last 40k lines): 30,833 samples, 1,687 core-value
changes = one change every 18.3 frames. The PRE-fix measurement was 18.2. The
fix accomplished nothing. It only reversed which side wrote last - the game
raises the core, we lower it, every frame - so the flicker and the screen pulse
were unchanged. Recorded here because the earlier entry claimed success on
reasoning alone and it was wrong.

ROOT CAUSE (hypothesis, self-verifying in code): SET_CORE used
0xC6258F41D86676E0 `_SET_ATTRIBUTE_CORE_VALUE`, which sets the DERIVED core
readout. The authoritative store is attribute POINTS - Rockstar's own scripts
convert explicitly, `SET_ATTRIBUTE_POINTS(ped, index, coreValue * 100)`
(abigail2_1.c:73128 and many others), so 1 core point = 100 attribute points.
The game recomputes the core from points every frame, wiping our write.

CHANGE: SET_CORE now writes 0x09A59688C26D88DF SET_ATTRIBUTE_POINTS with
value*100. `[CoreClock] WriteMode=0` restores the old setter. On the first
disagreement between the requested value and GET_CORE readback it writes one
line to GameplayTweaks.cores.log naming the fallback - so if the hypothesis is
wrong we learn it from the log instead of another round of claims.
If correct this is the shared cause under #203, #1 (swim + horse reserve) and
#19.

## #203 Intermittent fader/haze — root-caused and fixed 2026-08-05

Symptom: a low-stamina-like haze washing in and out continuously, unrelated to
what the player was doing.

Ruled out first, with evidence, not assumption:
- Toxicity/`SA_POISONED` (attribute 11) is forced to 100 every frame while
  active and would produce exactly this class of effect — but
  `GameplayTweaks.toxicity.ini` does not exist in the game folder, so
  `g_toxicActive` was false the whole session. Not it.
- No `ANIMPOSTFX`, timecycle or drunkenness call is on any per-frame path.
  `updateAlcohol` only fires on an observed inventory decrement.

Actual cause, from `GameplayTweaks.reserve.log` (4.3 MB, session ending
2026-08-04 21:01). 30,620 samples parsed: the logged core pair changes value
1,682 times, i.e. once every ~18 frames, all session. The stamina core
oscillates 61-60-61-60 while `stamina=89.6`, `exhausted=0`, `sprinting=0` — the
outer bar is nowhere near empty and nothing is being spent. Dead Eye shows the
same +/-1 flicker superimposed on a genuine downward drain.

Mechanism: the CoreClock loop in `script.cpp` refused vanilla's one-point
background core DROPS ("CoreClock replaces that metabolism") but accepted its
one-point background GAINS unconditionally:

    else if (live > managedCore[core] || live < managedCore[core] - 1) managedCore[core] = live;

So `drainCoreByMinutes` applied a -1, vanilla regen applied a +1, the guard
accepted it, the next clock tick applied -1 again. A permanent ~3 Hz fight. The
game flashes its core-state screen treatment on those transitions.

Fix: make the rule symmetric — one-point native ticks are refused in BOTH
directions, multi-point moves (real refills and real scripted penalties) still
pass.

    else if (live > managedCore[core] + 1 || live < managedCore[core] - 1) managedCore[core] = live;
    else if (live != managedCore[core]) SET_CORE(ped, core, managedCore[core]);

Built with `build.bat` (exit 0; only the pre-existing C4838 narrowing warnings
at script.cpp:1813). Installed to the game folder with the game closed and
hash-verified: SHA-256
`6C40FF0CDF44D8B56B8CCE4E66451F651E0A0B28EC1CE6E2A486D0553513C046` matches
source and destination.

Prediction to check on the next session: the same log should now show the core
pair changing only on genuine drain ticks and refills, not ~1,700 times.


