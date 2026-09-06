# GitHub #162 - Aim Tolerance Screen Radius still does nothing

## Live report

The live issue has an empty body and no comments. Its complete authoritative
request is the title: `Aim Tolerance Screen Radius` still produces no visible
change. This is a returned runtime failure, not a request to retune its number.

## fuckups.txt recurrence audit before code

- **Primary evidence/reference:** inspect the exposed setting, its load and
  hot-reload path, the exact screen-space aim/tolerance comparison, and the
  installed recon log. Resolve projection units against the native output
  before changing any threshold.
- **Sanctioned path:** one normalized screen-space distance test should govern
  recon acquisition. The configured radius is already in the same normalized
  0..1 coordinate space returned by `GET_SCREEN_COORD_FROM_WORLD_COORD`; no
  viewport/pixel conversion or second independent aim cone is sanctioned.
- **Execution proof:** always-on bounded diagnostics must record the effective
  normalized radius, measured target distance, and pass/fail/rejection result.
  A config-load line alone is not proof that the comparator executed.
- **Player-visible acceptance:** a small radius only acquires targets very near
  the reticle; a deliberately large radius visibly acquires targets farther
  from it, without changing completed-tag placement or binocular readiness.
- **Every per-frame native:** projection/viewport reads are allowed only during
  active recon acquisition. Configuration polling and diagnostic output must be
  bounded; no per-frame native setter or whole-world scan may be added.

## 2026-08-10 issue-local repair

The setting was wired to the ped and plant comparisons, but two lifecycle bugs
made its live effect misleading. Startup in shared `script.cpp` silently capped
every value above `0.15` to `0.15`; the live INI requested `1`, so the value the
player was testing was not the value the comparator received. The radius also
was not part of recon's bounded reload, so editing it in a running game did
nothing until an ASI/game restart.

`reconRefreshCachedSettings()` now rereads the normalized radius every two
seconds and clamps it to `0.001..0.70710678`. The upper bound is the exact
normalized distance from screen center `(0.5,0.5)` to a corner, so `1` now
means the entire projected screen rather than the old hidden `0.15` ceiling.
The ped, direct plant-visual, and typed plant-scenario paths continue to compare
against the same `g_reconAimRadius`.

The bounded logs now report requested/effective radius, nearest/best measured
ped distance, ped radius-rejection count, nearest plant distance, and plant
rejection count. This distinguishes “setting loaded” from “comparator executed
and rejected/accepted a candidate.”

Static verification: `python tools/reverse-engineering/
verify_recon_aim_tolerance_issue_162.py`. Runtime acceptance still needs one
comparison: hot-reload `0.01`, observe off-center candidates rejected with a
measured distance above radius, then set `1` and observe the same candidates
survive the radius gate within two seconds. LOS, distance, projected-size, and
tagged-state gates remain in force. No shared INI/dispatcher, build, install,
manifest, or label was changed.
