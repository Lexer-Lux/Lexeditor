# Lexer-Lux/Lexeditor #357 — binocular crash investigation

## 2026-09-06 pre-change evidence and acceptance boundary

Read fuckups.txt, current issue #357 and related #181 source/conversation.
Primary source: combat_inventory.cpp suppressNativeBinocularPutAwayPrompt
unconditionally dereferences three getGlobalPtr results. The existing registry
base, stride, allocation flag and INPUT_CAMERA_PUT_AWAY predicate are retained;
none is invented or retargeted. A null result is a demonstrable access violation
in this C++ path, but no supplied crash trace proves it caused the user's event.

Recurrence risks: assuming a cause from one occurrence, fabricating addresses,
removing unrelated Study prompts, and marking an unbuilt patch accepted. Planned
execution proof: compile and execute the actual extracted prompt routine against
null/partial/populated synthetic registry stubs. Trace stages distinguish swap
status, camera-readiness, forced-aim and prompt lookup; existing crash-file
rotation remains unchanged. Player-visible acceptance is crash-free native
binocular entry and preserved Study/Info and put-away behavior after an actual
ASI build/install. No runtime completion is claimed.

## Execution results

GCC C++17 -Wall -Wextra -Werror compiled the actual extracted prompt routine.
The executable passes null flags/action/handle, invalid handle, unrelated action,
matching action and final registry-slot cases. Existing cigarette-card removal
verification also passes and spent-casing glints remain present. These are unit
and source checks only; no Windows ASI build or game launch occurred.

## Fresh-checkout integration preflight

Primary evidence: GameplayTweaks/build.bat calls release_manifest.py verify before
compilation; asi_hash() exits when no prior GameplayTweaks.asi exists. The same
entry point assumes the caller's current directory, one absolute SDK location,
and the BuildTools VS2022 edition. These prevent a clean Windows checkout from
compiling the crash candidate. The authored compile/link inputs and libraries
remain authoritative; no native signature, gameplay constant or reference-mod
implementation is being guessed. SDK source is the already-credited
Smerdokryl/RDR2_SDK at ef53fc71e0ad95cfa8e72a63f15e1c6aa38091de.

Recurrence risks read in fuckups.txt: claiming builds as runtime acceptance,
omitting link inputs, replacing existing artifacts after a failed compile, and
reintroducing the explicitly removed issue-label manifest. Planned execution
proof: Windows tests of the actual batch entry point from an unrelated working
directory, first build, rebuild, missing SDK, compiler failure, and stale hash;
then compile the complete production translation unit. No installer or user
INI will be touched, and no build will close an issue or assert crash acceptance.
