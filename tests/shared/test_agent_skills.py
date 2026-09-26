"""Agent skills stay findable by every AI, not just the ones that load skills.

AGENTS.md holds the always-on rules and an index of skills under
.agents/skills/. An AI that does not discover skills on its own only finds one
through that index, so every skill must be listed there, and every listed path
must exist.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def test_every_skill_has_name_and_description():
    for path in skill_files():
        text = path.read_text(encoding="utf-8")
        match = re.match(r"---\n(.*?)\n---\n", text, re.S)
        assert match, f"{path} needs YAML frontmatter"
        fields = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
        assert fields.get("name", "").strip() == path.parent.name, f"{path}: name must match its folder"
        assert fields.get("description", "").strip(), f"{path}: description is what makes an AI pick the skill"


def test_agents_md_indexes_every_skill():
    listed = set(re.findall(r"\.agents/skills/([\w-]+)/SKILL\.md", AGENTS))
    present = {p.parent.name for p in skill_files()}
    assert listed == present, f"unlisted: {sorted(present - listed)}; missing: {sorted(listed - present)}"
