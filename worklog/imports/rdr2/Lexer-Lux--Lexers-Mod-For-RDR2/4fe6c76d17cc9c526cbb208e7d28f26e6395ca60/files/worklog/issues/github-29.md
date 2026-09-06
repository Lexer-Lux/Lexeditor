# GitHub #29 - Animal Spawn Multiplier

## Returned runtime result

Lexer held the setting at both 0 and 99 for extended play and reported no
credible difference: deer were still encountered at 0, and 99 did not produce
an obvious increase. The installed unified log proves the runtime path executed
with `Enabled=1` and INI value 99, but it also proves the runtime silently
applied 10 instead. A setter call and that log line do not prove a visible
population result.

## Issue-local correction and boundary

The old inline implementation clamped every value above 10 even though neither
the editor nor INI described that limit. The issue-local replacement forwards
the requested nonnegative finite value to both NativeDB-resolved per-frame
natives:

- `0xC0258742B034DFAF` — `_SET_AMBIENT_ANIMAL_DENSITY_MULTIPLIER_THIS_FRAME`
- `0xDB48E99F8E064E56` — `_SET_SCENARIO_ANIMAL_DENSITY_MULTIPLIER_THIS_FRAME`

Rockstar's shipped scripts continuously call the ambient native with 0, 1, or
2 while missions own population suppression, confirming float type and
per-frame cadence. The replacement retains that cadence and adds a bounded
15-second heartbeat naming configured versus applied values.

This does not delete already-streamed animals and cannot claim ownership of
animals explicitly created by Story scripts. Therefore seeing one deer after
setting 0 is not, by itself, a postcondition for either spawn multiplier. The
next controlled test must change the setting before travelling into a newly
streamed wilderness area and compare newly generated ambient/scenario groups;
the feature remains unaccepted until that produces a visible difference.

The feature agent did not edit the integration-owned inline block or register
the new module. Integration must replace the old block with
`updateAnimalDensity()` so the old 10x clamp does not overwrite this module's
value later in the same frame.
## fuckups.txt recurrence audit

- The old implementation logged the configured value `99` but silently clamped the applied value to `10`; that configuration log was falsely treated as behavior evidence.
- The dedicated module now logs configured and actually applied density with no hidden upper cap. Runtime acceptance still requires newly streamed wilderness populations at controlled 0 and high settings; already-streamed or scripted animals are not valid evidence either way.

## 2026-08-10 returned 999x result

The later installed log removes the old clamp as an explanation. It records
`configured=999 applied=999 enabled=1 cadence=every-frame` in the same session
where Lexer still saw no visible increase. That proves only that both native
calls received 999; it does not prove either population system accepted the
value or produced another animal. The local native database exposes no result
getter, and Rockstar's Story scripts demonstrate only 0, 1, and 2. Raising the
global population budget would affect every population family and Rockstar's
missions use it only at or below 1, so that is not an evidence-backed animal
fix and was not added.

The module now records a bounded observed-population window in addition to the
setter heartbeat. Every five seconds it reuses the existing shared 256-ped
snapshot, counts only nonhuman peds, and accumulates their numeric
`GET_ENTITY_POPULATION_TYPE` values. Every stable minute it logs the actual mean
loaded-animal count, unique handles, and population-type histogram. The types
remain numeric because no RDR2 primary source proves GTA's enum names carry over.
It also reads the engine's current population-budget multiplier for diagnosis.
The observer never creates, deletes, moves, owns, or marks a ped and never
changes the global population budget.

This is execution evidence, not a completed feature. #29 remains actionable
until stable 0/1/2 windows prove which native population classes respond, or a
different sanctioned engine path is found. The failed 999x run must not be
relabelled `test me` as though forwarding the number fixed it.

## 2026-08-10 installed observation handoff

The combined development build containing the one-minute, read-only population
observer was installed as
`5B34E2E779174554F646156A42A9FD296846BF7ED65D9748035D8334E6C153FA`.
The test configuration was changed from the disproven `999` to the highest
value directly demonstrated by Rockstar's Story scripts, `2.0`. This is a
diagnostic configuration, not a claimed engine limit and not a claimed fix.

No further source-side conclusion is possible without at least one stable
one-minute newly-streamed wilderness window. The issue therefore requires a
manual in-game observation and belongs in `needs a human`, not `test me` and
not `actionable`, until that evidence exists. The observer itself does not
mutate, clone, delete, move, or take ownership of animals.
