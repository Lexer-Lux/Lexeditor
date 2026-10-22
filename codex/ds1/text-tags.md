# DS1 FMG text tags

Measured by read-only inspection of the installed Remastered text: every
`<?...?>` code in `msg/ENGLISH/item.msgbnd.dcx` (31,840 strings) and
`msg/ENGLISH/menu.msgbnd.dcx` (14,935 strings): 873 distinct tags.
Substitution semantics cross-checked against the
[SoulsSpeedruns character-name notes](https://soulsspeedruns.com/darksouls/character-name).

## Shape

A tag is `<?name?>` or, for the lookups, `<?name@id?>`. The game replaces
it when the text renders: a glyph, a name, a number, or another string.
Lookups nest: a looked-up string may hold tags of its own
(`System_message_win32_` id 18300 is button tags; `Dialogue_` id 1 is just
`<?sysmsg@1?>`). A trailing `@` with no id changes nothing.

## Lookups (verified against the installed tables)

| Tag | Reads | Example |
| --- | --- | --- |
| `<?sysmsg@ID?>` | `System_message_win32_.fmg` entry ID | `<?sysmsg@1?>` renders `OK` |
| `<?platmsg@ID?>` | `System_specific_tags_win32_.fmg` entry ID: the platform's own button for the action | `<?platmsg@10002?>` renders the attack button |
| `<?gdsparam@ID?>` | A value the running event supplies (probably; no FMG holds these ids) | `Phantom <?deadName?>` style event text; `<?gdsparam@1020?> shattered, becoming <?gdsparam@1000?>` |
| `<?goodsNameId@ID?>` | An item's name by goods id (probably; used where an event names a reward) | shops and event text |

## Names (multiplayer and events)

`deadName`, `joinName`, `hostName`, `leaveName` (phantoms:
`Phantom <?joinName?> summoned`), `coliseumDeadNameA`–`F`,
`enemyPC1`–`6`, `mvpName`, `onLineID`, `rankPlayerName1`–`10`,
`warpName1`–`11`, `mapName`, `itemName`, `itemNum`,
`itemNameBeforeForge` / `itemNameAfterForge`
(`Reinforce <?itemNameBeforeForge?> into <?itemNameAfterForge?>?`),
`pcName`.

## Numbers (character, gear, wallet)

`souls` (current soul count), `demandSoul` (`Purchase for
<?demandSoul?> souls?`), `sellSouls`, `getSoulNum`,
`evntAcquittalPrice`, `pcLevel`, `pcHP`, `pcMP`, `pcMaxHp`,
`pcMaxMp`, `pcMaxStamina`, stats (`pcForce`, `pcStrength`,
`pcDexter`, `pcIntellect`, `pcWill`, `pcVitality`, `pcEndur`,
`pcDurability`, `pcLuck`, `pcHeroic`, `pcItemOccur`),
`equipWeight`, `maxEquipWeight`, `pcOath`, `playTime`, `ptTime`,
`pcPlayTime`. Weapon and armor figures: `wpPhysicalAtk`,
`wpMagicAtk`, `wpFireAtk`, `wpThunderboltAtk`, `wpCriticalAtk`,
`wpShotRange`, `wpHitRes`, `defPhysical`, `defMagic`, `defFire`,
`defThunderbolt`, `defCut`, `defStab`, `defBlunt`, `defSAToughness`,
`resistPoison`, `resistBleeding`, `resistPlague`, `resistCurse`,
`reqPcStrength` and kin, `costMP`, `weight`, `duration`, each with
a `*Total` worn-gear form, a `forged*` post-reinforcement form, an
`lvUp*` after-level form, and `itemList*1`–`5` / `forgedItemList*1`–`5`
comparison-row forms.

## Buttons and keys (key guides, help, descriptions)

One tag per control, rendering its glyph: `attackR`, `attackL`,
`subAttackR`, `subAttackL`, `selectUD`, `selectLR`, `selectAll`,
`selectL`, `selectR`, `conclusion` (confirm), `cancel`,
`commando` (toggle display), `viewChange`, `HelpMenu`,
`spin`, `spinLR`, `spinReset`, `startMenuSwitch`, `startItem`,
`startAction`, `slectMenuSwitch`, `pageUp`, `pageDown`, `scrollUp`,
`scrollDown`, `categoryChangeL`, `categoryChangeR`, `changeArmR`,
`changeArmL`, `changeEquStyle`, `changeMagic`, `chamgeItem`,
`shortCutL`, `shortCutR`, `cameraMove`, `playerMove`, `mouseMove`,
`keyboardEnter`, `keyboardEsc`, `keyGuide`, `keyCategory`,
`keyController`, `key1`–`10`, `keyAction1`–`10`, `keyDefault1`–`10`,
`selectGesture`, `openGesture`, `dush` (dash), `optCameraSpeed`,
`optBGMVol` and the rest of the `opt*` settings values.
Vanilla keeps the developers' typos (`slectMenuSwitch`,
`chamgeItem`, `dush`): the names are literal, so copy them exactly.

## Soapstone words

`bmsg` (the chosen word), `upr` / `low` (its position):
`<?bmsg?> ahead <?upr?>`, `Be wary of <?bmsg?> <?low?>`.

## Menu chrome

`menuTitle`, `title`, `titleName`, `message`, `messageList1`–`5`,
`messageListMap1`–`5`, `lineHelp`, `actionHelp`, `itemDetail`,
`itemLineMsg`, `itemListName1`–`5` and the other `itemList*1`–`5`
columns, `magicListName1`–`5` and kin, `loadHintCaption`,
`loadHintName`, `eval`, `evalPlus`, `evalMinus`, `systemDlgButton01`–`06`,
`rank*`, `match*`, `networkValue01`–`05`, `multiPlayNum`,
`miracleSlotNum`, `magicSlotNum`, `magicCount`, `magicMaxCount`,
`curMagicSlotNum`, `equipMagicInfo1`–`16`, `inventoryNum0`–`3`,
`repositoryNum0`–`3`, `registerItemNum`, `removeMagic`,
`remainSec`, `saveDataSize`, `dataSize`, `pcenvValue01`–`14` and
`pcenvInitValue01`–`14`, `pcenvTimer1`, `pmOptions*`, `reqGender`,
`reqSlot`, `wpType`, `wpAtkType`.
