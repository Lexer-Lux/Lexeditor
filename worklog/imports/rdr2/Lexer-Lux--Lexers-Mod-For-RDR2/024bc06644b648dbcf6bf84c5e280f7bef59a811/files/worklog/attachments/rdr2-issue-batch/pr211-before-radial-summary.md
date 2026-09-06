## Scope
Source candidate for Lexer-Lux/Lexeditor#181 and partial diagnostic/safety work for Lexer-Lux/Lexeditor#357. This does **not** claim to resolve the reported in-game crash or the entire RDR2 backlog.

## Changes
- Remove the failed TransitionAnimRate control, observer/state, and animation-speed setter calls, following the explicit removal option in #181. Preserve native binocular draw/stow, early-release latch, readiness checks, and timing gates.
- Remove the setting from the INI and generated menu; hide legacy keys in the presentation schema. Regenerate the menu from this repository's matching schema without unrelated layout changes.
- Check all three getGlobalPtr results before dereferencing the put-away prompt registry. Preserve unrelated prompts and retain the existing registry bounds/identifiers.
- Add granular CRASH_TRACE_STAGE markers around binocular task status, readiness, prompt lookup, forced aim, and update dispatch.
- Add focused CI and append evidence/remaining work to the issue handoffs. The temporary source-import files have been removed.

## Validation performed
- Compiled the **actual extracted production prompt routine** with C++17, -Wall -Wextra -Werror, then executed synthetic null-pointer, invalid-handle, wrong-action, exact-match, and registry-boundary tests.
- All seven binocular retirement/preservation checks pass.
- Existing cigarette-card glint removal check passes and confirms unrelated spent-casing glints remain.
- Generated menu is reproducible from the matching private schema.
- The same source checks passed on GitHub before the production commit was pushed.

## Not performed / acceptance still needed
No production ASI build, game installation, visual acceptance, or gameplay crash reproduction was performed. The checked-in snapshot lacks the external ScriptHook SDK, and this environment is not the user's Windows game installation. The prompt guard fixes a demonstrable null-dereference hazard, **not a proven cause of #357**. Follow the repository's existing build procedure and retained crash-trace evidence for runtime acceptance. Keep the broad issues open/actionable.

No other games, master, runtime data tuning, or unrelated branches were changed.