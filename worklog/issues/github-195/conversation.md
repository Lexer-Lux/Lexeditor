# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356305892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/195

Created: 2026-08-06T05:59:31Z; updated: 2026-09-05T06:59:54Z

Exact metadata: [source record](sources/issue-5356305892-a7867a65d64e51ffc830ca7d1f7774348378574a74da880be4956fcbb3b83a55.json).

## Requested behavior

Replace the current lost-money “bloodstain” presentation with a recoverable version of the last hat the player wore.

### On death

- Leave the last hat the player wore on the ground near the death location.
- Store the recoverable money on that hat/bloodstain.
- Replace the current bloodstain map icon with the new bloodstained-hat icon:
  - `GameplayTweaks/icons/build_blips/blip_hat_bloodstain.dds`
  - PNG preview: `GameplayTweaks/icons/build_blips/download.png`
- Show a corner notification with this exact text:

> Find your hat where near where you died and collect it to reclaim your money. If you die before then, it will be gone forever.

### Recovery

- Picking up the hat returns the stored money.
- The recovered hat/bloodstain, its map marker, and its world marker then dissipate immediately.

### Second death

- Only one recoverable bloodstain may exist.
- If the player dies again before recovering it, the previous hat and its stored money are permanently lost.
- The new death may then create the new recoverable hat/bloodstain from the last hat worn and the money lost on that death.

## Player-visible acceptance

- [ ] Die while wearing or having recently worn a hat and confirm that specific last-worn hat appears on the ground near the death location.
- [ ] Confirm the map uses the bloodstained-hat icon rather than the cash-bag icon.
- [ ] Confirm the corner notification appears once with the exact approved wording.
- [ ] Pick up the hat and confirm the stored money is returned and every bloodstain marker/effect disappears.
- [ ] Die again before recovery and confirm the previous hat and money are gone forever rather than duplicated or recoverable.

## Superseded behavior

The prior cash-bag prop/icon presentation and its test checklist are superseded by the hat-based behavior above.

## issue 5356305892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/195

Created: 2026-08-06T05:59:31Z; updated: 2026-09-06T13:07:27Z

Exact metadata: [source record](sources/issue-5356305892-f25fbdbbd64257302af8c7aa931864d7fa94c7569b30e7e5dbeb6e4e0ae0d11f.json).

**Status: A hat-based recovery build is installed; confirmation remains.** Respawn placement is a separate issue in #244.

- [ ] On a spare save with cash and a worn/recently worn hat, die. Confirm that hat and a bloodstained-hat marker appear near the death location, with the recovery warning.
- [ ] Retrieve it: confirm the stored money returns once and the hat recovery markers disappear.
- [ ] Repeat, but die again before recovery. Confirm only the newer recovery remains and the older money is permanently lost. Report the failed step.

## issue 5356305892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/195

Created: 2026-08-06T05:59:31Z; updated: 2026-09-06T13:57:53Z

Exact metadata: [source record](sources/issue-5356305892-a2e8dc0e2b47cc01e66f9f168b9c1434a58f34e5fb70924b589049f0cef73805.json).

**Status: A hat-based recovery build is installed; confirmation remains.** Respawn placement is a separate issue in #244.

- [ ] On a spare save with cash and a worn/recently worn hat, die. Confirm that hat and a bloodstained-hat marker appear near the death location, with the recovery warning.
- [ ] Retrieve it: confirm the stored money returns once and the hat recovery markers disappear.
- [ ] Repeat, but die again before recovery. Confirm only the newer recovery remains and the older money is permanently lost. Report the failed step.

## comment 5550134513 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/195#issuecomment-5550134513

Created: 2026-08-06T14:42:26Z; updated: 2026-08-06T14:42:26Z

Exact metadata: [source record](sources/comment-5550134513-c13a0cfe03ada95d531ef3dad34898d026b3ff6859cac2240805ca9f2aa6aa99.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Die with a worn/recent hat: confirm that exact hat appears at the death location with the bloodstained-hat icon and approved notice; pickup must restore money and clear everything; a second death must permanently replace the first recovery.

## comment 5550134530 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/195#issuecomment-5550134530

Created: 2026-08-10T08:33:57Z; updated: 2026-08-10T08:33:57Z

Exact metadata: [source record](sources/comment-5550134530-e9c3c62d23c6ba700abe2620abf80adcb45fb065b15ae766f3bf57bac461cf5d.json).

I had an activated campfire but I got some message saying I got respawned where I stood. I don't understand, if I ask for "respawn at nearest activated campsite" then surely that means that as long as there is a nonzero amount of them there will always be a closest one? Therefore it should never happen to me, regardless of where I am.
