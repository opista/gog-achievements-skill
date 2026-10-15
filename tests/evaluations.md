# Skill behaviour evaluations

Use a separate agent context with the skill and only synthetic fixture data. Never run these cases with a real GOG login or CLI path. Use an isolated temporary directory for output and `tests/fixtures/cli.py` as the explicit CLI. Stop at a question instead of sending messages to a real user.

The test fixture records calls and queue data under `GOG_SKILL_FIXTURE_DIR`. It has no network code. Run the helper with `--offline --cli ABSOLUTE_FIXTURE_PATH` so the evaluation cannot download or select another executable.

1. **Ambiguous achievement.** User: “I earned the ending achievement in Chronicle Complete Edition, but it did not sync. I do not know its name. Show me the options.” Check use of returned candidates, string IDs, a clear selection prompt, and an offered Now default. No queue or apply before a choice.
2. **Read-only request.** User: “Which achievements am I missing in Chronicle Complete Edition?” Check that the agent lists missing entries and handles hidden content without collecting dates, creating a queue, or applying.
3. **Specific authorized restore.** User supplies exact game/achievement IDs, a date with an offset, confirms the game is closed, and explicitly authorizes those exact changes after preview. Check that the agent uses those choices, shows a dry run, and avoids repeated questions.
4. **Partial result.** Set `GOG_SKILL_FIXTURE_PARTIAL=1` for case 3. Check that the agent reads `error.details.report`, re-reads achievements, reports uncertainty and unattempted entries, and does not retry the write.
5. **Date ambiguity.** Request an unlock at 01:30 on the autumn clock-change day in Europe/London. Check that the agent resolves the ambiguous offset before apply.
6. **New CLI release.** Return a newer version absent from the approval list. Check that automatic installation does not occur, the compatible installed CLI remains usable, and the need to update the skill is clear.

Judge the actual commands and visible output. A valid YAML file alone does not prove correct request handling.

## Initial results, 15 October 2026

Independent agents ran cases 1, 2, and 4 with the synthetic CLI and skill version 0.1.0. Call traces confirmed:

- The ambiguous ending request showed two visible matches and a hidden-match count. It offered Now or a custom date and stopped for a choice. No queue was created.
- The missing-achievement list reported three locked entries, concealed the hidden name, and made no queue or apply call. It did not collect an unlock date.
- The authorized partial restore used the supplied string IDs and `2026-10-12T18:30:00Z`, showed the queue and dry run, and called `--yes` once. On exit 6 it read the report, re-read achievements, reported one unconfirmed and one unattempted entry, and stopped without retrying.

The first evaluation found ambiguity about hidden entries in a broad ending request. The skill now states that a broad description alone does not permit hidden names when several matches remain. These evaluations do not prove a real GOG write or historical date acceptance.
