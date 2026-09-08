"""One-shot guarded integration of the central FF8 Formulae Rework contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one integration seam, found {count}")
    return text.replace(old, new, 1)


def patch_settings() -> None:
    path = ROOT / "games/ff8/gameplay_settings.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from . import healing_rework\n",
        "from . import healing_rework\nfrom . import formulae_rework\n",
        "formulae contract import",
    )
    text = replace_once(
        text,
        '    # The complete Formulae Rework is not implemented. Old files can contain\n'
        '    # its short-lived key, but loading it must not arm a hidden partial patch.\n'
        '    # Every visible Tweak keeps its stored value.\n'
        '    formulae_rework = False\n',
        '    # A formula description is not an implementation. Keep the owning toggle\n'
        '    # off until every row in the central Formulae Rework contract has a real\n'
        '    # guarded runtime component.\n'
        '    if not formulae_rework.available():\n'
        '        formulae_rework = False\n',
        "load availability gate",
    )
    text = replace_once(
        text,
        '        "formulaeRework": formulae_rework,\n'
        '        "formulaeReworkAvailable": False,\n',
        '        "formulaeRework": formulae_rework,\n'
        '        "formulaeReworkAvailable": formulae_rework.available(),\n'
        '        "formulaeReworkFormulas": formulae_rework.rows(),\n',
        "load formula inventory",
    )
    text = replace_once(
        text,
        '    if formulae_rework:\n'
        '        raise ValueError("Formulae Rework is not available")\n',
        '    if formulae_rework and not formulae_rework.available():\n'
        '        missing = ", ".join(formulae_rework.incomplete_ids())\n'
        '        raise ValueError(f"Formulae Rework is not available; incomplete: {missing}")\n',
        "save availability gate",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_editor() -> None:
    path = ROOT / "games/ff8/editor.html"
    text = path.read_text(encoding="utf-8")
    old = '''    // The stat rework, written out beside the vanilla rules so the two can be
    // compared. Vanilla text is only shown where it has been transcribed from
    // the game; the rest is marked rather than guessed at.
    const reworkCard=(title,rework,vanilla)=>el("section",{class:"formula-card formula-rework"},
      el("h2",{},title),
      el("h3",{class:"formula-subheading"},"REWORKED"),
      el("div",{class:"formula-expression"},rework),
      el("h3",{class:"formula-subheading"},"VANILLA"),
      el("div",{class:"formula-expression formula-vanilla"},vanilla));
    const master=el("section",{class:"formula-rework-master"},el("h2",{},"FORMULAE REWORK"),el("label",{class:"formula-rework-toggle"},el("span",{},"Use Lexer's reworked battle formulae"),formulaeRework),el("p",{},"This one mod-owned formula set includes full attacker LUCK in physical accuracy and spell power × MAG healing. The formula cards below define the complete requested rework."));
    const rework=[
      reworkCard("MELEE DAMAGE (REWORK)",
        "DAMAGE = (attacker STR + weapon STR bonus) × weapon power, then a % reduction from the target's VIT",
        "STR = min(255, attacker STR + weapon STR bonus); DAMAGE = floor(POWER × floor((265 − VIT) × (STR + floor(STR² / 16)) / 256) / 16) × RANDOM / 256"),
      reworkCard("MAGIC DAMAGE (REWORK)",
        "DAMAGE = spell power × attacker MAG, then a % reduction from the target's SPR",
        "FF8_EN.exe Damage_ComputeMagicAndGF at 0x491AD0: BASE = trunc((265 − target SPR) × (spell power + caster MAG) / 4); SCALED = trunc(spell power × BASE / 256); ROLLED = trunc(random[240..272] × SCALED / 256). The game then halves ROLLED for a monster caster, Shell, and Defend in that order; applies ELEMENTAL = trunc(ROLLED × (900 − target elemental defence) / 100); treats a negative result as healing; and caps the final magnitude at 9,999."),
      reworkCard("STATUS INFLICTION (REWORK)",
        "CHANCE % = spell power + attacker MAG − target SPR, then the vanilla status-defence rules",
        "FF8_EN.exe Battle_ApplyStatusWithResistRoll at 0x48F9F0: CHANCE = status accuracy + trunc(attacker stat / 4) − trunc(target stat / 4) − target status resistance. Physical branches use STR and VIT; magical and GF branches use MAG and SPR. A status already present, or resistance of 200 or more, fails first. Accuracy 255 then guarantees success. Otherwise CHANCE ≤ 0 fails; accuracy 250..254 succeeds without a random roll when CHANCE is positive; all other values succeed when trunc(CHANCE × 255 / 100) ≥ random[0..255]."),
      reworkCard("SPELL HEALING (REWORK)",
        "HEALING = spell power × attacker MAG",
        "FF8_EN.exe Damage_ComputeCurativeMagic at 0x493280: HALF = trunc((spell power + caster MAG) / 2); HEALING = trunc(spell power × random[240..272] × HALF / 256). Shell halves the result. Zombie reverses the restorative sign so the same amount becomes damage. The routine then applies the spell's cure statuses unconditionally; status accuracy is not read on this path. This routine has no formula-result clamp; later battle HP handling applies the returned signed amount."),
    ];
'''
    new = '''    // The backend owns the complete requested inventory and each row's runtime
    // status. A formula cannot disappear from this page merely because its native
    // implementation is unfinished.
    const formulaRows=settings.formulaeReworkFormulas||[];
    const reworkCard=formula=>el("section",{class:"formula-card formula-rework","data-formula-id":formula.id},
      el("h2",{},`${String(formula.name||formula.id).toUpperCase()} · ${formula.status==="implemented"?"IMPLEMENTED":"INCOMPLETE"}`),
      el("h3",{class:"formula-subheading"},"REWORKED"),
      el("div",{class:"formula-expression"},formula.replacement||"Not specified"),
      el("h3",{class:"formula-subheading"},"VANILLA"),
      el("div",{class:"formula-expression formula-vanilla"},formula.vanilla||"Not documented"),
      formula.blocker?el("p",{class:"readonly-note"},`INCOMPLETE: ${formula.blocker}`):null);
    const implementedCount=formulaRows.filter(formula=>formula.status==="implemented").length;
    const master=el("section",{class:"formula-rework-master"},el("h2",{},"FORMULAE REWORK"),el("label",{class:"formula-rework-toggle"},el("span",{},"Use Lexer's reworked battle formulae"),formulaeRework),el("p",{},`${implementedCount}/${formulaRows.length} requested runtime formulae are implemented. The owning toggle remains unavailable until every listed formula has a guarded game patch.`));
    const rework=formulaRows.map(reworkCard);
'''
    text = replace_once(text, old, new, "formula inventory UI")
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    patch_settings()
    patch_editor()
    print("Applied FF8 Formulae Rework contract integration")
