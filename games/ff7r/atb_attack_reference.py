"""Empirical attack-generated ATB constraints for FF7R issue #425.

A detailed public Remake mechanics guide records total ATB gain for individual
standard/unique attack sequences, including separate non-staggered/staggered
values. Those samples are enough to reject several overly-simple models, but not
to prove the game's internal per-event formula.

Source table:
https://gamefaqs.gamespot.com/ps5/314233-final-fantasy-vii-remake-intergrade/faqs/78875/gameplay-mechanics

No gameplay behavior is implemented from these samples.
"""

from __future__ import annotations

from typing import Any


# Values are total internal ATB points reported for one execution of the named
# attack sequence. `power` and `hits` are included only to test simple hypotheses.
ATTACK_ATB_SAMPLES = (
    {
        "character": "Cloud",
        "move": "Punisher Mode Combo",
        "power": 500,
        "hits": 9,
        "normalGain": 558,
        "staggeredGain": 1050,
    },
    {
        "character": "Cloud",
        "move": "Punisher Mode Sidewinder",
        "power": 140,
        "hits": 5,
        "normalGain": 220,
        "staggeredGain": 390,
    },
    {
        "character": "Cloud",
        "move": "Punisher Mode Crush",
        "power": 60,
        "hits": 2,
        "normalGain": 50,
        "staggeredGain": 100,
    },
    {
        "character": "Tifa",
        "move": "Whirling Uppercut",
        "power": 108,
        "hits": 1,
        "normalGain": 400,
        "staggeredGain": 500,
    },
    {
        "character": "Tifa",
        "move": "Omnistrike",
        "power": 370,
        "hits": 1,
        "normalGain": 50,
        "staggeredGain": 100,
    },
    {
        "character": "Tifa",
        "move": "Rise and Fall",
        "power": 390,
        "hits": 4,
        "normalGain": 110,
        "staggeredGain": 450,
    },
)


def analyze_attack_atb_reference() -> dict[str, Any]:
    """Turn public samples into explicit hypothesis rejections, not a formula."""
    rows = []
    for sample in ATTACK_ATB_SAMPLES:
        row = dict(sample)
        row["normalGainPerHit"] = sample["normalGain"] / sample["hits"]
        row["staggeredGainPerHit"] = sample["staggeredGain"] / sample["hits"]
        row["staggerMultiplier"] = sample["staggeredGain"] / sample["normalGain"]
        row["normalGainPerPower"] = sample["normalGain"] / sample["power"]
        rows.append(row)

    normal_per_hit = {round(row["normalGainPerHit"], 9) for row in rows}
    stagger_multipliers = {round(row["staggerMultiplier"], 9) for row in rows}

    # The two one-hit Tifa unique attacks are a particularly clean rejection of
    # damage-scaled ATB: the much lower-power Whirling Uppercut gains 8x as much
    # normal-state ATB as Omnistrike.
    whirling = next(row for row in rows if row["move"] == "Whirling Uppercut")
    omnistrike = next(row for row in rows if row["move"] == "Omnistrike")
    lower_power_gains_more = bool(
        whirling["power"] < omnistrike["power"]
        and whirling["normalGain"] > omnistrike["normalGain"]
    )

    return {
        "exactAttackFormulaValidated": False,
        "samples": rows,
        "constraints": {
            "singleGlobalPerHitConstantRejected": len(normal_per_hit) > 1,
            "damageProportionalModelRejected": lower_power_gains_more,
            "singleGlobalStaggerMultiplierRejected": len(stagger_multipliers) > 1,
            "moveSpecificValuesRequiredBySamples": True,
            "perHitVsPerAttackEventStillUnresolved": True,
            "runtimeEventGranularityStillUnresolved": True,
        },
        "cleanCounterexample": {
            "lowerPowerMove": whirling["move"],
            "lowerPower": whirling["power"],
            "lowerPowerNormalGain": whirling["normalGain"],
            "higherPowerMove": omnistrike["move"],
            "higherPower": omnistrike["power"],
            "higherPowerNormalGain": omnistrike["normalGain"],
        },
        "notes": [
            "The samples reject a single global ATB-per-hit constant because total gain divided by hit count differs materially by attack sequence.",
            "The samples reject simple damage/power proportionality: Whirling Uppercut has much lower listed power than Omnistrike while generating far more ATB.",
            "The staggered/non-staggered ratios are move-dependent, so a single global stagger multiplier cannot explain these samples.",
            "These observations are compatible with move-specific authored ATB values, per-hit event values, or a more complex dispatch table. They do not establish which representation the installed game uses.",
            "The native HitSuccess versus PerHitSuccess correlation probe remains the authoritative path for deciding event granularity before implementing the tweak.",
        ],
    }
