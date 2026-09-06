# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356317434 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/242

Created: 2026-08-10T12:35:47Z; updated: 2026-09-05T07:02:25Z

Exact metadata: [source record](sources/issue-5356317434-3ea7a465e6feb13c1c71dcc9cf10f135325ff526a95f2ca6e36120c5f8aaedf5.json).

## Problem

Repeated releases have reproduced failure classes already documented in `fuckups.txt`: invented or overstated evidence, intent-only logs treated as execution, per-frame fights with Rockstar systems, uninspected reference artifacts, and static/API checks presented as proof of visual behavior.

The current actionable batch reproduced several of them: Lexer-Lux/Lexeditor#236 forced the locomotion graph every owned frame, Lexer-Lux/Lexeditor#105 shipped an unverified rotation guess, and Lexer-Lux/Lexeditor#154/#62 were treated as repaired without rendering the resulting editor screens.

## Required workflow

- Read `fuckups.txt` before implementing or repairing an issue.
- Immediately before any workflow-label change, re-read the live issue body and every comment added since the candidate was implemented. Any unanswered or unimplemented user requirement keeps the issue actionable.
- Add an issue-specific recurrence audit to its worklog before code: primary evidence/reference, sanctioned engine path, execution/postcondition proof, every per-frame mutation, and the player-visible acceptance boundary.
- Do not ship unresolved constants, hashes, flags, texture names, call-site claims, or pose axes.
- A configuration line, setter call, build, hash, or syntax/API check is not behavior acceptance.
- Visual/UI repairs require an actual rendered wide and narrow check.
- Supplied reference mods/logs/screenshots must be inspected before proposing a cause.

## Acceptance

The current actionable batch is rebuilt only after every included issue has the recurrence audit and its relevant checks. Returned failures stay `actionable`; only installed runtime candidates move to `test me`, with visible behavior still left for in-game confirmation.

## issue 5356317434 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/242

Created: 2026-08-10T12:35:47Z; updated: 2026-09-06T13:17:57Z

Exact metadata: [source record](sources/issue-5356317434-bd4ab57cbdf86d0bf03d675baa3183a79a3addd88ce164436883838081304850.json).

**Status: Closed as a development-process improvement.** Release checks require issue-specific evidence and reject known unsafe approaches before shipping. This is automated/internal work, not a gameplay feature for you to test; implementation logs do not belong in the issue body.

## comment 5550147369 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/242#issuecomment-5550147369

Created: 2026-08-10T17:01:10Z; updated: 2026-08-10T17:01:10Z

Exact metadata: [source record](sources/comment-5550147369-44cf319b901a01e2abb8c07c37afdb96b6ce039b7541bfcbe2d381c41fc9a40b.json).

The recurrence-audit gate is now applied to every issue included in this repair batch: each has its issue-specific audit before code, relevant scoped checks, and an explicit player-visible boundary. The reconciled batch was built only after all agents stopped and no partial source remained. This process issue is now in test me: its acceptance is whether subsequent issue handling continues to follow those safeguards, not whether a compile or hash alone proves a feature.

## comment 5550147375 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/242#issuecomment-5550147375

Created: 2026-08-12T12:34:55Z; updated: 2026-08-12T12:34:55Z

Exact metadata: [source record](sources/comment-5550147375-666deca2fabe7931722af959f43e4fd107095814c04290d4814b6e0c84150717.json).

I don't really know want you want me to do here? What am I supposed to be testing?

## comment 5550147381 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/242#issuecomment-5550147381

Created: 2026-08-12T13:23:11Z; updated: 2026-08-12T13:23:11Z

Exact metadata: [source record](sources/comment-5550147381-7c1fc961441c7c7ad4856a4a40791602b9ebc7dd07377f7b509d171b92af7b53.json).

You do not need to test anything in-game for this issue. The build now runs an automated fail-closed guard before release verification. It excludes Claude-labeled work and refuses the build when a changed actionable issue lacks its failure class, primary evidence, sanctioned path, execution proof, per-frame mutation inventory, or player-visible boundary. Its ten self-tests passed, and it blocked this build until the current audits were corrected. I am closing this process issue as implemented.
