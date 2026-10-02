# Remastered native stamina and encumbrance rules

## Identified input and evidence

This map applies only to the 50,286,344-byte executable whose SHA-256 is
`a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b`.
The preferred image base is `0x140000000`. The file contains duplicate section
names, so use the section address ranges, not the first matching name.

The addresses below were traced in that private executable. Its original
functions were then executed in an isolated x86-64 harness with controlled
player/effect structures. This proves the listed computations for those inputs,
not Windows game startup, animation timing, or multiplayer compatibility.
No executable, original function dump, or proprietary parameter archive is
included in the repository.

## Baseline and effect additions

The player recovery getter at RVA `0x35ED00` calls the active-effect accumulation
routine at `0x4034B0`, then adds a native float. The original float is **45** at
RVA `0x1A2BE40`, file offset `0x1A2A240`. The getter is reached through player
virtual slot `0x1F0` by the stamina update.

The isolated test supplied effects with recovery adjustments +10, +20 and -2;
they added 28 to each baseline tested (0, 45, 60 and 200). A fourth effect node
with its inactive flag set and adjustment +500 was excluded. This is not the
`changeStaminaPoint` periodic stamina-damage field.

## Movement classes and recovery

The selector at RVA `0x2E1A10` returns these classes. Ordinary limits are
inclusive at the upper boundary.

| Class | Ordinary load range | Original recovery multiplier |
| --- | --- | --- |
| 0: Ultralight | Within the light range, with the special movement effect | 1.0 |
| 1: Light | 0% through 25% | 1.0 |
| 2: Medium | Above 25% through 50% | 1.0 |
| 3: Heavy | Above 50% through 100% | 0.8 |
| 4: Overloaded | Above 100%, or the forced class condition | 0.7 |

The special and forced inputs are separate from the numeric load ratio.
Ultralight does not have an independent numeric threshold.

The recovery factor is chosen in the player update at RVA `0x356FEA` and stored
at player offset `0x1E4`. The stamina update consumes that factor and the
baseline/effect getter. This is a recovery multiplier, not an animation speed.

The light and medium constants are at RVAs `0x1A2B580` and `0x1A2B444` (file
offsets `0x1A29980` and `0x1A29844`). The overload comparison originally reads a
shared constant. Its one displacement at file offset `0x2E0E1C` is redirected;
the shared constant itself must not be changed.

## Within-class fraction

RVA `0x2E1A70` computes a normalized within-class load fraction. The original
middle denominator assumes the original 25%/50% split. Changing only the
threshold constants is not a consistent implementation.

The replacement uses `(ratio - lower) / (upper - lower)` within each class,
clamped to 0 through 1, and returns 0 above the heavy limit. With original
thresholds, the private-function test matched the original output at 1,101
samples from 0% through 110% load. A 30%/60%/120% configuration was checked at
each boundary and midpoint. The original debug override remains in place.

Only the function body from RVA `0x2E1A7B` through `0x2E1B11` is replaced.
The original stack frame, saved nonvolatile register and epilogue remain.
This does not map every other load-dependent calculation, animation duration
or invincibility window.

## Patch form and ownership

`plugins/ds1/encumbrance.S` is original replacement assembly, independently
rebuilt by a test with `encumbrance.ld`. It uses two existing spans: a 41-byte
factor selection containing five floats and a private heavy-limit float, and
a 151-byte fraction body. No section, trampoline, DLL, new unwind record, or
game-code call is added by the patch.

`stamina_patch.py` verifies the whole pristine executable before transforming
it. Identification of an installed modification requires the verified backup,
an ownership record and exact reproduction of the entire expected image.
Unrelated patches, including other independently owned native PRs, are refused
rather than overwritten.

The original image and one small ownership record are retained. Durable
pending hashes allow interrupted writes to be identified. Restoration reproduces
the original bytes. Parameter deployment separately preserves its original
archive; the pair is not falsely described as one atomic filesystem operation.

## Platform references

Microsoft's [PE format specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
defines the distinction between an RVA and a disk file pointer and the section
mapping used here. Its [x64 exception handling documentation](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64)
describes the stack and nonvolatile-register state represented by unwind data.
The native patch preserves the original frame rather than introducing an
unregistered one.

Changing a signed image's contents invalidates its signature. No signature,
DRM or anti-cheat bypass is implemented or claimed.
