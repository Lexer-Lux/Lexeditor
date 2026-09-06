# GitHub issue #176 — vanilla animal InfoBox through binoculars

## 2026-08-11 recurrence audit before implementation

- **Primary evidence/reference:** Lexer reports that the vanilla lower-right
  animal name/quality panel is absent through binoculars. Story
  `short_update.c` is authoritative: event 30/type 35 toggles
  `Global_1935496.f_23` and calls `_SET_SHOW_INFO_CARD`; the update then requires
  `GET_IS_PLAYER_UI_PROMPT_ACTIVE(player, 35)`, launches `SHOP_BROWSING` entry
  `-649639953` for horses or `-1645363952` for other animals, and populates the
  `InfoBox` data binding. A custom map-blip name is not this feature.
- **Sanctioned path:** preserve Story's event, global, app, compendium, and data
  binding ownership. The mod may stop suppressing the exact vanilla prompt/input
  path and observe its native/app/data-binding readbacks. It must not write
  `Global_1935496.f_23`, launch a replacement shop page, or manufacture a custom
  lower-right card.
- **Execution proof:** while a valid animal is selected through binoculars, log
  the type-35 player UI-prompt state, `SHOP_BROWSING` active state, and `InfoBox`
  container/visibility readback on transitions. These records distinguish
  `not requested`, `requested but app inactive`, and `app active with no data`.
- **Player-visible acceptance:** the real Rockstar lower-right animal panel
  appears through the custom binocular entry path and shows the animal name,
  quality/stars, and description exactly as vanilla does. It closes normally
  when the target or binocular view is lost.
- **Cadence:** input release is frame-local only while an eligible animal is the
  active binocular target. UI diagnostics are transition-based with a bounded
  heartbeat. No per-frame app launch, global write, or data-binding rebuild is
  allowed.

## 2026-08-11 source repair

The installed log contains zero `put-away prompt suppressed` records during
many completed quick-binocular sessions. That is a positive failure result:
the exact `INPUT_CAMERA_PUT_AWAY` registry handle was never observed, so
`putAwayPromptObserved` never became true. The alleged one-frame fallback
therefore called `HUD::_UIPROMPT_DISABLE_PROMPTS_THIS_FRAME()` on every active
binocular frame. This blanketed Rockstar's animal Study/Info prompt together
with the unwanted put-away prompt.

The broad fallback is removed. Quick binoculars now suppress only the exact
`INPUT_CAMERA_PUT_AWAY` control action and, if its source-backed registry entry
exists, that one valid prompt handle. A missing handle authorizes no HUD-wide
mutation. The native binocular task, optics-ready gate, movement bridge, zoom,
and draw/stow path are unchanged.

The active owner also disabled `INPUT_INTERACT_LOCKON`, `INPUT_CONTEXT`, and
`INPUT_CONTEXT_SECONDARY`. Recon now returns only those three contextual
actions, in input groups 0 and 2, while the authored binocular scope is active
and a live nonhuman ped is the nearest valid reticle target. This lets Story
rebuild the animal context path after the HUD-wide suppression is gone.

The contextual bridge does not run during the draw, for human targets, or
outside binocular mode. Already-tagged animals remain eligible for the InfoBox
even though they are excluded from a new recon dwell.

The bridge does not call `_SET_SHOW_INFO_CARD`, write
`Global_1935496.f_23`, launch `SHOP_BROWSING`, or create any `InfoBox` binding.
Those remain owned by `short_update`. A 100 ms diagnostic read records
`GET_IS_PLAYER_UI_PROMPT_ACTIVE(player, 35)`, `SHOP_BROWSING` activity, and
validity of the existing `InfoBox` container on transitions, with a two-second
eligible-target heartbeat. This separates input/prompt failure from app launch
or data-binding failure in the next run.

`python tools/reverse-engineering/verify_recon_animal_infobox_issue_176.py`
and `verify_binocular_quick_access_issue_4.py` passed. Runtime acceptance
remains the real lower-right Rockstar panel through the quick binocular path,
including name, quality/stars, and description, plus normal close behavior
after the target or scope is lost. The exact Backspace prompt must also remain
absent without suppressing unrelated prompts.
