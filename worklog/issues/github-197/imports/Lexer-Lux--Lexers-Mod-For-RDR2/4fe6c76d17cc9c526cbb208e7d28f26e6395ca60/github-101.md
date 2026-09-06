# GitHub #101 — Oleander poisoning

The requested behavior was already implemented in the combined runtime source
when this migrated issue was audited. No second controller was added.

The implementation watches an actual running item interaction and requires a
matching inventory-count decrease within three seconds. This prevents merely
discarding or losing an item from being treated as consumption. The exact
records are:

- `CONSUMABLE_HERB_OLEANDER_SAGE` — activates Toxic.
- `CONSUMABLE_MEDICINE` — Health Cure; clears Toxic.
- `CONSUMABLE_MEDICINE_USED` — Opened Health Cure; clears Toxic.
- `CONSUMABLE_POTENT_MEDICINE` — Potent Health Cure; clears Toxic.
- `CONSUMABLE_SPECIAL_MEDICINE_CRAFTED` — Special Health Cure; clears Toxic.

Toxic sets Rockstar's `SA_POISONED` ped attribute (attribute 11) to 100 and
starts status icon 5 (`STATUS_SNAKE_VENOM` / Toxic). Clearing it resets the
attribute and stops that icon. Each transition is written to
`GameplayTweaks.toxicity.ini`; startup reloads the state, restores the attribute,
and starts the icon again. Consuming Oleander while already Toxic deliberately
leaves the same single active state in place rather than stacking independent
timers. The per-frame guard restores attribute 11 if the engine clears it while
the persisted state remains active.

Static audit:
`python tools/reverse-engineering/verify_oleander_poisoning_issue_101.py`.

Runtime acceptance after integration confirms the installed combined ASI:

- Eat Oleander Sage and confirm Toxic plus its status icon appear.
- Restart the game and confirm both state and icon return.
- Separately repeat poisoning and consume each of the four cure variants; each
  must clear Toxic and remove the icon.
- Eat Oleander again while already Toxic; it must remain one active condition,
  without duplicate icons or an unintended stacked duration.
- Dropping/discarding Oleander without eating it must not activate Toxic.

The separate outer-Health damage behavior and its timing belong to the Toxic
damage feature, not this issue's activation/cure contract.
