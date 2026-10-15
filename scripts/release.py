#!/usr/bin/env python3
"""Build and verify versioned skill release assets using only local files."""

import argparse
import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


def release_version(tag, root=ROOT):
    root = Path(root)
    version = (root / "version.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version) or tag != "v" + version:
        raise ValueError("The release tag must match version.txt.")
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))
    source = (root / "skills/gog-achievements/SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", source, re.S)
    skill_version = re.search(r'^  version: "([^"]+)"(?:\s+#.*)?$', frontmatter.group(1), re.M) if frontmatter else None
    if not skill_version or skill_version.group(1) != version or manifest.get(".") != version:
        raise ValueError("The skill, version file, and Release Please manifest must agree.")
    return version


def asset_names(version):
    archive = "gog-achievements-skill-" + version + ".zip"
    return archive, archive + ".sha256"


def verify(tag, directory, root=ROOT):
    root, directory = Path(root), Path(directory)
    version = release_version(tag, root)
    archive_name, checksum_name = asset_names(version)
    if sorted(path.name for path in directory.iterdir()) != sorted([archive_name, checksum_name]):
        raise ValueError("A release must contain exactly its versioned ZIP and checksum.")
    archive, checksum = directory / archive_name, directory / checksum_name
    for path in (archive, checksum):
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Release assets must be nonempty regular files.")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksum.read_text(encoding="utf-8") != digest + "  " + archive_name + "\n":
        raise ValueError("The release archive does not match its SHA-256 checksum.")
    skill = root / "skills/gog-achievements"
    expected = sorted("gog-achievements/" + name for name in package.FILES)
    with zipfile.ZipFile(archive) as bundle:
        if sorted(bundle.namelist()) != expected:
            raise ValueError("The release archive must contain exactly the portable skill files.")
        for name in package.FILES:
            source = skill / name
            if source.is_symlink() or not source.is_file() or bundle.read("gog-achievements/" + name) != source.read_bytes():
                raise ValueError("Release archive contents must match the tagged source: " + name)
    return {"version": version, "archive": str(archive.resolve()), "checksum": str(checksum.resolve())}


def build(tag, directory, root=ROOT):
    version = release_version(tag, root)
    directory = Path(directory)
    archive_name, checksum_name = asset_names(version)
    if directory.exists() and any(path.name not in (archive_name, checksum_name) for path in directory.iterdir()):
        raise ValueError("Build release assets in a directory without unrelated files.")
    for name in (archive_name, checksum_name):
        path = directory / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Release outputs must be regular files.")
    archive = package.build(directory / archive_name, Path(root) / "skills/gog-achievements")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with (directory / checksum_name).open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(digest + "  " + archive_name + "\n")
    return verify(tag, directory, root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--directory", default=str(ROOT / "dist/release"))
    options = parser.parse_args()
    print(json.dumps((build if options.command == "build" else verify)(options.tag, options.directory)))
