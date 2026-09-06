# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356295820 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/150

Created: 2026-08-06T02:34:39Z; updated: 2026-09-05T06:57:36Z

Exact metadata: [source record](sources/issue-5356295820-1615caa5624b1c7d5b3dd729e751d7316f039248c3b2e6cab5de3b3623f7a1d0.json).

Should I have a tab to edit enemy stats? Enemy AI? Does each enemy even have their own stats? There are like 50 different files editing different things on the global and group level and I'm so confused help
190. ENEMY STATS REWORK — get that tab up and running. Maybe it's just the
     bullet speed change, but I'm standing around with this one O'Driscoll
     shooting at me and he can't even hit me from a few feet away if I just walk
     constantly. Not even move, just walk. First slice of Lexer-Lux/Lexeditor#263.
     STATUS: the tab is up. New Mobs tab, split Humans / Animals, with two
     views — Combat profiles (how well a faction shoots) and Health archetypes
     (how much it takes to kill). Everything on it is editable and saving was
     tested end to end.
     IT IS NOT THE BULLET SPEED. The O'Driscolls have their own combat profile
     and their accuracy in it is 0.6, against your 0.1 — he is authored to be a
     good shot. What guts him is a separate global rule that halves an enemy's
     accuracy while its target moves sideways, and it only looks at DIRECTION,
     never speed, so your walk is worth exactly as much as a sprint. The one
     thing that normally claws that back needs you to stand still for six
     seconds, so walking constantly pins him at half forever. Both dials are in
     the editor now.
     THE MOBS TAB NOW HAS TWO HALVES, as you asked: "Mobs" lists every ped
     model with a dropdown to pick its archetype, and "Archetypes" is the plain
     list of stat tables to edit directly.
     ONE-TIME PROBE IS BUILT AND INSTALLED. The game never tells us in any file
     which mob uses which stat record, so a throwaway probe asks the running
     game instead: it quietly spawns each of the 253 known mobs out of sight,
     reads its health, and deletes it. You do not have to meet anything or
     press anything — load a save, watch the counter on screen, and it fills
     the Observed HP column in. Delete the probe afterwards.
     HEADS UP ON THE DROPDOWN: picking an archetype writes your choice to a
     list, but nothing reads that list yet — the mod-side piece that applies it
     when a mob spawns is not built. So assignments do nothing in game until I
     build that. Say the word and it is next.
     LEFT: the actual rebalance. Nothing was retuned — the numbers were only
     exposed. Raising the global movement rule fixes walk-to-win for every
     faction at once; raising one gang's own accuracy only papers over it.
     ALSO WORTH KNOWING: the enemy difficulty names are a lie. MEDIUM, HARD,
     HARDER and HARDEST are identical, and EASY is tougher than all of them.
     Only EASIEST is genuinely weaker. Difficulty is not coming from health.

## issue 5356295820 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/150

Created: 2026-08-06T02:34:39Z; updated: 2026-09-06T13:31:16Z

Exact metadata: [source record](sources/issue-5356295820-23339a84d6307e1569d4a92f38919a621c1cf36105529f20b8fe2674768f0934.json).

**Actionable — validation remains.** Mobs exposes separate combat, accuracy, tactics and health data; there is no universal per-model stat record. The reported walking-target misses match a directional accuracy penalty that does not distinguish walking from sprinting.

A controlled stationary/walk/sprint comparison is still needed before proposing rebalance values. Asking whether you want more work is not a blocker. Model assignments must not pretend to apply unsupported changes.

## comment 5550123298 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/150#issuecomment-5550123298

Created: 2026-08-06T03:57:20Z; updated: 2026-08-06T03:57:20Z

Exact metadata: [source record](sources/comment-5550123298-4ecf9addf1045c48300b884df408b5f1fdeff8fc0059a5fe49bb62ec0d6088fb.json).

Research result: enemies do not have one unified per-model stat record. Shooting profiles live in `combatbehaviour.meta`, situational modifiers in `pedaccuracy.meta`, tactics in `combatstyles.meta`, health/knockout values in shared `pedhealth.meta` archetypes, and perception/noise elsewhere. The walking-target miss problem is not bullet speed: the default lateral-movement rule halves accuracy without checking speed, so walking earns the same penalty as sprinting, while recovery requires six seconds of loitering. The current profile/archetype split is the right authoritative UI. Model rows may show observed HP and explicit runtime overrides, but must not claim a static mapping the files do not contain. Next proof: controlled stationary/walk/sprint/lateral/away trials; rebalance values are a later design choice.

## comment 5550123311 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/150#issuecomment-5550123311

Created: 2026-08-06T07:44:14Z; updated: 2026-08-06T07:45:40Z

Exact metadata: [source record](sources/comment-5550123311-0522d02d9c3f81e9096606cab83aaa8dd5dc6b62b3cac96c4ea4a20d0e582a9d.json).

Research complete.

The extracted stack confirms there is no unified per-ped-model “enemy stats” record:

- `combatbehaviour.meta` contains 40 named combat profiles; for example `GANG_ODRISCOLLS` has `WeaponAccuracy=0.6` and `CA_Professional`.
- `pedaccuracy.meta` contains only `companion` and `Default`. In `Default`, lateral movement multiplies accuracy by `0.5`, movement away by `0.4`, and the recovery ramp requires 6 seconds loitering. Those rules test direction, not walk/sprint speed, so continuous sideways walking permanently receives the full penalty.
- `pedhealth.meta` contains shared health archetypes. Exhaustive searches find no general model-to-health-archetype table; only mission scripts selectively call `_SET_PED_HEALTH_CONFIG`, so a model assignment must be described as a runtime override, not vanilla data.
- `combatstyles.meta` is tactics, separate from accuracy and health.

Conclusion: the current editor design is already the correct one: expose Combat profiles, contextual Accuracy modifiers, Combat styles, and Health archetypes as separate authoritative layers. A model list may show runtime-observed HP/candidate archetypes, but cannot truthfully claim a static vanilla assignment. No additional editor implementation is authorized by this exploratory issue.

Human follow-up, if desired: controlled stationary/walk/sprint tests are gameplay validation of a later rebalance choice, not missing research.
