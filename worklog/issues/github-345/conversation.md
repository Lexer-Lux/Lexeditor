# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356490118 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/345

Created: 2026-08-24T17:07:41Z; updated: 2026-09-05T07:41:06Z

Exact metadata: [source record](sources/issue-5356490118-9157a3999d51ef8418c102800b93ee3e163b49e889dd6f49f6104107cbfa2f4f.json).

Change the cutscene-skip key from Backspace to E. Change the campsite Travel to key from Return to T. Update the active input binding and the displayed prompt from resolved RDR control data or script paths. Do not remap unrelated uses of E, T, Backspace, or Return. Acceptance: E skips a skippable cutscene, Backspace no longer does; T selects Travel to at camp, Return no longer does; other menu confirmation and interaction controls retain their normal behavior.

## issue 5356490118 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/345

Created: 2026-08-24T17:07:41Z; updated: 2026-09-06T12:39:10Z

Exact metadata: [source record](sources/issue-5356490118-a91964fad5d9b01de6137637b47f754cc72844dfe5b0b0bf25f0fb369d198e90.json).

Change the actual actions and displayed prompts: E for cutscene Skip, T for campsite Travel. Leave unrelated confirmation controls alone.

**Status: Incomplete.** The camp test still used Return. A prompt-only change was correctly rejected; the real camp action still needs a safe script-level repair. No new retest is ready.

## issue 5356490118 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/345

Created: 2026-08-24T17:07:41Z; updated: 2026-09-06T12:39:10Z

Exact metadata: [source record](sources/issue-5356490118-df302d1dfb407fecaeeb722034433123b3ea5b6a68b740b6bfaa3da9d92f63a3.json).

Change the actual actions and displayed prompts: E for cutscene Skip, T for campsite Travel. Leave unrelated confirmation controls alone.

**Status: Incomplete.** The camp test still used Return. A prompt-only change was correctly rejected; the real camp action still needs a safe script-level repair. No new retest is ready.

## comment 5550351844 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/345#issuecomment-5550351844

Created: 2026-08-27T05:50:36Z; updated: 2026-08-27T05:50:36Z

Exact metadata: [source record](sources/comment-5550351844-c7341cafb9f5ceaf50f75567fc512041f104abb8d690ae19f214718d1bbe5032.json).

Runtime check failed: the campsite Travel to action and prompt still use Return. They must both use T without changing ordinary menu acceptance.

## comment 5550351856 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/345#issuecomment-5550351856

Created: 2026-08-27T06:17:37Z; updated: 2026-08-27T06:17:37Z

Exact metadata: [source record](sources/comment-5550351856-5a5eebd5250f01a9be11342ae6d18ed784a095851059fae3b4cd03d6436daa4e.json).

I did not install a prompt-only T remap. The camp action is private to player.sco, while RedHook can change only its text; a global accept remap or synthetic Return would also affect unrelated controls. This still needs a supported player-script override that preserves the camp state and cleanup.
