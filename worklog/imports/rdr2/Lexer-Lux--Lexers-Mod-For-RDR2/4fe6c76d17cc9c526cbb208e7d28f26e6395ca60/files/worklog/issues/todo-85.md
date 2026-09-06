# Worklog: Todo 85

## #85(b) casing pickup — REVERTED, my regression

The LEX_CASING_PICKUP_UNARMED/_RIFLE states I authored were cloned from
`USE_HANDFULL_SATCHEL_*`, whose ScriptName is `generic_single_use_item` and
whose FALLBACKS@HANDFULL clip sets are the raise-to-mouth CONSUME animation.
Correct hand and correct rifle awareness, wrong verb: Lexer's ped ate the
casing. iteminteractioninfo.meta contains ONLY InteractionType Consumable (105)
and Outfit (12) plus one Weapon - there is no pickup family to clone, which is
what should have been checked before shipping. Both states removed from the meta
(XML re-validated) and script.cpp reverted to the TASK_PLAY_ANIM ground reach,
still suppressed while a longarm is held (attach points 9/10).

## #85 long-gun casings regression — root cause, 2026-08-04

Build `48732242DAB50AC02B08B5EDE035ED047A9B2E75CDD4A42A9FEE5A105D3F051D`.

`GameplayTweaks.casings.log` shows the shot detected and queued every time, then:

    shooting weapon=0x772c8dd6 group=0x39d5c192 clip=4 ammo=26
    cycle eject pending count=1
    ready-flip 1->0 freeAim=0 targeting=0 attackTask=1 accepted=0
    ready-flip 0->1 freeAim=0 targeting=0 attackTask=0 accepted=0
    NO CYCLE detected in 20s for weapon=0x772c8dd6; dropping pending

The ready-flip edge detection works fine. The ACCEPTANCE gate was
`inShootingPosture = freeAim || targeting || attackTask`, evaluated at the moment
of the rising 0->1 flip. A lever/bolt/pump cycle completes AFTER the trigger is
released, so at that instant the combat task has ended and free-aim/lock-on are
both false — the gate can essentially never be true for a long gun. Every pending
aged out at 20 s. Revolvers were unaffected because they eject via the reload
path, not this one.

Fix: a pending eject only exists because a shot was already fired, so the shot is
the proof of intent. Dropped the posture requirement at flip time and bounded it
by `[SpentCasings] CycleWindowMs` (default 8000) since `pe.firedAt`. Posture is
still logged for evidence but no longer gates. If phantom flips reappear, tighten
the window rather than reinstating the posture test.

