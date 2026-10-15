#!/usr/bin/env python3
"""Resolve and manage an approved CLI. Never access GOG credentials or writes."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPOSITORY = "opista/gog-achievements-cli"
TARGETS = {"macos-arm64", "macos-x64", "windows-arm64", "windows-x64"}
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
DAY = 24 * 60 * 60
ARCHIVE_LIMIT = 256 * 1024 * 1024
EXTRACT_LIMIT = 512 * 1024 * 1024
REQUIRED_COMMANDS = {
    "doctor": set(), "auth status": set(), "auth login": set(),
    "games list": {"search"}, "achievements list": {"game"},
    "queue create": {"file", "game", "achievement", "unlocked-at"},
    "queue add": {"file", "achievement", "unlocked-at"},
    "queue set-date": {"file", "achievement", "unlocked-at"},
    "queue show": {"file"}, "queue apply": {"file", "dry-run", "yes"},
    "self update": {"check"},
}


class RuntimeErrorDetail(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise RuntimeErrorDetail(code, message)


def read_json(path, default=None):
    try:
        require(path.stat().st_size <= 65536, "INVALID_STATE", "Metadata is too large: " + path.name)
        value = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(value, dict), "INVALID_STATE", "Expected an object: " + path.name)
        return value
    except FileNotFoundError:
        if default is not None:
            return default.copy()
        raise RuntimeErrorDetail("INVALID_STATE", "Missing metadata: " + path.name)
    except (OSError, ValueError, UnicodeError):
        raise RuntimeErrorDetail("INVALID_STATE", "Cannot read metadata: " + path.name) from None


def write_json(path, value):
    descriptor, name = tempfile.mkstemp(prefix=".metadata-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def release_lock():
    lock = read_json(SKILL / "cli-releases.json")
    releases = lock.get("releases")
    require(lock.get("schema_version") == 1 and lock.get("repository") == REPOSITORY
            and isinstance(releases, dict) and releases
            and lock.get("preferred_version") in releases,
            "INVALID_STATE", "The CLI release approval list is invalid.")
    for version, hashes in releases.items():
        require(VERSION.fullmatch(version) and isinstance(hashes, dict) and set(hashes) == TARGETS
                and all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
                        for value in hashes.values()),
                "INVALID_STATE", "A CLI release or archive hash is invalid.")
    require(lock["preferred_version"] == max(releases, key=version_key),
            "INVALID_STATE", "The preferred CLI must be the newest approved release.")
    return lock


def version_key(value):
    return tuple(int(part) for part in value.split("."))


def host_target():
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform)
    machine = platform.machine().lower()
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(machine)
    require(system and architecture, "UNSUPPORTED_PLATFORM", "Use a local ARM64 or x64 Mac or Windows host.")
    if system == "macos":
        version = platform.mac_ver()[0]
        require(version and tuple(map(int, version.split(".")[:2])) >= (13, 5),
                "UNSUPPORTED_PLATFORM", "macOS 13.5 or later is required.")
    else:
        require(sys.getwindowsversion().major >= 10, "UNSUPPORTED_PLATFORM", "Windows 10 or later is required.")
    return system + "-" + architecture


def data_directory(override=None):
    if override:
        root = Path(override).expanduser().resolve()
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "GogAchievementsSkill"
    else:
        local = os.environ.get("LOCALAPPDATA")
        require(local, "INVALID_STATE", "LOCALAPPDATA is not set. Supply --data-dir.")
        root = Path(local) / "GogAchievementsSkill"
    root = root.resolve()
    require(root != SKILL and SKILL not in root.parents, "INVALID_STATE", "Keep runtime data outside the installed skill.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / "queues").mkdir(exist_ok=True, mode=0o700)
    return root


@contextmanager
def runtime_lock(root):
    path = root / ".runtime.lock"
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeErrorDetail("RUNTIME_BUSY", "Another runtime operation may be active. Inspect .runtime.lock.") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump({"pid": os.getpid()}, output)
        yield
    finally:
        path.unlink()


def call_cli(executable, arguments):
    try:
        result = subprocess.run([str(executable)] + arguments + ["--json"],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                encoding="utf-8", timeout=20, check=False)
        envelope = json.loads(result.stdout)
        require(result.returncode == 0 and isinstance(envelope, dict) and envelope.get("ok") is True
                and isinstance(envelope.get("data"), dict),
                "CLI_CONTRACT_INVALID", "The CLI did not return a successful JSON object.")
        return envelope["data"]
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError):
        raise RuntimeErrorDetail("CLI_CONTRACT_INVALID", "Could not run the CLI JSON command.") from None


def probe(executable, lock, expected=None):
    data = call_cli(executable, ["--help"])
    version = data.get("version")
    require(isinstance(version, str) and version in lock["releases"],
            "CLI_VERSION_UNAPPROVED", "Use a CLI release approved by this installed skill.")
    commands = data.get("commands")
    require(data.get("name") == "gog-achievements" and isinstance(commands, list)
            and (expected is None or version == expected),
            "CLI_CONTRACT_INVALID", "The CLI identity or version does not match.")
    by_name = {item.get("command"): item for item in commands if isinstance(item, dict)}
    require(all(name in by_name and isinstance(by_name[name].get("flags"), list)
                and flags.issubset(by_name[name]["flags"])
                for name, flags in REQUIRED_COMMANDS.items()),
            "CLI_CONTRACT_INVALID", "The CLI is missing required JSON commands or options.")
    require("--json" in data.get("common_flags", []), "CLI_CONTRACT_INVALID", "The CLI does not declare JSON output.")
    return version


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        require(newurl.startswith("https://"), "DOWNLOAD_FAILED", "An insecure download redirect was rejected.")
        return super().redirect_request(request, response, code, message, headers, newurl)


def download(url, destination, expected_hash):
    started = time.monotonic()
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={"User-Agent": "gog-achievements-skill/0.1.0"})
    try:
        opener = urllib.request.build_opener(HTTPSRedirect())
        with opener.open(request, timeout=20) as response, destination.open("xb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= ARCHIVE_LIMIT and time.monotonic() - started <= 120,
                        "DOWNLOAD_FAILED", "The download exceeded its size or time limit.")
                digest.update(chunk)
                output.write(chunk)
    except (OSError, urllib.error.URLError):
        raise RuntimeErrorDetail("DOWNLOAD_FAILED", "Cannot download the approved GitHub release. Check network and TLS access.") from None
    require(digest.hexdigest() == expected_hash, "CHECKSUM_MISMATCH", "The archive does not match its pinned SHA-256 hash.")


def executable_name(target):
    return "gog-achievements.exe" if target.startswith("windows-") else "gog-achievements"


def extract_package(archive, destination, root_name, target):
    allowed = {executable_name(target), "build.json", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "licenses"}
    if target == "macos-x64":
        allowed.update({"lib", "native"})
    seen, entries, total = {}, [], 0
    try:
        with zipfile.ZipFile(archive) as zipped:
            require(len(zipped.infolist()) <= 1024, "PACKAGE_INVALID", "The archive has too many entries.")
            for entry in zipped.infolist():
                name = entry.filename
                directory = entry.is_dir()
                parts = name[:-1].split("/") if directory else name.split("/")
                mode = entry.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                require(entry.orig_filename == name and name and not re.search(r"[\\:\x00-\x1f\x7f-\x9f]", name)
                        and parts[0] == root_name
                        and all(part and part not in {".", ".."} and not re.search(r"[. ]$", part)
                                and not re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part, re.I)
                                for part in parts),
                        "PACKAGE_INVALID", "The archive contains an unsafe path.")
                parts = parts[1:]
                relative = "/".join(parts)
                metadata = bool(parts and parts[-1].startswith("._"))
                top = parts[0][2:] if metadata and len(parts) == 1 else (parts[0] if parts else None)
                key = unicodedata.normalize("NFC", relative).casefold()
                total += entry.file_size
                require((not parts and directory or top in allowed) and key not in seen
                        and file_type in {0, stat.S_IFDIR if directory else stat.S_IFREG}
                        and not entry.flag_bits & 1 and entry.compress_type in {0, 8}
                        and entry.file_size <= ARCHIVE_LIMIT
                        and entry.file_size <= max(1, entry.compress_size) * 1000
                        and total <= EXTRACT_LIMIT and (not directory or entry.file_size == 0),
                        "PACKAGE_INVALID", "The archive has duplicate, unsupported, or oversized entries.")
                seen[key] = directory
                entries.append((entry, parts, directory, metadata, mode))
            for entry, parts, directory, metadata, mode in entries:
                for depth in range(1, len(parts)):
                    key = unicodedata.normalize("NFC", "/".join(parts[:depth])).casefold()
                    require(seen.get(key) is not False, "PACKAGE_INVALID", "The archive has a file/directory conflict.")
            destination.mkdir(mode=0o700)
            for entry, parts, directory, metadata, mode in entries:
                if not parts or metadata:
                    continue
                path = destination.joinpath(*parts)
                if directory:
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(entry) as source, path.open("xb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                    path.chmod(0o755 if mode & 0o111 else 0o644)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
        raise RuntimeErrorDetail("PACKAGE_INVALID", "The CLI archive is invalid or incomplete.") from None


def validate_package(directory, version, target):
    metadata = read_json(directory / "build.json")
    expected = {
        "version": version,
        "platform": "darwin" if target.startswith("macos-") else "win32",
        "architecture": target.split("-")[1],
        "layout": "native_launcher_with_private_runtime" if target == "macos-x64" else "single_executable",
        "runtime_included": True, "native_helper_included": True,
    }
    require(all(metadata.get(key) == value for key, value in expected.items()),
            "PACKAGE_INVALID", "The CLI package does not match its version or target.")
    executable = executable_name(target)
    executables = {executable}
    required = {executable, "build.json", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/NODE-LICENSE.txt"}
    if target == "macos-x64":
        required.update({"lib/node", "lib/main.cjs", "native/bin/gog-login"})
        executables.update({"lib/node", "native/bin/gog-login"})
    for name in required:
        path = directory / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size > 0,
                "PACKAGE_INVALID", "The CLI package is missing a required regular file.")
        if target.startswith("macos-") and name in executables:
            require(path.stat().st_mode & 0o111, "PACKAGE_INVALID", "The CLI package is missing executable permission.")


def install(root, lock, version, target):
    destination = root / "runtime" / version / target
    if destination.exists():
        validate_package(destination, version, target)
        probe(destination / executable_name(target), lock, version)
        return destination / executable_name(target)
    require(version in lock["releases"], "CLI_VERSION_UNAPPROVED", "The requested CLI release is not approved.")
    root_name = "gog-achievements-" + version + "-" + target
    url = "https://github.com/" + REPOSITORY + "/releases/download/v" + version + "/" + root_name + ".zip"
    with tempfile.TemporaryDirectory(prefix=".download-", dir=str(root)) as temporary:
        staging = Path(temporary)
        download(url, staging / "release.zip", lock["releases"][version][target])
        package = staging / "package"
        extract_package(staging / "release.zip", package, root_name, target)
        validate_package(package, version, target)
        probe(package / executable_name(target), lock, version)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(package, destination)
    return destination / executable_name(target)


def locate(root, lock, target, explicit, offline):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path, probe(path, lock), False
    active = read_json(root / "active.json", {})
    if active:
        version = active.get("version")
        require(isinstance(version, str) and version in lock["releases"],
                "CLI_VERSION_UNAPPROVED", "The active managed CLI version is not approved.")
        path = root / "runtime" / version / target / executable_name(target)
        validate_package(path.parent, version, target)
        return path, probe(path, lock, version), True
    found = shutil.which("gog-achievements")
    if found:
        path = Path(found).resolve()
        try:
            return path, probe(path, lock), False
        except RuntimeErrorDetail as error:
            if error.code != "CLI_VERSION_UNAPPROVED":
                raise
    require(not offline, "CLI_NOT_FOUND", "No approved local CLI is available in offline mode.")
    version = lock["preferred_version"]
    path = install(root, lock, version, target)
    write_json(root / "active.json", {"version": version})
    return path, version, True


def update_check(root, executable, version, lock, force=False):
    cached = read_json(root / "update-check.json", {})
    checked_at = cached.get("checked_at")
    if (not force and cached.get("current_version") == version
            and isinstance(checked_at, (int, float)) and 0 <= time.time() - checked_at < DAY):
        require(isinstance(cached.get("result"), dict) and cached["result"].get("status") in {"checked", "unavailable"},
                "INVALID_STATE", "Invalid cached update result.")
        return dict(cached["result"], cached=True)
    data = call_cli(executable, ["self", "update", "--check"])
    latest = data.get("latest_version")
    require(data.get("current_version") == version and isinstance(latest, str) and VERSION.fullmatch(latest),
            "CLI_CONTRACT_INVALID", "The CLI update check returned invalid versions.")
    newer = version_key(latest) > version_key(version)
    result = {"status": "checked", "latest_version": latest, "update_available": newer,
              "approved": latest in lock["releases"],
              "skill_update_required": newer and latest not in lock["releases"]}
    write_json(root / "update-check.json", {"checked_at": time.time(), "current_version": version, "result": result})
    return result


def execute(options):
    target = host_target()
    lock = release_lock()
    root = data_directory(options.data_dir)
    with runtime_lock(root):
        preferences = read_json(root / "preferences.json", {"automatic_updates": False})
        require(type(preferences.get("automatic_updates")) is bool, "INVALID_STATE", "Invalid automatic-update preference.")
        if options.command == "config":
            preferences["automatic_updates"] = options.auto_update == "on"
            write_json(root / "preferences.json", preferences)
            return preferences
        explicit = options.cli or os.environ.get("GOG_ACHIEVEMENTS_CLI")
        path, version, managed = locate(root, lock, target, explicit, options.offline or options.command != "ensure")
        result = {"executable": str(path), "version": version, "managed": managed,
                  "queue_directory": str(root / "queues"), "automatic_updates": preferences["automatic_updates"],
                  "updated": False, "update": {"status": "offline"}}
        if options.command == "update":
            require(managed, "EXTERNAL_CLI", "Use the external CLI installation's own update method.")
        if not options.offline:
            try:
                result["update"] = update_check(root, path, version, lock, options.command != "ensure")
                update = result["update"]
                wants_update = options.command == "update" or options.command == "ensure" and preferences["automatic_updates"] and managed
                if wants_update and update.get("update_available", False):
                    require(update["approved"], "UPDATE_NOT_APPROVED", "Update the skill after the new CLI release is validated.")
                    latest = update["latest_version"]
                    path = install(root, lock, latest, target)
                    write_json(root / "active.json", {"version": latest})
                    result.update(executable=str(path), version=latest, previous_version=version, updated=True)
            except RuntimeErrorDetail as error:
                if options.command != "ensure":
                    raise
                result["update"] = {"status": "unavailable", "code": error.code, "message": str(error)}
                write_json(root / "update-check.json", {"checked_at": time.time(), "current_version": version,
                                                        "result": result["update"]})
        return result


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("ensure", "check-updates", "update", "config"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--data-dir")
        subparser.set_defaults(cli=None, offline=False)
        if command == "config":
            subparser.add_argument("--auto-update", choices=("on", "off"), required=True)
        else:
            subparser.add_argument("--cli")
            if command == "ensure":
                subparser.add_argument("--offline", action="store_true")
    options = parser.parse_args(arguments)
    try:
        result = {"ok": True, "data": execute(options)}
        status = 0
    except RuntimeErrorDetail as error:
        result = {"ok": False, "error": {"code": error.code, "message": str(error)}}
        status = 1
    except OSError:
        result = {"ok": False, "error": {"code": "IO_ERROR", "message": "Cannot access the runtime directory or files."}}
        status = 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return status


if __name__ == "__main__":
    sys.exit(main())
