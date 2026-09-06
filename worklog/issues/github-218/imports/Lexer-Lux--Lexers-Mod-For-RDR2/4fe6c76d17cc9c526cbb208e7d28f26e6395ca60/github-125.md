# GitHub #125 - Dead Eye consumption speed

## Rejected implementation

The first implementation called unknown native `0x22B3CABEDDB538B2`, measured
the raw Dead Eye amount, and nudged the unknown parameter through a proportional
controller. Lexer tested values 0 and 99 and observed no difference. Logging a
requested value was not evidence that the engine applied it.

## Corrected source

The native database names `0xB783F75940B23014` as
`_SET_SPECIAL_ABILITY_DURATION_COST` and documents its argument as a per-second
duration cost. The runtime now passes `ConsumptionPointsPerSecond` directly to
that native while Dead Eye is active and clears the override with 0 when the
feature is disabled or Dead Eye ends. The old unknown native and self-tuning
controller were removed. Raw bar deltas remain diagnostic readback only.

`python tools/reverse-engineering/verify_deadeye_consumption_issue_125.py`
passes. The correction still requires the combined build, hash-verified install,
and an in-game comparison of materially different values.

## 2026-08-10 clamp truthfulness correction

The runtime clamped `-25` to zero but left `-25` in the INI/editor, so the shown
value did not match the applied value. `ConsumptionPointsPerSecond` now has the
same explicit 0..100 range in the editor schema and runtime. The generic settings
save path clamps declared numeric ranges before writing, and runtime load writes
its normalized value back as a final safety net. The shipped INI is normalized
to zero. Static checks verify both paths; the actual Dead Eye rate remains an
in-game acceptance item.
## 2026-08-10 combined release

- Source repair included in release ASI `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`; one hidden payload installer was queued while RDR2 remained open. The issue stayed actionable pending installed-hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- Reading and saving a zero setting is not proof that Rockstar's Dead Eye consumption path uses it.
- The implementation must drive the duration-cost native actually used by the live ability and retain a postcondition/log boundary that distinguishes a zero configured value from zero observed drain. Runtime acceptance is a sustained Dead Eye use at 0 with no core loss, plus a nonzero comparison.

## 2026-08-10 returned-test zero-rate correction

The returned test exposed a direct contract inversion in source. Although the
issue requires `0 points/sec` to mean no Dead Eye consumption, the update path
returned early whenever `g_deadeyeConsumptionRate <= 0.0f`; zero therefore
left Rockstar's vanilla cost untouched. This was not an engine failure—the
requested zero was never submitted.

The corrected path applies `_SET_SPECIAL_ABILITY_DURATION_COST` for every
active Dead Eye frame, including an exact zero. It releases only when Dead Eye
ends. The one-second readback now also runs at zero and reports requested zero,
observed raw-bar delta and the exact submitted duration cost. A zero setting is
no longer documented as vanilla behavior anywhere in source or the INI.

The exact zero/nonzero verifier passed. Installed in development ASI `DB994488E6418520480BE3825614761F4E611CBB4A06BAF52ECE5DD4A6CA3799`; sustained zero-drain runtime remains `test me`.

## 2026-08-10 live zero-value correction

Lexer tested both values. A configured value of 0 still used Rockstar's drain,
while 1 changed the rate. The native therefore treats zero as its default
sentinel rather than as a literal no-drain rate. The earlier source comment and
acceptance claim were false.

The runtime, INI, editor, and in-game settings now use the supported range
1-100. Requests below 1 are normalized to 1 and written back, so the settings
cannot continue to promise a zero-drain value that the engine does not provide.
