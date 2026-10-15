# CLI workflow reference

Use the approved CLI's `--help --json` for the installed contract. The source documentation is [CLI reference at v0.5.0](https://github.com/opista/gog-achievements-cli/blob/v0.5.0/docs/cli-reference.md). All calls below also need `--json`. Use “ready to unlock” or “ready to lock” for a successful dry run in normal chat. Reserve “unlocked” and “locked” for confirmed states.

Both `queue create` and `queue add` must declare `action` in JSON help before preparing locks or mixed queues. The runtime rejects v0.5.0 packages that lack either option. Approved v0.4.0 remains usable for reads and unlock-only queues; omit `--action` on that version. See [setup.md](setup.md#updates) before updating an older managed CLI.

## Responses and selection

Success: `{ "ok": true, "data": ... }`. Failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ... } }`. Parse stdout separately from stderr, including after a nonzero exit. Never print raw native sign-in output.

- `games list --search TEXT`: `data.user_id`, `data.games[]` with string `id` and `title`. Search is not an achievement filter.
- `achievements list --game GAME_ID`: `data.user_id`, `data.game`, `data.achievements[]`. Each entry has string `id`, `key`, `name`, `description`, boolean `hidden`, boolean `unlocked`, and `unlocked_at` (timestamp or null). Use the explicit state and date together. A null date is never a valid requested unlock date or, by itself, proof of a successful lock.
- `auth status`: inspect `authenticated`, `expired`, and `user_id`. A stored expired access token can refresh on the next GOG command. Native credential permission errors can require explicit local sign-in.
- `auth login`: human completes the native window; successful JSON reports `authenticated: true`. Manual `--no-open` can return exit 0 with `authenticated: false` and `action_required`; that is not a completed sign-in. Do not pass callback URLs or codes through chat or command arguments.

## Achievement-list display

Use this format for all achievement lists, including read-only follow-ups, unless the user requests another format. Populate rows only from returned entries:

**Game title — 3 locked achievements: 2 visible, 1 hidden.**

| # | Achievement | Requirement | Status |
| --- | --- | --- | --- |
| 1 | **Returned name** | Short returned description | Locked |
| 2 | **Another returned name** | Short returned description | Locked |

**1 hidden achievement** is omitted to avoid spoilers. Offer to show its name and requirement. When the user requests it, show it in the same table format with the next choice number. An explicit request for one hidden entry does not permit revealing all hidden entries.

Counts must match the returned, filtered entries and any withheld hidden entries. For pages, state the range and total, and continue the numbering; do not reduce an ordinary list to a few sample rows. Keep the mapping from choice to the actual string ID. A description can identify candidates; use the user's request to decide whether they want a list, unlock, or lock. No statement or proof that they earned the achievement is required for an unlock. Apply only within their authorization for the reviewed selection, actions, and dates.

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

Always set explicit RFC 3339 dates with a time zone, at or before the actual current time. Dates are stored at UTC second precision. For Now, generate once when preparing the queue:

```python
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

The default for an omitted date is ten seconds before the CLI operation, not the skill's explicit Now. A supplied ambiguous local date needs a time zone or UTC offset. If GOG returns another date, report that difference; do not claim the requested historical date was retained.

`queue show` returns the queue in `data`, including `user_id`, `game`, and `items[]` with `achievement_id`, `name`, action, and the relevant date field above. Apply returns a report in `data`, or in `error.details.report` on exit 6. A report has `dry_run`, `complete`, `user_id`, `game`, and `results[]`.

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

Keep the game closed during apply to avoid conflicting updates from its next GOG sync. GOG has no atomic compare-and-set operation. Explain that practical reason when asking the user to save and close it. Do not require a specific reply word or another confirmation if closure is already known; a reliable read-only process check can establish that the game has stopped. Do not run concurrent apply commands or remove another process's queue lock. Do not perform statistics or account-wide resets, implicit locks, or a lock/unlock cycle to edit an existing unlock date.
