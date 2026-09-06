# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356298892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165

Created: 2026-08-06T02:46:40Z; updated: 2026-09-05T06:58:20Z

Exact metadata: [source record](sources/issue-5356298892-d0347847ccc1651f614aa03de1d9fea950c15bdb7a0d6359b16098202ee28f74.json).

RECOVERABLE UNIQUE WEAPONS — every OTHER one-off weapon that can be lost
     for good after being thrown or dropped stays recoverable: if I lose one, it
     turns up in my WEAPON LOCKER AT CAMP for me to collect. It does not
     reappear in my hands.
     Covers the unique hatchets and tomahawks — Viking, Hewing, Double Bit,
     Double Bit Rusted, Hunter's, Hunter's Rusted — plus anything else loseable
     that turns up. Never duplicate one that still exists in inventory, on the
     horse, in the locker, or lying in the world. Preserve ordinary manual
     retrieval and mission behaviour.
     NOT BUILT AS SPECIFIED. What exists tracks first acquisition and waits for
     the world pickup to disappear — that groundwork is right — but then it
     gives the weapon straight back to me instead of putting it in the locker.
     The locker is the whole point and it is the missing half.
     Retest after #199 restores the thrown-weapon settings that were lost.


NOT LIKE the Lexer-Lux/Lexeditor#164 ! Not some magical thing that brings it back to you on the spot -- just lets you retrieve it from the locker like any other weapon.

## issue 5356298892 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165

Created: 2026-08-06T02:46:40Z; updated: 2026-09-06T13:31:19Z

Exact metadata: [source record](sources/issue-5356298892-35a384128feac828b23cf286829b373c798ecaf36563d210ffc1aa40d948a168.json).

**Actionable — requested locker integration is incomplete.** The installed workaround adds a named Recover action; it does not add the ordinary weapon-list entries you explicitly requested.

Lost unique hatchets/tomahawks must return through the camp locker, unequipped and without duplication. The native melee/throwable filter still needs a safe solution. No repeat acceptance request for the smaller workaround is pending.

## comment 5550126881 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126881

Created: 2026-08-06T08:09:01Z; updated: 2026-08-06T08:09:01Z

Exact metadata: [source record](sources/comment-5550126881-932e48ed8d03d75294086665bc51391b68f38f45b97accee0915de2cbd19878d.json).

Built successfully. Lost unique recovery now grants without equipping/duplicating, finds the exact ALL WEAPONS inventory GUID, clears Rockstar locker field 21, commits and reads it back, and rolls the grant back on any failure. Queued until RDR2 exits.

Queued ASI SHA-256: `5E08E021F25A1B0A597B350451514544086EE8898949E98608D0C8BAF05855CC`

## comment 5550126888 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126888

Created: 2026-08-06T08:16:12Z; updated: 2026-08-06T08:16:12Z

Exact metadata: [source record](sources/comment-5550126888-08271d0e261ec58197f86aa8acd4d96786296adcd514f983eb7034e35967345d.json).

Superseding combined build queued; includes locker-based unique recovery. It will install when RDR2 exits.

Queued ASI SHA-256: `9124F920A8A97381327D8FF1D2E01A0A3220A793EA9BE475BAF5D7198E9B225B`

## comment 5550126898 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126898

Created: 2026-08-06T12:06:16Z; updated: 2026-08-06T12:06:16Z

Exact metadata: [source record](sources/comment-5550126898-222bcb0223f520bf136d4e6724061c3a857334b205a37fd2fb4f9ebda5ba98fc.json).

i threw the viking hatchet into a tree and went back to camp. i don't see it in my weapons locker menu. in fact, i don't see any melee or throwable weapons in the weapons locker list at all.
am i missing something? How am i meant to recover theM?

## comment 5550126912 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126912

Created: 2026-08-06T13:00:41Z; updated: 2026-08-06T13:00:41Z

Exact metadata: [source record](sources/comment-5550126912-b4ea7943654e7b07fef95550dad8df29fd6dd8d1e9c3d31f1d3aa0d19c782051.json).

?

## comment 5550126928 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126928

Created: 2026-08-06T14:42:10Z; updated: 2026-08-06T14:42:10Z

Exact metadata: [source record](sources/comment-5550126928-365b6cca7ade082c97fa635873330765fa98dfebf18915d4ab097797f0951fde.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Lose a recoverable unique, wait at least 30 seconds, then use the weapon-locker recovery prompt and confirm the exact weapon returns.

## comment 5550126943 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126943

Created: 2026-08-10T09:21:31Z; updated: 2026-08-10T09:21:31Z

Exact metadata: [source record](sources/comment-5550126943-8e08dff7e88512462ecd3bd316c056f23e7919e3db3eb784b78fd61c1c5d04bd.json).

<img width="427" height="401" alt="Image" src="https://github.com/user-attachments/assets/4fe5ae3a-825f-4639-8280-70cad18fe8d4" />

Well I can't even access the locker anymore so you should probably fix that one first

## comment 5550126955 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126955

Created: 2026-08-10T12:42:54Z; updated: 2026-08-10T12:42:54Z

Exact metadata: [source record](sources/comment-5550126955-c7e191ce442d66cdf77fce8d90dd373cd3c805c17735ff794a0f487529642000.json).

Can you not just add the uniques themselves to the weapon locker menu so I can just grab them from there like any other weapon?

## comment 5550126964 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126964

Created: 2026-08-10T15:54:18Z; updated: 2026-08-10T15:54:18Z

Exact metadata: [source record](sources/comment-5550126964-60edf7bce496739855629290299a9c5c89da79fc1c6da74cb36c1f029ace6604.json).

Am I going to test this only to see no difference whatsoever and no uniques in my weapon locker and no reply or explanation whatsoever for you?

## comment 5550126972 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/165#issuecomment-5550126972

Created: 2026-08-10T16:39:34Z; updated: 2026-08-10T16:39:34Z

Exact metadata: [source record](sources/comment-5550126972-523bece8b59c94a9248b855fefa53c90754fb6065cb2409bf9fc50cb7dfc8607.json).

No—the test should not be “look through the normal locker list and hope something changed,” and I should have answered your question directly.

Rockstar's `weapon_locker` script rejects melee/throwable weapons **before** it checks the stored/in-locker state. That is why adding the unique hatchets as ordinary locker entries did not make them appear; worse, those hidden entries were part of the build that made the locker inaccessible. So I removed that mutation. Making them literal standard list rows would require replacing/patching Rockstar's locker UI filter, not merely adding the weapons.

What is installed now:
1. Losing a covered unique for 30 seconds records it as pending without giving it back or inserting a hidden melee entry.
2. The ordinary weapon locker must open normally first.
3. Once the actual `WEAPON_LOCKER` app is open, a named **Recover Viking Hatchet** (or the relevant unique) action appears there.
4. Completing it gives exactly one unequipped copy and clears pending only after ownership reads back.

Please first confirm the ordinary locker opens. With the already-lost Viking Hatchet pending, confirm that named recovery action appears inside it, returns one copy, and is gone after reopening. This is `test me` because that implementation is installed; if the ordinary locker or named action fails, it goes straight back to `actionable` with that exact failure—not another claim that a hidden inventory bit is success.
