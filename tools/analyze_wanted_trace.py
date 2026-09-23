"""Summarize wanted-system trace runs from GameplayTweaks.log (#149).

Reads the subsystem "wanted" lines the trace module emits (see
C:/RDR2Mod/GameplayTweaks/modules/wanted_system.cpp) and prints one row per
observed state signature: first/last elapsed_ms, duration, and the
parole-relevant columns (wanted_level, seconds_since_seen, radius,
origin_distance, visual_dark_red). F8 VISUAL_MARK lines delimit the visible
dark-red windows. Pure stdin/stdout; no game needed.
"""
import re
import sys

SAMPLE = re.compile(
    r"^(?P<ms>\d+)\s+pos=(?P<pos>\S+)\s+law_incident=(?P<law>\d)\s+"
    r"wanted_score=(?P<score>-?\d+)\s+wanted_level=(?P<level>\d+)\s+"
    r"hud_crime=(?P<crime>\S+)\s+dispatch=(?P<dispatch>\S+)\s+"
    r"witnesses=(?P<wit>\d)\s+pending_witnesses=(?P<pwit>\d)\s+"
    r"investigators=(?P<inv>\d)\s+any_law_investigating=(?P<anylaw>\d)\s+"
    r"seconds_since_seen=(?P<seen>\S+)\s+radius=(?P<radius>\S+)\s+"
    r"origin_distance=(?P<dist>\S+)\s+visual_dark_red=(?P<dark>\d)"
)
MARK = re.compile(r"^(?P<ms>\d+)\s+VISUAL_MARK\s+dark_red=(?P<dark>[01])")


def summarize(lines):
    """Fold sample lines into state-duration rows. Returns (rows, marks)."""
    rows = []
    marks = []
    current = None
    for raw in lines:
        line = raw.strip()
        mark = MARK.match(line)
        if mark:
            marks.append((int(mark.group("ms")), int(mark.group("dark"))))
            continue
        sample = SAMPLE.match(line)
        if not sample:
            continue
        ms = int(sample.group("ms"))
        sig = (
            sample.group("law"), sample.group("score"), sample.group("level"),
            sample.group("crime"), sample.group("dispatch"),
            sample.group("wit"), sample.group("pwit"),
            sample.group("inv"), sample.group("anylaw"),
        )
        if current is None or current["sig"] != sig:
            if current is not None:
                current["last_ms"] = prev_ms
                current["last_seen"] = prev_seen
                current["last_radius"] = prev_radius
                current["last_dist"] = prev_dist
                rows.append(current)
            current = {
                "sig": sig, "first_ms": ms,
                "level": sample.group("level"),
                "dark": sample.group("dark"),
            }
        prev_ms = ms
        prev_seen = sample.group("seen")
        prev_radius = sample.group("radius")
        prev_dist = sample.group("dist")
    if current is not None:
        current["last_ms"] = prev_ms
        current["last_seen"] = prev_seen
        current["last_radius"] = prev_radius
        current["last_dist"] = prev_dist
        rows.append(current)
    return rows, marks


def report(rows, marks):
    out = []
    for row in rows:
        duration = row["last_ms"] - row["first_ms"]
        out.append(
            f"level={row['level']} dark={row['dark']} "
            f"first={row['first_ms']}ms last={row['last_ms']}ms "
            f"duration={duration}ms seen={row['last_seen']} "
            f"radius={row['last_radius']} dist={row['last_dist']}"
        )
    for ms, dark in marks:
        out.append(f"mark@{ms}ms dark_red={dark}")
    return "\n".join(out)


def main():
    rows, marks = summarize(sys.stdin)
    print(report(rows, marks))


if __name__ == "__main__":
    main()
