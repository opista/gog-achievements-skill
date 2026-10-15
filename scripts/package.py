#!/usr/bin/env python3
"""Build a portable skill ZIP without downloads or user runtime data."""

import argparse
import json
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/gog-achievements"
FILES = (
    "SKILL.md", "LICENSE.txt", "cli-releases.json", "agents/openai.yaml",
    "scripts/runtime.py", "references/cli.md", "references/setup.md",
)


def build(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(FILES):
            source = SKILL / relative
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing regular skill file: " + relative)
            entry = zipfile.ZipInfo(SKILL.name + "/" + relative, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (stat.S_IFREG | (0o755 if relative.endswith(".py") else 0o644)) << 16
            archive.writestr(entry, source.read_bytes())
    return destination.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "dist/gog-achievements-skill.zip"))
    options = parser.parse_args()
    print(json.dumps({"archive": str(build(options.output))}))
