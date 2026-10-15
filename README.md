# GOG Achievements Skill

Find, unlock, and re-lock selected GOG achievements through a conversation with a local AI agent. This skill uses the [GOG Achievements CLI](https://github.com/opista/gog-achievements-cli). It can resolve game and achievement descriptions, show choices, collect unlock dates, and prepare unlocks, locks, or a mixed queue for review.

## Install

Install with the [Skills CLI](https://github.com/vercel-labs/skills), then choose your agent and installation scope:

```sh
npx skills add opista/gog-achievements-skill --skill gog-achievements
```

For a user-wide Codex installation:

```sh
npx skills add opista/gog-achievements-skill --skill gog-achievements --agent codex --global
```

The installer needs Node.js and npm. The skill and downloaded CLI do not. You can also download a ZIP from [Releases](https://github.com/opista/gog-achievements-skill/releases), or clone this repository over HTTPS:

```sh
git clone https://github.com/opista/gog-achievements-skill.git
```

For manual installation, copy the complete `skills/gog-achievements` folder into your agent's skill directory. In a release ZIP, that folder is named `gog-achievements`. For Codex, use `~/.agents/skills/gog-achievements` or a project `.agents/skills/gog-achievements` directory. Start a new chat after installation.

This repository follows the [Agent Skills specification](https://agentskills.io/specification). The optional `agents/openai.yaml` adds Codex display metadata; the main workflow uses no vendor-specific tools. A directory listing or plugin-store installation is separate from installing this repository.

## Requirements

- A local Mac with macOS 13.5 or later, or Windows 10/11; ARM64 or x64.
- Python 3.9 or later for the setup helper. Use a maintained Python version where possible. On Windows, `py -3` can replace `python3` in the examples.
- Network access to GitHub for setup and update checks, and to the CLI's GOG services for normal use.
- A user who can complete local GOG sign-in. Windows sign-in also needs the Microsoft WebView2 Runtime.

The CLI release includes its own runtime and native helper. A compiler is not required. Hosted Linux agents cannot use the current CLI or native sign-in. They need a separate local connection, which this skill does not supply.

## Test a fresh installation

Move an existing manual skill installation to a backup directory outside every agent's skill directory, then run the install command above. Start a new chat and ask it to list achievements before trying an unlock. This checks public installation and skill discovery without changing achievements.

Replacing the skill does not remove its downloaded CLI, preferences, queues, or GOG login. Keep those for an installation-only test. To also test the first CLI download, use the runtime helper's `--data-dir` option with a new directory outside the skill; an existing CLI on PATH may still be reused. Sign-in is separate and can reuse the credentials held by the CLI.

## Use

Examples:

- “Show my missing GOG achievements for Cyberpunk 2077.”
- “Help me find the story ending achievement.”
- “Unlock these two achievements. Use 12 October 2026 at 19:30 in Europe/London.”
- “Lock First Steps again. Leave my other achievements unchanged.”
- “Unlock these two achievements at that date, and lock this other one.”

The skill uses information already present in the conversation. It asks only for unresolved game, achievement, action, or unlock-date choices. An unlock request does not require a claim or proof that the user earned the achievement. If no unlock date is given, it offers **Now** as the default in the selection or review prompt. Listing achievements does not authorize a write.

Achievement lists use numbered tables with names, requirements, and status, including follow-up requests such as “What else is locked?” Hidden entries stay in a separate count until requested. Large lists use labeled pages with stable choice numbers. An explicit request for another format takes precedence.

The skill checks local support and sign-in, uses native sign-in if needed, checks the requested changes, and shows each action before it changes GOG. It says an achievement is “ready to unlock” or “ready to lock” after the checks, and reports success only after confirmation from GOG. Existing unlocks stay unchanged unless you explicitly select them for locking. Partial or unconfirmed results stop the flow for review.

Locks need CLI v0.5.0 and remove the current unlock date. The review shows that original date, which the CLI saves in the queue and result. If it changes before apply, the request stops for a new review. Locks have no requested date. An unlock request never authorizes a lock, and the skill does not use a lock/unlock cycle to edit an existing unlock date. Mixed queues apply in order; earlier confirmed changes remain if a later item fails. Statistics and account-wide resets are not supported.

For a running game, it explains the next step directly: “Save and close Cyberpunk 2077 first so its next GOG sync does not conflict with this change.” It accepts a normal reply or a reliable process check; it does not require the word “closed.” Routine messages explain the practical reason. Host instructions may still require a source citation for an actual confirmation or block, and take precedence over the skill's wording guidance.

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

The preferred approved release is **CLI v0.5.0**. CLI v0.4.0 remains approved for reads and unlocks. Each approved release has four pinned SHA-256 archive hashes. Installation checks the hash, archive paths, package metadata, and executable JSON contract before activation; v0.5.0 must declare action support on both queue commands. Previous versions stay available for rollback. These hashes check the downloaded bytes; they are not a publisher signature.

`ensure` checks public update metadata at most once per 24 hours while the skill is used. Offline mode performs no checks or downloads. A failed update check does not prevent use of an available approved CLI. Automatic installation is off by default and applies only to the skill-managed copy and a release approved in `cli-releases.json`. New upstream versions need validation and a skill update before automatic installation is allowed. External and Electron-bundled CLIs are never updated by this helper. There are no background jobs.

An existing v0.4.0 managed copy stays active until you request `update` or enable automatic installation. Update it before a lock request; the skill checks for the required action options and never sends lock flags to the older CLI.

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

## Releases

This repository uses the same Release Please flow as the CLI and Electron repositories. Conventional Commits on `main` create or update a release PR with the version and changelog. Release Please updates `version.txt`, `.release-please-manifest.json`, and the skill's version together. Merge the checked release PR to start publication.

The release starts as a draft. The workflow pins its existing tag to one commit, runs the fixture tests, validation, packaging, and native CLI probes on Mac, Windows, and Linux, and builds a versioned skill ZIP with a SHA-256 checksum. Linux runs package and helper checks; native probes run on Mac and Windows. Publication uses the verified Linux-built archive after all three jobs pass. It checks the tag again and publishes only the matching draft release.

To retry a failed draft release, run the **Release** workflow with its existing version tag. Published releases cannot be replaced by that workflow. Local release checks are:

```sh
python3 scripts/release.py build --tag v0.1.3
python3 scripts/release.py verify --tag v0.1.3
```

Replace the example tag with `v` followed by the version in `version.txt`.
