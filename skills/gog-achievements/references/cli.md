# CLI workflow reference

Use the approved CLI's `--help --json` for the installed contract. The source documentation is [CLI reference at v0.4.0](https://github.com/opista/gog-achievements-cli/blob/v0.4.0/docs/cli-reference.md). All calls below also need `--json`. These command and result names are technical reference terms; use “ready to unlock” for a successful dry run in normal chat, and reserve “unlocked” for a confirmed write.

## Responses and selection

Success: `{ "ok": true, "data": ... }`. Failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ... } }`. Parse stdout separately from stderr, including after a nonzero exit. Never print raw native sign-in output.

- `games list --search TEXT`: `data.user_id`, `data.games[]` with string `id` and `title`. Search is not an achievement filter.
- `achievements list --game GAME_ID`: `data.user_id`, `data.game`, `data.achievements[]`. Each entry has string `id`, `key`, `name`, `description`, boolean `hidden`, boolean `unlocked`, and `unlocked_at` (UTC string or null). A null read value means locked; it is never a valid requested unlock date.
- `auth status`: inspect `authenticated`, `expired`, and `user_id`. A stored expired access token can refresh on the next GOG command. Native credential permission errors can require explicit local sign-in.
- `auth login`: human completes the native window; successful JSON reports `authenticated: true`. Manual `--no-open` can return exit 0 with `authenticated: false` and `action_required`; that is not a completed sign-in. Do not pass callback URLs or codes through chat or command arguments.

Selection display, using only actual returned entries:

| Choice | Achievement | Requirement | State |
| --- | --- | --- | --- |
| 1 | Returned name | Short returned description | Locked |

Keep the mapping from choice to the actual string ID. Display a useful subset and offer more. A description can identify candidates; use the user's request to decide whether they want a list or an unlock. No statement or proof that they earned the achievement is required. Apply only within their authorization for the reviewed selection and dates.

## Queue commands

Use a new UUID filename under `data.queue_directory`. For example, generate the basename with Python `uuid.uuid4()` and a `.json` suffix. Do not create the file before `queue create`; that command refuses to overwrite an existing file.

```sh
CLI queue create --game GAME_ID --file QUEUE_PATH --achievement FIRST_ID --unlocked-at TIMESTAMP --json
CLI queue add --file QUEUE_PATH --achievement SECOND_ID --unlocked-at OTHER_TIMESTAMP --json
CLI queue show --file QUEUE_PATH --json
CLI queue apply --file QUEUE_PATH --dry-run --json
CLI queue apply --file QUEUE_PATH --yes --json
```

Repeat `--achievement` for several entries with the same date. Use `queue add` or `queue set-date --file PATH --achievement ID --unlocked-at TIMESTAMP` for different dates. `queue remove --file PATH --achievement ID` changes only the local queue. Queue files belong to one user and game, use schema version 1, and hold at most 1,000 achievements. Let the CLI capture current achievement keys and validate the file.

Always set explicit RFC 3339 dates with a time zone, at or before the actual current time. Dates are stored at UTC second precision. For Now, generate once when preparing the queue:

```python
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

The default for an omitted date is ten seconds before the CLI operation, not the skill's explicit Now. A supplied ambiguous local date needs a time zone or UTC offset. If GOG returns another date, report that difference; do not claim the requested historical date was retained.

`queue show` returns the queue in `data`, including `user_id`, `game`, `items[]` with `achievement_id`, `name`, and `unlocked_at`. Apply returns a report in `data`, or in `error.details.report` on exit 6. A report has `dry_run`, `complete`, `user_id`, `game`, and `results[]`.

## Apply results

| Status | Meaning |
| --- | --- |
| `pending` | Preview only. No write. |
| `restored` | Unlock and requested date confirmed. |
| `skipped_already_unlocked` | Existing unlock and date preserved. |
| `restored_with_different_date` | Unlock confirmed, requested date not retained. |
| `failed` | Write rejected; unlock not confirmed. |
| `unconfirmed` | Could not confirm the final state. Read live achievements. |
| `not_attempted` | Apply stopped before this entry. |

Inspect `requested_unlocked_at` and `actual_unlocked_at` per result. The CLI checks the full queue before writes, rechecks each achievement before writing, and reads back each result. It preserves existing unlocks. A failure, uncertainty, or date mismatch stops later writes. A lost write response is reconciled with reads; the CLI does not repeat the POST automatically.

Exit codes: 0 command completed; 2 input invalid; 3 login required/rejected; 4 network/API failure; 5 account, ownership, game, or lock conflict; 6 incomplete apply; 7 native credential/browser/process failure. For exit 6, inspect the report, read live state, and await review before retrying. A retry cannot correct a date on an already unlocked entry.

Keep the game closed during apply to avoid conflicting updates from its next GOG sync. GOG has no atomic compare-and-set operation. Explain that practical reason when asking the user to save and close it. Do not require a specific reply word or another confirmation if closure is already known; a reliable read-only process check can establish that the game has stopped. Do not run concurrent apply commands or remove another process's queue lock. Do not reset/relock achievements or alter dates on existing unlocks.
