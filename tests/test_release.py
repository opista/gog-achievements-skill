import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_skill", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        skill = self.root / "skills/gog-achievements"
        shutil.copytree(ROOT / "skills/gog-achievements", skill, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("version.txt", ".release-please-manifest.json"):
            shutil.copy2(ROOT / name, self.root / name)
        self.version = (self.root / "version.txt").read_text(encoding="utf-8").strip()
        self.tag = "v" + self.version
        self.directory = self.root / "assets"

    def build(self):
        result = release.build(self.tag, self.directory, self.root)
        return Path(result["archive"]), Path(result["checksum"])

    def checksum(self, archive, checksum):
        with checksum.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")

    def test_build_and_verify_complete_release(self):
        archive, checksum = self.build()
        self.assertEqual(archive.name, "gog-achievements-skill-" + self.version + ".zip")
        self.assertEqual(release.verify(self.tag, self.directory, self.root)["version"], self.version)
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(bundle.read("gog-achievements/SKILL.md"), (self.root / "skills/gog-achievements/SKILL.md").read_bytes())
        self.assertIn(archive.name, checksum.read_text(encoding="utf-8"))

    def test_tag_and_all_version_sources_must_agree(self):
        with self.assertRaisesRegex(ValueError, "tag"):
            release.build("v99.0.0", self.directory, self.root)
        manifest = self.root / ".release-please-manifest.json"
        manifest.write_text(json.dumps({".": "99.0.0"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must agree"):
            release.build(self.tag, self.directory, self.root)
        manifest.write_text(json.dumps({".": self.version}), encoding="utf-8")
        skill = self.root / "skills/gog-achievements/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace('version: "' + self.version + '"', 'version: "99.0.0"', 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must agree"):
            release.build(self.tag, self.directory, self.root)
        self.assertFalse(self.directory.exists())

    def test_missing_or_extra_release_assets_are_rejected(self):
        archive, checksum = self.build()
        checksum.unlink()
        with self.assertRaisesRegex(ValueError, "exactly"):
            release.verify(self.tag, self.directory, self.root)
        self.checksum(archive, checksum)
        (self.directory / "old.zip").write_bytes(b"old")
        with self.assertRaisesRegex(ValueError, "exactly"):
            release.verify(self.tag, self.directory, self.root)

    def test_corrupt_archive_or_checksum_is_rejected(self):
        archive, checksum = self.build()
        original = archive.read_bytes()
        archive.write_bytes(original + b"modified")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            release.verify(self.tag, self.directory, self.root)
        archive.write_bytes(original)
        checksum.write_text("0" * 64 + "  " + archive.name + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            release.verify(self.tag, self.directory, self.root)

    def test_recomputed_checksum_does_not_hide_changed_source(self):
        archive, checksum = self.build()
        with zipfile.ZipFile(archive) as bundle:
            files = {name: bundle.read(name) for name in bundle.namelist()}
        files["gog-achievements/scripts/runtime.py"] = b"print('unexpected code')\n"
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, contents in files.items():
                bundle.writestr(name, contents)
        self.checksum(archive, checksum)
        with self.assertRaisesRegex(ValueError, "tagged source"):
            release.verify(self.tag, self.directory, self.root)

    def test_extra_zip_payload_is_rejected_even_with_valid_checksum(self):
        archive, checksum = self.build()
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("gog-achievements/queues/private.json", b"{}")
        self.checksum(archive, checksum)
        with self.assertRaisesRegex(ValueError, "portable skill files"):
            release.verify(self.tag, self.directory, self.root)

    def test_build_preserves_unrelated_files(self):
        self.directory.mkdir(parents=True)
        existing = self.directory / "unrelated.txt"
        existing.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unrelated"):
            release.build(self.tag, self.directory, self.root)
        self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(list(self.directory.iterdir()), [existing])


if __name__ == "__main__":
    unittest.main()
