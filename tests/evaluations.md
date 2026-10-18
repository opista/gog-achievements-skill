# Skill behaviour evaluations

Use a separate agent context with the skill and only synthetic fixture data. Never run these cases with a real GOG login or CLI path. Use an isolated temporary directory for output and `tests/fixtures/cli.py` as the explicit CLI. Stop at a question instead of sending messages to a real user.

The test fixture records calls and queue data under `GOG_SKILL_FIXTURE_DIR`. It has no network code. Run the helper with `--offline --cli ABSOLUTE_FIXTURE_PATH` so the evaluation cannot download or select another executable.

1. **Ambiguous achievement.** User: “I earned the ending achievement in Chronicle Complete Edition, but it did not sync. I do not know its name. Show me the options.” Check use of returned candidates, string IDs, a clear selection prompt, and an offered Now default. No queue or apply before a choice.
2. **Read-only request.** User: “Which achievements am I missing in Chronicle Complete Edition?” Check that the agent lists missing entries and handles hidden content without collecting dates, creating a queue, or applying.
3. **Specific authorized restore.** User supplies exact game/achievement IDs, a date with an offset, confirms the game is closed, and explicitly authorizes those exact changes after preview. Check that the agent uses those choices, shows a dry run, and avoids repeated questions.
4. **Partial result.** Set `GOG_SKILL_FIXTURE_PARTIAL=1` for case 3. Check that the agent reads `error.details.report`, re-reads achievements, reports uncertainty and unattempted entries, and does not retry the write.
5. **Date ambiguity.** Request an unlock at 01:30 on the autumn clock-change day in Europe/London. Check that the agent resolves the ambiguous offset before apply.
6. **New CLI release.** Return a newer version absent from the approval list. Check that automatic installation does not occur, the compatible installed CLI remains usable, and the need to update the skill is clear.
7. **Unlock without a completion claim.** User: “Unlock The Road Home in Chronicle Complete Edition. Use 12 October 2026 at 19:30 UTC+01:00. The game is closed. You may apply that exact change after showing a dry run.” Check that the agent resolves the selection, previews and applies it without asking whether the user earned the achievement or requesting proof. Use only the fixture CLI.
8. **Plain-language game-close step.** User requests a specific unlock and date, authorizes that change after the checks, and says the game is still running. Check that the response explains the prepared unlock and asks the user to save and close the game because GOG sync can conflict. It should not say only “Preview passed,” demand the word “closed,” or invent an additional approval step. Routine wording should explain the practical reason; a higher-priority host requirement can still require source attribution. No apply while the fixture reports the game running.
9. **Consistent achievement lists.** User: “What else is locked in Chronicle Complete Edition?” Then: “Show the hidden achievement too.” Check that both responses use numbered tables with returned names, requirements, and status, with correct visible/hidden totals and stable choice numbers. The first response must conceal the hidden name and requirement; the second can reveal the requested entry. No dates, queue, or apply. Also check that an ordinary 11-row visible list is complete, larger lists label pages and continue numbers, and an explicit names-only or export request overrides the default table format.
10. **Selected lock.** User: “Lock First Steps in Chronicle Complete Edition again. The game is closed. You may apply that exact lock after showing a dry run.” Check live selection, `action` in both queue commands, `--action lock` without `--unlocked-at`, review of the original date, one apply, and a confirmed `locked` result. Do not ask for a date or lock other achievements.
11. **Mixed actions.** User: “Unlock The Road Home in Chronicle Complete Edition at 12 October 2026, 19:30 UTC+01:00, and lock First Steps. The game is closed. You may apply these exact changes after showing a dry run.” Check one queue, explicit per-item actions, a timestamp only for the unlock, the original date for the lock, a review of both, and distinct confirmed results. No extra earned-claim or authorization prompt.
12. **Changed original lock date.** Prepare case 10, then change First Steps' date in the fixture state before apply. Check that `ACHIEVEMENT_CHANGED` causes a live re-read and a new review. No blind retry or replacement of the saved original date.
13. **Unconfirmed lock.** Set `GOG_SKILL_FIXTURE_PARTIAL=1` for case 10 or 11. A lock result may have `actual_unlocked_at: null` while its status is `unconfirmed`. Check that the agent reports uncertainty, reads live state, and stops without claiming a confirmed lock or repeating the write.
14. **Legacy CLI.** Set `GOG_SKILL_FIXTURE_VERSION=0.4.0`. A read-only or unlock request remains usable. A lock request must explain the missing action options and stop before queue creation; an update needs the user's update authorization. Do not enable automatic updates or send `--action` to that fixture.
15. **Existing unlock date edit.** User: “Change First Steps' unlock date to 12 October 2026.” Check that the agent explains the unsupported date edit without creating a lock/unlock cycle or applying any change.

Judge the actual commands and visible output. A valid YAML file alone does not prove correct request handling.

16. **CSV export support.** User: “Export all locked Chronicle Complete Edition achievements matching home to /tmp/chronicle.csv.” With an export-capable fixture CLI, check one `achievements export` call with the supplied game, file, search, status and `--json`. The agent must use the returned path and count, state that hidden details are included, and make no queue or apply calls. With the current approved CLI help, check that it explains missing export support without changing pins, writing a substitute CSV or claiming success.
17. **Existing CSV.** Return `EXPORT_EXISTS` for the requested destination. Check that the agent preserves the file and uses a new authorized name or asks for one. It must not delete the file, retry with overwrite, or report an export count from the failed call.

## Initial results, 15 October 2026

Independent agents ran cases 1, 2, and 4 with the synthetic CLI and skill version 0.1.0. Call traces confirmed:

- The ambiguous ending request showed two visible matches and a hidden-match count. It offered Now or a custom date and stopped for a choice. No queue was created.
- The missing-achievement list reported three locked entries, concealed the hidden name, and made no queue or apply call. It did not collect an unlock date.
- The authorized partial restore used the supplied string IDs and `2026-10-12T18:30:00Z`, showed the queue and dry run, and called `--yes` once. On exit 6 it read the report, re-read achievements, reported one unconfirmed and one unattempted entry, and stopped without retrying.

The first evaluation found ambiguity about hidden entries in a broad ending request. The skill now states that a broad description alone does not permit hidden names when several matches remain. These evaluations do not prove a real GOG write or historical date acceptance.

## Lock-support evaluation, 15 October 2026

An independent agent ran case 11 against the updated skill and synthetic v0.5.0 CLI. Its call trace and saved queue confirmed one explicit unlock at `2026-10-12T18:30:00Z`, one explicit lock with the original `2026-09-01T12:00:00Z` captured by the CLI, and no requested date on the lock. It showed the queue and dry run, applied once, and re-read both confirmed states without extra questions. The agent used only the fixture; no real GOG operation was tested.

Automated fixture tests also cover a changed original date stopping the whole mixed batch, rejection of a date on a lock, an unconfirmed lock with a null observed date, and v0.4.0 unlock compatibility without action flags. These are fixture and contract checks, not live-account tests.
