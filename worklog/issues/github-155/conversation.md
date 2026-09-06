# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356296830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/155

Created: 2026-08-06T02:39:27Z; updated: 2026-09-05T06:57:51Z

Exact metadata: [source record](sources/issue-5356296830-71c9ce281a7fba0c4458b7ca2a5e031ae6647b9bcf04918df6136934a07ea2fe.json).

Wait I Remember being told that fists already KO'ed? Then being told not? Does KO'ing even exist in game? What's the diff? I'm so confused
27.  FISTS KNOCK OUT, NEVER KILL — ordinary punches should knock NPCs out, not     kill them. Needs research on knockout thresholds, recovery, kicking and     stomping, melee damage and mission compatibility. Reference: Rededrunk's     Ultimate Combat Overhaul (Nexus 5731).
     I'm surprised fists didn't knock out to begin with. Then how DID you knock
     out in vanilla? Anyway, just tell me what fields to edit in the Weapons tab
     under Unarmed and I'll do it myself. ~Lex

## issue 5356296830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/155

Created: 2026-08-06T02:39:27Z; updated: 2026-09-06T12:54:23Z

Exact metadata: [source record](sources/issue-5356296830-f239a5193a7746d6d8c98edcac34ebba8c46d611b286a0389490e2cb83865c50.json).

**Status: The requested explanation is still outstanding.** Knockout exists, but lowering Unarmed damage alone does not guarantee nonlethal punches. Action-specific damage/reactions and shared health/knockout rules both matter.

Trace and explain the actual decision in plain language before proposing settings or a never-kill change. This remains exploratory; no new combat behavior is ready.

## issue 5356296830 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/155

Created: 2026-08-06T02:39:27Z; updated: 2026-09-06T13:54:35Z

Exact metadata: [source record](sources/issue-5356296830-a9edf56224910c129f791f25d6298d95230404f9ba4dcd0cd0261f7fb693e4c5.json).

**Status: The requested explanation is still outstanding.** Knockout exists, but lowering Unarmed damage alone does not guarantee nonlethal punches. Action-specific damage/reactions and shared health/knockout rules both matter.

Trace and explain the actual decision in plain language before proposing settings or a never-kill change. This remains exploratory; no new combat behavior is ready.

## comment 5550124595 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/155#issuecomment-5550124595

Created: 2026-08-06T03:57:22Z; updated: 2026-08-06T03:57:22Z

Exact metadata: [source record](sources/comment-5550124595-c3ea7c07221f339dab610a1b8106bbbe9aa7091381f4bec22bea1cef752b894c.json).

Knockout exists in vanilla, but no set of fields under Weapons → Unarmed guarantees it. `action/damages.meta` gives punch/kick/stomp/grapple actions Damage, Cost, and reaction attributes; many use `DRA_KNOCKOUT`, while some omit it or include fatal behavior. `pedhealth.meta` owns knockout thresholds, recovery health, and counts per shared archetype. Lowering unarmed weapon damage may reduce deaths but cannot define recovery or guarantee nonlethality. The editor needs an Action Damage surface distinct from Weapons, followed by logging of punches, kicks, stomps, finishers, grapples, and environmental impacts. A runtime fatal-damage guard may still be required for “never kill,” especially in missions.

## comment 5550124610 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/155#issuecomment-5550124610

Created: 2026-08-06T05:31:53Z; updated: 2026-08-06T05:31:53Z

Exact metadata: [source record](sources/comment-5550124610-2fa3739a68acf0907f01259177642a00ce005a776f5998066cb879b71de6f6c2.json).

i don't understand. so you're saying that its controlled by certain actions -- which i don't know, are those things under weapons or what -- having nonlethal flags? except then you're saying that the nonlethal flag doesn't actually make it nonlethal and it's a PROC based on damage?
do you understand what "exploratory" means? you're supposed to actually explain things to me please
