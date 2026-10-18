# CLI workflow reference

Use the approved CLI's `--help --json` for the installed contract. The source documentation is [CLI reference at v0.5.0](https://github.com/opista/gog-achievements-cli/blob/v0.5.0/docs/cli-reference.md). In examples, `CLI` means the resolved absolute executable path. All calls need `--json`.

## Compatibility

Before preparing locks or mixed queues, check that both `queue create` and `queue add` declare `action` in JSON help. CLI v0.5.0 supports both; the runtime rejects v0.5.0 packages that lack either option. Approved v0.4.0 supports reads and unlocks only; omit `--action` on that version. If action options are missing, explain the required update and stop before preparing locks. Follow [updates](setup.md#updates) within the user's update authorization; never replace the CLI during a reviewed batch.

## Responses and selection

Success: `{ "ok": true, "data": ... }`. Failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ... } }`. Parse stdout separately from stderr, including after a nonzero exit. Never print raw native sign-in output.

- `games list --search TEXT`: `data.user_id`, `data.games[]` with string `id` and `title`. Search is not an achievement filter.
- `achievements list --game GAME_ID`: `data.user_id`, `data.game`, `data.achievements[]`. Each entry has string `id`, `key`, `name`, `description`, boolean `hidden`, boolean `unlocked`, and `unlocked_at` (timestamp or null). Use the explicit state and date together. A null date is never a valid requested unlock date or, by itself, proof of a successful lock.

## Achievement-list display

Use numbered Markdown tables for all achievement lists, including search matches, read-only follow-ups, and requested hidden entries. Honor explicit requests for another format. Populate rows only from returned entries:

**Game title — 3 locked achievements: 2 visible, 1 hidden.**

| # | Achievement | Requirement | Status |
| --- | --- | --- | --- |
| 1 | **Returned name** | Short returned description | Locked |
| 2 | **Another returned name** | Short returned description | Locked |

Use bold names, brief returned requirements, and **Locked** or **Unlocked** status. If no description is returned, use an em dash. Never invent a requirement. Escape pipes and collapse line breaks in cells. Add unlock dates or results when useful for a review or result.

Lead with the game and matching count. Show all visible matches that fit on one page; for large lists, use pages of about 20 rows, state the shown range and total, and offer the next page. Do not silently omit matches. Keep choice numbers stable across pages and follow-ups, mapped to their string IDs; hide raw IDs unless requested.

Report withheld hidden entries as a count and offer to reveal them. Reveal names and requirements only when requested or clearly identified by the user; a broad description such as “the ending achievement” does not permit hidden names when several matches remain. Do not withhold information needed for an explicit request. Append requested hidden entries with new choice numbers. Permission to show one entry does not permit showing all hidden entries. All counts must match the filtered data and withheld entries.

## CSV export

Inspect `CLI --help --json` for `achievements export` and its `game`, `file`, `search`, and `status` flags before use. Current approved CLI releases v0.4.0 and v0.5.0 lack this command. If absent, explain that export needs a CLI release with this feature. Do not change release pins, replace the CLI, or build CSV with a separate script as a fallback.

Resolve the requested game and destination path. Reuse supplied search text and status; omit filters when the user asks for all achievements. Ask only when the destination or selection is unclear. Tell the user that CSV includes hidden achievement names and descriptions. An explicit export request permits those fields in the file; keep chat details within the user's reveal request.

```sh
CLI achievements export --game GAME_ID --file CSV_PATH --json
CLI achievements export --game GAME_ID --file CSV_PATH --search TEXT --status locked --json
```

`--status` accepts `all`, `locked`, or `unlocked`. Search matches names and descriptions without case sensitivity and combines with status. The CLI uses the same selection as `achievements list`. It writes UTF-8 CSV with columns `game_id,game_title,achievement_id,name,description,hidden,status,unlocked_at`. IDs retain their exact digits; unlocked dates use UTC and locked dates are empty. Spreadsheet applications must import ID columns as text to retain all digits.

CSV goes to the file, never stdout. Parse the success envelope and report `data.path` and `data.count`. An empty selection still writes the header with count 0. `EXPORT_EXISTS` means no replacement was made: choose another path within the user's request, or ask for a new name. Do not delete the existing file or claim success after a file or network error. No queue, unlock date, game-close step, dry run, or achievement apply is needed for export.

## Queue commands

Use a new UUID filename under `data.queue_directory`. For example, generate the basename with Python `uuid.uuid4()` and a `.json` suffix. Do not create the file before `queue create`; that command refuses to overwrite an existing file.

```sh
CLI queue create --game GAME_ID --file QUEUE_PATH --achievement FIRST_ID --action unlock --unlocked-at TIMESTAMP --json
CLI queue add --file QUEUE_PATH --achievement SECOND_ID --action lock --json
CLI queue show --file QUEUE_PATH --json
CLI queue apply --file QUEUE_PATH --dry-run --json
CLI queue apply --file QUEUE_PATH --yes --json
```

For a lock-only queue, use `queue create --game GAME_ID --file QUEUE_PATH --achievement ID --action lock`, with no date flag. Repeat `--achievement` for several entries with the same action and, for unlocks, the same date. Add other actions or dates with separate `queue add` calls. Use `queue set-date --file PATH --achievement ID --unlocked-at TIMESTAMP` only for unlock entries. `queue remove --file PATH --achievement ID` changes only the local queue.

Queue files belong to one user and game, use schema version 1, and hold at most 1,000 unique achievements. An ID cannot appear twice with different actions. Let the CLI capture current achievement keys and validate the file. Unlock entries have `unlocked_at` and optional `action: "unlock"`; an omitted action means unlock. Lock entries have `action: "lock"` and the original non-null `previous_unlocked_at` captured exactly from GOG. They omit `unlocked_at`. Never pass a null unlock date or add a date flag to a lock.

`queue show` returns the queue in `data`, including `user_id`, `game`, and `items[]` with `achievement_id`, `name`, action, and the relevant date field above. Apply returns a report in `data`, or in `error.details.report` on exit 6. A report has `dry_run`, `complete`, `user_id`, `game`, and `results[]`.

## Unlock dates

Always pass `--unlocked-at` explicitly for unlocks, with an RFC 3339 timestamp and explicit offset, at or before the actual current time. Allow one date for several achievements or separate dates for each. Never pass a date with `--action lock`.

For Now, read the actual clock when preparing the queue and freeze one UTC timestamp at second precision for the reviewed batch. Do not use the date in the prompt. For example:

```python
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

The CLI's omitted-date default is ten seconds before the operation. For custom dates, reuse the user's date and zone or established context; ask if the exact time, zone, or daylight-saving offset is ambiguous. Do not infer a historical offset from the machine's current offset. Dates are stored at UTC second precision. Show the local date, time zone, and UTC equivalent in the review. Do not promise that GOG will accept or retain a historical date; report any returned date difference.

## Apply results

| Status | Meaning |
| --- | --- |
| `pending` | Preview only. No write. |
| `restored` | Unlock and requested date confirmed. |
| `skipped_already_unlocked` | Existing unlock and date preserved. |
| `restored_with_different_date` | Unlock confirmed, requested date not retained. |
| `locked` | Requested lock confirmed by a fresh read. |
| `skipped_already_locked` | Already locked; no write needed. |
| `failed` | Write rejected; requested change not confirmed. |
| `unconfirmed` | Could not confirm the final state. Read live achievements. |
| `not_attempted` | Apply stopped before this entry. |

Inspect each result's action and status, plus `requested_unlocked_at`, `previous_unlocked_at`, and `actual_unlocked_at`. A missing action means unlock. Lock results have `action: "lock"`, `requested_unlocked_at: null`, and the saved `previous_unlocked_at`. Only `locked` or `skipped_already_locked` confirms a lock; `actual_unlocked_at: null` in an `unconfirmed` result is not success.

The CLI checks the full queue before writes, rechecks each achievement before writing, and reads back each result. Unlock requests preserve existing unlocks. Locks require explicit user selection and preserve the original date in the queue and report. If a still-unlocked achievement's date changes, `ACHIEVEMENT_CHANGED` stops the request. Re-read the state, remove and re-add only the selected lock, then review its new original date before applying. Never silently replace that snapshot to bypass a conflict.

A failure, uncertainty, or date mismatch stops later writes. A lost write response is reconciled with reads; the CLI does not repeat the POST automatically. Earlier confirmed changes stay applied. A mixed batch is not atomic and is not rolled back automatically.

Exit codes: 0 command completed; 2 input invalid; 3 login required/rejected; 4 network/API failure; 5 account, ownership, game, or lock conflict; 6 incomplete apply; 7 native credential/browser/process failure. For exit 6, inspect the report, read live state, and await review before retrying. A retry cannot correct a date on an already unlocked entry.

GOG has no atomic compare-and-set operation. Keep the game closed during apply to avoid conflicting updates from its next GOG sync. Do not run concurrent apply commands or remove another process's queue lock.
