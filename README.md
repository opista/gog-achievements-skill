# GOG Achievements Skill

Find and restore GOG achievements you already earned, through a conversation with a local AI agent. This skill uses the [GOG Achievements CLI](https://github.com/opista/gog-achievements-cli). It can resolve game and achievement descriptions, show choices, collect unlock dates, and prepare a queue for review.

## Install

This is an [Agent Skills](https://agentskills.io/specification) repository. Copy `skills/gog-achievements` into your agent's skill directory. Keep the whole folder intact. For Codex, use `~/.agents/skills/gog-achievements` or a project `.agents/skills/gog-achievements` directory. The optional `agents/openai.yaml` adds Codex display metadata; the main workflow uses no vendor-specific tools.

The GitHub repository is private. Authenticate with GitHub before cloning or using a skill installer that reads it. Do not put a GitHub token in the skill, a command argument, or chat.

```sh
git clone git@github.com:opista/gog-achievements-skill.git
```

Use your agent's skill installer with this repository and the path `skills/gog-achievements`, or copy that folder from the checkout. No marketplace submission or global installation is performed by cloning this repository.

## Requirements

- A local Mac with macOS 13.5 or later, or Windows 10/11; ARM64 or x64.
- Python 3.9 or later for the setup helper. Use a maintained Python version where possible. On Windows, `py -3` can replace `python3` in the examples.
- Network access to GitHub for setup and update checks, and to the CLI's GOG services for normal use.
- A user who can complete local GOG sign-in. Windows sign-in also needs the Microsoft WebView2 Runtime.

The CLI release includes its own runtime and native helper. Node, npm, and a compiler are not required. Hosted Linux agents cannot use the current CLI or native sign-in. They need a separate local connection, which this skill does not supply.

## Use

Examples:

- “Show my missing GOG achievements for Cyberpunk 2077.”
- “I earned the story ending achievement, but GOG did not record it. Help me find it.”
- “Restore these two achievements. Use 12 October 2026 at 19:30 in Europe/London.”

The skill uses information already present in the conversation. It asks only for unresolved game, achievement, or date choices. If no date is given, it offers **Now** as the default in the selection or review prompt. Listing achievements does not authorize an unlock.

The skill runs `doctor` and `auth status`, uses native sign-in if needed, shows a queue and dry run, and applies the exact selection within the user's authorization. Existing unlocks stay unchanged. Partial or unconfirmed results stop the flow for review.

## Runtime and updates

From an installed skill folder:

```sh
python3 scripts/runtime.py ensure
python3 scripts/runtime.py ensure --offline
python3 scripts/runtime.py check-updates
python3 scripts/runtime.py config --auto-update on
python3 scripts/runtime.py config --auto-update off
python3 scripts/runtime.py update
```

The helper returns JSON with the absolute CLI path, version, queue directory, and update status. Use `--cli /absolute/path/to/gog-achievements` or `GOG_ACHIEVEMENTS_CLI` to select an existing installation. An explicit path must pass validation; the helper does not silently replace it.

Runtime data goes to `~/Library/Application Support/GogAchievementsSkill` on Mac, or `%LOCALAPPDATA%\GogAchievementsSkill` on Windows. `--data-dir PATH` can select another private directory outside the installed skill. No downloaded executables, credentials, or queues belong in this repository.

The initial approved release is **CLI v0.4.0**. Each approved release has four pinned SHA-256 archive hashes. Installation checks the hash, archive paths, package metadata, and executable JSON contract before activation. Previous versions stay available for rollback. These hashes check the downloaded bytes; they are not a publisher signature.

`ensure` checks public update metadata at most once per 24 hours while the skill is used. Offline mode performs no checks or downloads. A failed update check does not prevent use of an available approved CLI. Automatic installation is off by default and applies only to the skill-managed copy and a release approved in `cli-releases.json`. New upstream versions need validation and a skill update before automatic installation is allowed. External and Electron-bundled CLIs are never updated by this helper. There are no background jobs.

Read [setup and recovery](skills/gog-achievements/references/setup.md) for errors and rollback. The [CLI workflow reference](skills/gog-achievements/references/cli.md) covers command shapes, dates, and partial results.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
python3 scripts/package.py
```

Tests use local fixtures and make no GOG requests. CI runs on Mac, Windows, and Linux. Linux is for helper tests and package checks only. Platform support still requires native release tests and a local user for sign-in. Real historical date acceptance remains a CLI/GOG limitation; a fixture test does not prove a live write.

`scripts/package.py` creates `dist/gog-achievements-skill.zip` with only the portable skill folder. Keep platform marketplace manifests separate when adding them. A shared skill format does not guarantee marketplace approval.

To approve a CLI release, validate its command contract and native release packages, add all four published archive hashes, update `preferred_version`, and run the tests. Update `tests/evaluations.md` when a real request exposes a missing decision rule.
