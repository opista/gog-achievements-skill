import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_skill", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_portable_archive_is_complete_and_excludes_runtime_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = package.build(Path(temporary) / "skill.zip")
            with zipfile.ZipFile(path) as archive:
                files = set(archive.namelist())
                self.assertEqual(files, {"gog-achievements/" + name for name in package.FILES})
                self.assertIn(b"MIT License", archive.read("gog-achievements/LICENSE.txt"))
                self.assertNotIn(b"/Users/beau", archive.read("gog-achievements/SKILL.md"))
                self.assertTrue(all("__pycache__" not in name and "queues/" not in name for name in files))

    def test_same_sources_make_identical_archive_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = package.build(Path(temporary) / "first.zip").read_bytes()
            second = package.build(Path(temporary) / "second.zip").read_bytes()
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
