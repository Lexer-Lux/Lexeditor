# GitHub #183 — carried-mask item-info stack overwrite

## Recurrence audit

- Failure class: an undocumented or decompiler-sized native output buffer can
  overwrite the plugin stack and report `ERROR:FFFFFFFF` later.
- Primary evidence: `RDR2.exe.325624.dmp`, the matching ASI/map, and
  `_downloads/natives.json` for `ITEMDATABASE_FILLOUT_ITEM_INFO`.
- Execution proof: the dump reported `FAST_FAIL_STACK_COOKIE_CHECK_FAILURE` in
  `GameplayTweaks.asi`; the return address resolved to `itemCategory()`.
- Player-visible acceptance: startup and the #151 holster transition do not
  crash. Static structure and hashes alone cannot establish this.

## 2026-08-11 repair

The installed log ended on the same frame as #151's first LOADOUT_3 transition,
but the minidump did not place the fault in that module. It placed the corrupted
return in `itemCategory()` inside the carried-mask scan. That helper copied the
decompiler's `struct<2>` display and passed only two 64-bit `Any` slots to
`ITEMDATABASE_FILLOUT_ITEM_INFO`. Public DataView callers allocate six to eight
64-bit slots and read the category from slot 1. The native wrote past the
two-slot local and the compiler cookie failed on return.

The helper now supplies eight zeroed `Any` slots and reads category from slot 1.
This preserves two guard slots beyond the observed six-slot contract.
Verification rejects the old two-field buffer. The #151 transition remains in
source because it exposed, but did not itself contain, the invalid output-buffer
ABI. Runtime acceptance remains required.
