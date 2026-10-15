#!/usr/bin/env python3
"""Validate portable skill metadata and local resource references."""

import importlib.util
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/gog-achievements"


def validate():
    source = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", source, re.S)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter.")
    metadata = yaml.safe_load(match.group(1))
    if metadata.get("name") != SKILL.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"]):
        raise ValueError("The skill name must match its folder.")
    description = metadata.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        raise ValueError("The skill needs a description of at most 1024 characters.")
    if len(source.splitlines()) > 500 or "[TODO:" in source:
        raise ValueError("Keep the skill concise and remove unfinished placeholders.")
    for markdown in SKILL.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
            if "://" in link or link.startswith("#"):
                continue
            target = (markdown.parent / link.split("#")[0]).resolve()
            if not target.is_file() or SKILL not in target.parents:
                raise ValueError("Missing or nonportable resource: " + link)
    interface = yaml.safe_load((SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))
    if "$gog-achievements" not in interface["interface"]["default_prompt"]:
        raise ValueError("The default prompt must name this skill.")
    if interface.get("policy", {}).get("allow_implicit_invocation") is not True:
        raise ValueError("Keep this skill available for contextual selection.")
    specification = importlib.util.spec_from_file_location("skill_runtime", SKILL / "scripts/runtime.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    lock = module.release_lock()
    if metadata["metadata"]["cli-release"] != lock["preferred_version"]:
        raise ValueError("Skill metadata and approved CLI release must agree.")
    if (SKILL / "LICENSE.txt").read_bytes() != (ROOT / "LICENSE").read_bytes():
        raise ValueError("The portable package must include the repository license.")
    return {"skill": metadata["name"], "preferred_cli": lock["preferred_version"], "valid": True}


if __name__ == "__main__":
    print(json.dumps(validate()))
