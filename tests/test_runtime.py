import argparse
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime", ROOT / "skills/gog-achievements/scripts/runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def help_data(version="0.4.0"):
    return {"name": "gog-achievements", "version": version, "common_flags": ["--json"],
            "commands": [{"command": name, "flags": sorted(flags)} for name, flags in runtime.REQUIRED_COMMANDS.items()]}


def package_bytes(version="0.4.0", target="windows-x64", extra=None):
    name = "gog-achievements-" + version + "-" + target
    metadata = {"version": version, "platform": "darwin" if target.startswith("macos") else "win32",
                "architecture": target.split("-")[1], "runtime_included": True, "native_helper_included": True,
                "layout": "native_launcher_with_private_runtime" if target == "macos-x64" else "single_executable"}
    files = {runtime.executable_name(target): b"fixture executable", "build.json": json.dumps(metadata).encode(),
             "README.md": b"fixture docs", "LICENSE": b"fixture license", "THIRD_PARTY_NOTICES.md": b"fixture notices",
             "licenses/NODE-LICENSE.txt": b"fixture runtime license"}
    if target == "macos-x64":
        files.update({"lib/node": b"fixture node", "lib/main.cjs": b"fixture script", "native/bin/gog-login": b"fixture helper"})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            entry = zipfile.ZipInfo(name + "/" + path)
            entry.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(entry, contents)
        for entry, contents in extra or []:
            archive.writestr(entry, contents)
    return output.getvalue()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.lock = runtime.release_lock()

    def options(self, command="ensure", **changes):
        values = {"command": command, "data_dir": str(self.root), "cli": None, "offline": False, "auto_update": "off"}
        values.update(changes)
        return argparse.Namespace(**values)

    def execute(self, options, executable=None, version="0.4.0", managed=True, latest="0.4.0"):
        executable = executable or self.root / "fixture-cli"
        response = {"current_version": version, "latest_version": latest}
        with mock.patch.object(runtime, "host_target", return_value="windows-x64"), \
                mock.patch.object(runtime, "release_lock", return_value=self.lock), \
                mock.patch.object(runtime, "locate", return_value=(executable, version, managed)), \
                mock.patch.object(runtime, "call_cli", return_value=response):
            return runtime.execute(options)

    def extract(self, data, target="windows-x64"):
        archive = self.root / "release.zip"
        archive.write_bytes(data)
        destination = self.root / "package"
        runtime.extract_package(archive, destination, "gog-achievements-0.4.0-" + target, target)
        return destination

    def test_approved_release_covers_exactly_four_targets(self):
        self.assertEqual(set(self.lock["releases"]["0.4.0"]), runtime.TARGETS)

    def test_probe_checks_capabilities_not_only_version(self):
        data = help_data()
        data["commands"] = [item for item in data["commands"] if item["command"] != "queue apply"]
        with mock.patch.object(runtime, "call_cli", return_value=data):
            with self.assertRaisesRegex(runtime.RuntimeErrorDetail, "missing required"):
                runtime.probe(Path("fixture"), self.lock)

    def test_probe_rejects_unapproved_version(self):
        with mock.patch.object(runtime, "call_cli", return_value=help_data("0.5.0")):
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.probe(Path("fixture"), self.lock)
        self.assertEqual(caught.exception.code, "CLI_VERSION_UNAPPROVED")

    def test_process_arguments_are_separate_and_never_use_shell(self):
        response = subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "data": help_data()}), "")
        with mock.patch.object(runtime.subprocess, "run", return_value=response) as execute:
            runtime.call_cli(Path("folder with spaces/cli"), ["--help"])
        self.assertEqual(execute.call_args.args[0], [str(Path("folder with spaces/cli")), "--help", "--json"])
        self.assertNotIn("shell", execute.call_args.kwargs)
        self.assertEqual(execute.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_invalid_process_output_does_not_leak_stderr(self):
        response = subprocess.CompletedProcess([], 7, "not json", "secret callback fixture")
        with mock.patch.object(runtime.subprocess, "run", return_value=response):
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.call_cli(Path("fixture"), ["--help"])
        self.assertNotIn("secret", str(caught.exception))

    def test_valid_windows_package(self):
        package = self.extract(package_bytes())
        runtime.validate_package(package, "0.4.0", "windows-x64")

    @unittest.skipIf(os.name == "nt", "POSIX executable bits are checked on Mac/Linux")
    def test_intel_mac_package_keeps_private_runtime(self):
        package = self.extract(package_bytes(target="macos-x64"), "macos-x64")
        runtime.validate_package(package, "0.4.0", "macos-x64")
        self.assertTrue((package / "lib/node").is_file())
        self.assertTrue((package / "native/bin/gog-login").stat().st_mode & 0o111)

    def test_package_metadata_must_match_target(self):
        package = self.extract(package_bytes())
        with self.assertRaises(runtime.RuntimeErrorDetail):
            runtime.validate_package(package, "0.4.0", "windows-arm64")

    def test_unsafe_archive_paths_are_rejected_before_extraction(self):
        root = "gog-achievements-0.4.0-windows-x64/"
        for path in [root + "../outside", "/absolute", root + "licenses/../../outside", root + "licenses\\outside",
                     root + "licenses/C:/file", root + "licenses/CON.txt", root + "licenses/file. ",
                     root + "licenses//file", root + "licenses/\x00file", root + "unknown"]:
            with self.subTest(path=path):
                with self.assertRaises(runtime.RuntimeErrorDetail):
                    self.extract(package_bytes(extra=[(path, b"bad")]))
                self.assertFalse((self.root / "package").exists())
                self.assertFalse((self.root / "outside").exists())

    def test_archive_links_and_case_collisions_are_rejected(self):
        root = "gog-achievements-0.4.0-windows-x64/"
        link = zipfile.ZipInfo(root + "licenses/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for extra in [[(link, b"../../outside")], [(root + "readme.md", b"collision")],
                      [(root + "licenses/file", b"file"), (root + "licenses/file/child", b"child")]]:
            with self.subTest(extra=extra):
                with self.assertRaises(runtime.RuntimeErrorDetail):
                    self.extract(package_bytes(extra=extra))
                self.assertFalse((self.root / "package").exists())

    def test_pinned_hash_is_checked_before_extraction(self):
        class Response(io.BytesIO):
            pass
        opener = mock.Mock()
        opener.open.return_value = Response(b"changed archive")
        with mock.patch.object(runtime.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.download("https://github.com/fixture", self.root / "download.zip", "0" * 64)
        self.assertEqual(caught.exception.code, "CHECKSUM_MISMATCH")

    def test_failed_install_does_not_change_active_version(self):
        runtime.write_json(self.root / "active.json", {"version": "0.4.0"})
        with mock.patch.object(runtime, "download", side_effect=runtime.RuntimeErrorDetail("DOWNLOAD_FAILED", "fixture")):
            with self.assertRaises(runtime.RuntimeErrorDetail):
                runtime.install(self.root, self.lock, "0.4.0", "windows-x64")
        self.assertEqual(runtime.read_json(self.root / "active.json")["version"], "0.4.0")
        self.assertFalse((self.root / "runtime").exists())
        self.assertEqual(list(self.root.glob(".download-*")), [])

    def test_failed_probe_does_not_activate_download(self):
        def downloaded(url, destination, expected):
            destination.write_bytes(package_bytes())
        with mock.patch.object(runtime, "download", side_effect=downloaded), \
                mock.patch.object(runtime, "probe", side_effect=runtime.RuntimeErrorDetail("CLI_CONTRACT_INVALID", "fixture")):
            with self.assertRaises(runtime.RuntimeErrorDetail):
                runtime.install(self.root, self.lock, "0.4.0", "windows-x64")
        self.assertFalse((self.root / "active.json").exists())
        self.assertFalse((self.root / "runtime/0.4.0/windows-x64").exists())

    def test_explicit_bad_cli_does_not_fall_back(self):
        with mock.patch.object(runtime, "probe", side_effect=runtime.RuntimeErrorDetail("CLI_VERSION_UNAPPROVED", "fixture")), \
                mock.patch.object(runtime, "install") as install:
            with self.assertRaises(runtime.RuntimeErrorDetail):
                runtime.locate(self.root, self.lock, "windows-x64", str(self.root / "bad"), False)
        install.assert_not_called()

    def test_offline_missing_cli_does_not_download(self):
        with mock.patch.object(runtime.shutil, "which", return_value=None), mock.patch.object(runtime, "install") as install:
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.locate(self.root, self.lock, "windows-x64", None, True)
        self.assertEqual(caught.exception.code, "CLI_NOT_FOUND")
        install.assert_not_called()

    def test_offline_ensure_does_not_check_updates(self):
        with mock.patch.object(runtime, "update_check") as check:
            result = self.execute(self.options(offline=True))
        check.assert_not_called()
        self.assertEqual(result["update"]["status"], "offline")

    def test_automatic_update_defaults_off(self):
        result = self.execute(self.options(), latest="0.5.0")
        self.assertFalse(result["automatic_updates"])
        self.assertTrue(result["update"]["skill_update_required"])
        self.assertFalse(result["updated"])

    def test_daily_check_cache_is_used_then_expires(self):
        with mock.patch.object(runtime, "call_cli", return_value={"current_version": "0.4.0", "latest_version": "0.4.0"}) as call, \
                mock.patch.object(runtime.time, "time", return_value=100000) as clock:
            runtime.update_check(self.root, Path("fixture"), "0.4.0", self.lock)
            clock.return_value = 100100
            cached = runtime.update_check(self.root, Path("fixture"), "0.4.0", self.lock)
            self.assertTrue(cached["cached"])
            self.assertEqual(call.call_count, 1)
            clock.return_value = 100000 + runtime.DAY
            runtime.update_check(self.root, Path("fixture"), "0.4.0", self.lock)
            self.assertEqual(call.call_count, 2)

    def test_failed_automatic_check_leaves_cli_usable_and_caches_failure(self):
        with mock.patch.object(runtime, "update_check", side_effect=runtime.RuntimeErrorDetail("CLI_CONTRACT_INVALID", "offline")):
            result = self.execute(self.options())
        self.assertEqual(result["version"], "0.4.0")
        self.assertEqual(result["update"]["status"], "unavailable")
        result = self.execute(self.options())
        self.assertTrue(result["update"]["cached"])

    def test_explicit_update_never_changes_external_cli(self):
        with mock.patch.object(runtime, "install") as install:
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                self.execute(self.options("update"), managed=False)
        self.assertEqual(caught.exception.code, "EXTERNAL_CLI")
        install.assert_not_called()

    def test_update_check_never_installs_even_when_auto_update_enabled(self):
        runtime.write_json(self.root / "preferences.json", {"automatic_updates": True})
        self.lock["releases"]["0.4.1"] = self.lock["releases"]["0.4.0"]
        with mock.patch.object(runtime, "install") as install:
            result = self.execute(self.options("check-updates"), latest="0.4.1")
        install.assert_not_called()
        self.assertFalse(result["updated"])

    def test_update_check_cannot_bootstrap_missing_cli(self):
        with mock.patch.object(runtime, "host_target", return_value="windows-x64"), \
                mock.patch.object(runtime.shutil, "which", return_value=None), mock.patch.object(runtime, "install") as install:
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.execute(self.options("check-updates"))
        self.assertEqual(caught.exception.code, "CLI_NOT_FOUND")
        install.assert_not_called()

    def test_auto_update_rejects_new_unapproved_version(self):
        runtime.write_json(self.root / "preferences.json", {"automatic_updates": True})
        with mock.patch.object(runtime, "install") as install:
            result = self.execute(self.options(), latest="0.5.0")
        install.assert_not_called()
        self.assertEqual(result["version"], "0.4.0")
        self.assertEqual(result["update"]["code"], "UPDATE_NOT_APPROVED")

    def test_auto_update_activates_only_approved_managed_package(self):
        runtime.write_json(self.root / "preferences.json", {"automatic_updates": True})
        self.lock["releases"]["0.4.1"] = self.lock["releases"]["0.4.0"]
        new_cli = self.root / "runtime/0.4.1/windows-x64/gog-achievements.exe"
        with mock.patch.object(runtime, "install", return_value=new_cli) as install:
            result = self.execute(self.options(), latest="0.4.1")
        install.assert_called_once_with(self.root, self.lock, "0.4.1", "windows-x64")
        self.assertTrue(result["updated"])
        self.assertEqual(result["previous_version"], "0.4.0")
        self.assertEqual(runtime.read_json(self.root / "active.json")["version"], "0.4.1")

    def test_lock_does_not_remove_another_process_lock(self):
        (self.root / ".runtime.lock").write_text('{"pid": 123}', encoding="utf-8")
        with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
            with runtime.runtime_lock(self.root):
                self.fail("Lock must not be acquired")
        self.assertEqual(caught.exception.code, "RUNTIME_BUSY")
        self.assertTrue((self.root / ".runtime.lock").exists())

    def test_runtime_data_cannot_be_inside_skill(self):
        with self.assertRaises(runtime.RuntimeErrorDetail):
            runtime.data_directory(str(runtime.SKILL / "runtime"))

    def test_runtime_lock_is_removed_after_failure(self):
        with self.assertRaises(ValueError):
            with runtime.runtime_lock(self.root):
                raise ValueError("fixture")
        self.assertFalse((self.root / ".runtime.lock").exists())

    def test_linux_is_rejected_before_creating_runtime_files(self):
        with mock.patch.object(runtime.sys, "platform", "linux"):
            with self.assertRaises(runtime.RuntimeErrorDetail) as caught:
                runtime.execute(self.options())
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PLATFORM")
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
