# Out-of-combat sprint
## Dark Souls Remastered | candidate 0.2.0 | issue #856

This is the actual external script mod for Lexeditor PR #918.

**Implemented and tested in isolation, not yet accepted in a running retail game.**
Use an offline test session and keep normal save backups. No multiplayer or
anti-cheat safety claim is made.

## What changes

The mod redirects only the native sprint stamina charge. While no living AI
character is in its native battle state targeting the local player, that charge
does not consume stamina. Combat entry and exit follow the game's state and
target changes at the next sprint-charge tick. There is no added delay.

Attacks, dodges, blocking, other stamina costs, recovery rules and the stamina
cap are unchanged. This is not a refill or a global infinite-stamina flag.
The normal rules still decide whether an exhausted character can start sprinting.

Another loaded player instance, unsupported or incomplete enemy data, and an
unresolved battle target retain normal sprint costs. This includes co-op.
The code uses native battle and target getters, with checks before calling them.
It is an Elden Ring-style backport, not a claim of identical Elden Ring internals.

## Install and use

1. Extract the `out-of-combat-sprint` folder into your **DS1 mod library**.
2. Restart the DS1 editor. In **Tweaks**, review and explicitly trust
   **Out-of-combat sprint**, enable it, close the game, and select **Apply**.
3. No compiler or separate DLL is needed on the player's machine.

The package starts disabled and untrusted. Importing it does not modify game
files. The shared mod host builds `native/out-of-combat-sprint.json` and combines
its native patch with the other enabled native script mods.

The original must be `DarkSoulsRemastered.exe`, 50,286,344 bytes, SHA-256:
`a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`.
Other builds, Prepare to Die Edition, and unowned executable changes are refused.

## Verification supplied

- 16 package tests passed with zero skips on Linux using the actual host modules.
- Native tests made 156 calls: 47 cases at each of three code addresses, plus
  five combat-transition ticks at each address. The inspected native getters
  came from the supplied private executable; the stamina writer was a test spy.
- Exact hook-only preservation, assembly rebuilding, relocations, unwind data,
  neighboring native patch composition, and Apply/Restore byte preservation
  were checked.

These are not in-game tests. Remaining checks include Windows startup, real
traversal/aggro/de-aggro and boss fights, death/reload, unchanged combat-action
costs, dense-area performance, entity lifetime/thread safety, and in-game
restoration. The package does not establish save safety or online safety.

## Reproduce the developer tests

Python, pytest, GNU binutils and GCC are needed for all tests. From this
unpacked mod folder, set `PYTHONPATH` to a Lexeditor checkout and
`LEXEDITOR_DS1_NATIVE_EXE` to a private, unmodified supported executable:

```sh
python -m pytest -q -p no:cacheprovider tests/test_sprint_mod.py
```

Without the private executable, private-image tests skip. Do not report a
skipped run as full validation.

No original executable, game-function dump, game assets, fonts or trust
credentials are distributed.
