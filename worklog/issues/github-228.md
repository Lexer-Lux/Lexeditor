# #228: Make maximum bounty values configurable

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/228)

## Requirements and decisions

Read the live GitHub issue and comments before implementation or status changes. Use the current issue, relevant central Worklog/Codex material, and available chat/file context; do not recreate a local issue archive.

## Current implementation and evidence

Reconcile live code, PRs and existing topic/session worklogs. Do not infer build, deployment, gameplay success, or acceptance from documentation alone.

## Next agent work

Read the live issue and comments and preserve the latest explicit human corrections in this concise handoff. Do not create source-record, conversation, or attachment archives.

## 2026-09-08 recovered maximum-bounty path

Read live #228 and the retained original request. It asks for bounty maximum
changes; no replacement amount is specified. Existing wanted-system and bounty
hunter verifiers were read before runtime inspection. The wanted module is an
observational trace and must not be converted into an unverified state mutator.

New concrete evidence replaces the earlier 'no native/global found' dead end:

- short_update.c func_2107, lines64399-64420, selects30000,50000,150000 based on
  story progression (func_2323 and func_767). Network mode returns-1.
- func_790, lines26990-27033, gets that cap, clamps the requested bounty, calls
  PLAYER::_SET_MAX_WANTED_LEVEL_2(cap), sets the live local bounty, and persists
  the clamped regional amount to Global_40.f_358[region*12].
- The misleadingly named native resolves to0xEA6DE0CD15AECBE2 in both the local
  native database and SDK header. It is supplied bounty amounts, not0..5 wanted
  stars, by this Rockstar function. The separate SET_MAX_WANTED_LEVEL hash is
  0x28A4BD2CEE236E19; do not substitute it.
- func_174, called from the active short_update loop atline861, invokes func_790
  on the current bounty and on region-state changes. Thus native-only raising
  can be overwritten and still loses amounts to the independent script clamp.

Added tools/verify_rdr2_bounty_cap_evidence.py. It checks cap selection, correct
native identity, the independent clamp, ordering before live/persisted writes,
and active call path. Three mutated sources are rejected. Run passed. The tool
explicitly reports NOT IMPLEMENTED; this is source evidence, not game acceptance.

Exact next implementation work:
1. Obtain the installed-build short_update script bytes and establish a verified,
   reversible script-function patch path. Replace the cap-return policy used by
   func_790, so the same configured amount reaches both engine and regional clamp.
2. Match the complete function and native-call context, not a global search for
   30000/50000/150000; those constants occur in unrelated timers and money paths.
   Require a supported script fingerprint and fail closed on unknown builds.
3. Configure the replacement in bounded currency units with explicit conversion;
   update active and saved regional behavior together. Do not write progression
   globals or relocate story state to bypass the chapter-dependent function.
4. Verify below/at/above cap, crime increases, region changes, payoff, reload,
   mission overrides, and restoration when disabled. Preserve existing bounties
   when disabling; do not zero them as a cleanup action.

No RDR2 script-bytecode patch infrastructure or extracted short_update bytecode
was found in the checked runtime/tools paths. That recovery remains agent work.
No functional setting was exposed. No runtime source, game data, build, install,
or game process changed. Issue remains actionable.

## Installed-bytecode extraction follow-up

Installed RDR2.exe reports1.0.1491.50. RpfCli1.3 listings locate the scripts in
update_2.rpf at x64/levels/rdr3/script/script_rel.rpf. Metadata read from the
existing read-only RPF library: offset39008000, size113038110, outer entry key255
(unencrypted). Reading only its16-byte header directly gives RPF8 magic,
1639 entries,27470 name bytes, PC platform121, encryption tag198 (0xC6).

RpfCli --list-chain fails with "Can't get encoder key!". Its shipped dictionary
has164 keys and does not contain198. This is a specific missing inner-directory
key, not a nonexistent archive or failed plain filename lookup. No short_update
bytecode was recovered. Do not use decompiled positions as live memory offsets.

The list-chain implementation unexpectedly wrote a113038110-byte temporary
nested archive before the missing-key exception. Verified and removed only that
created temp file; no source archive changed. This exposes a separate temporary
cleanup defect in RPF8.Load(VirtualPath,bytes): it sets IsTemp only after a
successful nested load. Future attempts must preflight keys or guarantee cleanup.

Recovered versioned decompilation already present locally:
C:/RDR2Mod/_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/short_update.ysc.c
Source repository: https://github.com/creativewild/rdr2-scripts-decompiled.git
Commit953155c10ab0809fdcfb287f98650cd7e7eed1c4
SHA256216119D7DCB5455E3C4A9DF49ED30388F42461AEC7E26F705D8E975A0B62A298.
It confirms both cap layers and annotates these bytecode regions:
- func_2107 cap selector:0x559A2 to next function0x559FC (90 bytes).
- func_790 clamp/apply/persist:0x2494B to next function0x24A0B (192 bytes).

The evidence verifier now checks this exact source fingerprint and annotated
mapping when available. It passes but explicitly says installed bytes are NOT
verified. Existing local tools have no RDR2 bytecode assembler/patcher; the RDR1
patcher targets another format. No blind constant replacement is permissible.

Next: supply/support the actual tag198 decryption path, extract only short_update,
verify its resource/native table and full opcode ranges against this versioned
mapping, then design the guarded cap-policy replacement. No patch tool can safely
write offsets from source annotations alone. This remains actionable research.
