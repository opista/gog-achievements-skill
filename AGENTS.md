# Project instructions

- This repository contains a portable Agent Skill for the GOG Achievements CLI.
- Keep the skill in `skills/gog-achievements`. Keep its instructions independent of any agent vendor. Vendor metadata can live in `agents/`.
- Use Python 3.9 or later and the standard library for runtime helpers. Do not add a second GOG API client or credential store.
- All GOG operations use the CLI JSON contract. Keep IDs as strings. Never print login codes, callback URLs, or tokens.
- Keep runtime files, preferences, and queues outside the skill and repository. Only update a skill-managed CLI installation.
- Pin approved CLI releases and all four archive hashes in `cli-releases.json`. Do not approve a release from its version number alone.
- Tests must use fixtures. Do not sign in or write real achievements in an automated test.
- Release Please updates the version and changelog from Conventional Commits. Publish only the existing draft release after all platform checks pass, and verify the version, archive contents, checksum, and pinned tag before publication.
- Classify commits by their effect, including changes in Markdown: use `feat:` for new skill capabilities, `fix:` for corrections, `refactor:` for instruction restructuring, and `docs:` for supporting documentation. Keep `docs:` and `refactor:` eligible for patch releases. Use `chore:` and `test:` for maintenance that does not change the shipped skill.
- After changes, run `python3 -m unittest discover -s tests -v` and validate the skill. Keep tool waits at 30 seconds or less.
- Use Conventional Commits. Before a new task, use main and pull latest unless the task needs an existing branch. Preserve concurrent work.
