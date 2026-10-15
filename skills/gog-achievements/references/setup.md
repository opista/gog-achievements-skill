# Setup, updates, and recovery

Run `scripts/runtime.py` with Python 3.9 or later. It uses only the standard library. Resolve it from this installed skill folder; do not assume the working directory is the skill directory. On Windows, use `py -3` if `python3` is unavailable.

## Commands

| Command | Effect |
| --- | --- |
| `ensure` | Resolve an approved CLI, or install the pinned release if none is available. Check updates at most once per 24 hours. |
| `ensure --offline` | Use a local approved CLI only. No download or update check. |
| `check-updates` | Force a public release check. Never install. |
| `update` | Install a newer approved release into the skill-managed directory. Never update an external CLI. |
| `config --auto-update on` | Enable automatic installation of approved releases for the managed copy. |
| `config --auto-update off` | Disable automatic installation. This is the default. |

All commands accept `--data-dir PATH`. All except `config` accept `--cli PATH`. `GOG_ACHIEVEMENTS_CLI` is an alternative explicit CLI path. Relative explicit paths resolve against the caller's working directory. Supply paths as separate process arguments; do not construct a shell command from user data.

Selection order is: explicit CLI path, an active managed copy, a compatible CLI on PATH, then a pinned managed download. An invalid explicit path fails rather than falling back to another installation. The helper runs only JSON help and public update checks. It never reads GOG credentials, signs in, or sends an achievement write.

Success uses `{ "ok": true, "data": { ... } }`. Failure uses `{ "ok": false, "error": { "code": "...", "message": "..." } }`. Runtime errors exit 1. These are helper errors, not the CLI's exit codes.

The helper stores private files under:

- Mac: `~/Library/Application Support/GogAchievementsSkill`.
- Windows: `%LOCALAPPDATA%\GogAchievementsSkill`.

`runtime/<version>/<target>/` holds complete CLI packages. `active.json` selects the active version. `preferences.json` holds only the automatic-update preference. `update-check.json` caches public metadata. `queues/` holds user queue files. Credentials stay in the CLI's existing Mac Keychain or Windows DPAPI store and can be reused if the OS permits access.

The skill-managed runtime stays outside the installed skill. A read-only skill directory is supported. Removing or updating the skill does not delete queues or credentials. Keep the complete CLI package intact, especially the private runtime and native helper in Intel Mac packages.

## Updates

The checked-in `cli-releases.json` is the approval list, including exact archive hashes for all supported targets. A version is not approved merely because it has a compatible-looking number. The helper reports newer upstream versions without downloading them unless the version is approved. Install or update the skill to obtain a new approval list.

The preferred CLI is v0.5.0, with lock and mixed-action queue support. Existing approved v0.4.0 installations remain usable for reads and unlocks. Updating the skill does not itself update an active CLI when automatic installation is off. If a requested lock needs an update, explain the requirement and use `update` within the user's update authorization before preparing its queue. For an external CLI, use its original update method. Never pass lock options to v0.4.0.

Automatic installation is off until the user asks to enable it. It runs only during `ensure`, only for a managed copy, and before the agent prepares its review. There are no background tasks. The helper downloads a pinned version directly, instead of invoking `self update --yes`, because that CLI command can select a different latest release between check and installation. External installations must use their own update method.

Old managed versions stay in place. To roll back, close any running CLI operation, choose an approved older package, then pass its absolute executable path with `--cli`. Review the resulting CLI version before reusing a queue. Do not delete queues or the GOG credential store to repair a runtime problem.

## Errors

| Code | Action |
| --- | --- |
| `UNSUPPORTED_PLATFORM` | Use a local supported Mac or Windows host. |
| `CLI_NOT_FOUND` | Leave offline mode, supply an approved local CLI, or allow GitHub access. |
| `CLI_VERSION_UNAPPROVED` | Use an approved CLI version or update the skill after that release is validated. |
| `CLI_CONTRACT_INVALID` | Stop. The executable did not match the approved JSON command contract. |
| `EXTERNAL_CLI` | Update through the installation's original method; the helper will not alter it. |
| `UPDATE_NOT_APPROVED` | A newer upstream release needs validation and a skill update. Keep using the current approved CLI. |
| `RUNTIME_BUSY` | Another setup operation may be running. Inspect `.runtime.lock`; remove it only after confirming its process has stopped. |
| `DOWNLOAD_FAILED` | Check GitHub/network access and TLS trust. Never disable TLS checks. |
| `CHECKSUM_MISMATCH` | Stop. Do not run or extract the archive. |
| `PACKAGE_INVALID` | Keep the previous runtime. Inspect the damaged package; do not delete unrelated files. |
| `INVALID_STATE` | Inspect the named runtime metadata file. Do not clear the GOG credential store. |

A failed automatic check or update is returned in `data.update` while an available approved CLI remains usable. An explicit `check-updates` or `update` returns its error. The active pointer changes only after a complete package passes verification. No retry is needed for GOG writes because this helper makes none.
