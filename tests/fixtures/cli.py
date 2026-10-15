#!/usr/bin/env python3
"""Synthetic CLI for agent evaluations. No network or credential access."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ACCOUNT = "90071992547409930"
GAME = {"id": "9007199254740993", "title": "Chronicle Complete Edition", "client_id": "9007199254740994"}
ACHIEVEMENTS = [
    {"id": "90071992547409931", "key": "ENDING_HOME", "name": "The Road Home", "description": "Finish the story by returning home.", "hidden": False, "unlocked": False, "unlocked_at": None},
    {"id": "90071992547409932", "key": "ENDING_STAY", "name": "A New Beginning", "description": "Finish the story by staying in the new world.", "hidden": False, "unlocked": False, "unlocked_at": None},
    {"id": "90071992547409933", "key": "SECRET", "name": "The Secret Gate", "description": "Find the secret ending.", "hidden": True, "unlocked": False, "unlocked_at": None},
    {"id": "90071992547409934", "key": "FIRST", "name": "First Steps", "description": "Complete the tutorial.", "hidden": False, "unlocked": True, "unlocked_at": "2026-09-01T12:00:00Z"},
]
COMMANDS = {
    "doctor": [], "auth status": [], "auth login": [],
    "games list": ["search"], "achievements list": ["game"],
    "queue create": ["file", "game", "achievement", "unlocked-at", "action"],
    "queue add": ["file", "achievement", "unlocked-at", "action"],
    "queue set-date": ["file", "achievement", "unlocked-at"],
    "queue remove": ["file", "achievement"],
    "queue show": ["file"], "queue apply": ["file", "yes", "dry-run"], "self update": ["check"],
}


def failure(code, message, exit_code=2):
    print(json.dumps({"ok": False, "error": {"code": code, "message": message}}))
    return exit_code


def main():
    root = Path(os.environ["GOG_SKILL_FIXTURE_DIR"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    arguments = sys.argv[1:]
    with (root / "calls.jsonl").open("a", encoding="utf-8") as trace:
        trace.write(json.dumps(arguments) + "\n")
    words, flags = [], {}
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("--"):
            key = argument[2:]
            if index + 1 < len(arguments) and not arguments[index + 1].startswith("--"):
                flags.setdefault(key, []).append(arguments[index + 1])
                index += 1
            else:
                flags[key] = True
        else:
            words.append(argument)
        index += 1
    command = " ".join(words)
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    achievements = [dict(item, **state.get(item["id"], {})) for item in ACHIEVEMENTS]
    by_id = {item["id"]: item for item in achievements}
    value = lambda key: flags[key][0]
    version = os.environ.get("GOG_SKILL_FIXTURE_VERSION", "0.5.0")
    if version == "0.4.0" and "action" in flags:
        return failure("INVALID_ARGUMENT", "This fixture version does not support --action.")
    if "help" in flags:
        data = {"name": "gog-achievements", "version": version, "common_flags": ["--json"],
                "commands": [{"command": name,
                              "flags": [option for option in options if version != "0.4.0" or option != "action"]}
                             for name, options in COMMANDS.items()]}
    elif command == "doctor":
        data = {"supported": True, "platform": "darwin", "architecture": "arm64", "node": "24.19.0",
                "credentials_available": True, "login": {"authenticated": True, "user_id": ACCOUNT}}
    elif command == "auth status":
        data = {"authenticated": True, "expired": False, "user_id": ACCOUNT}
    elif command == "self update":
        data = {"current_version": version, "latest_version": version, "update_available": False, "can_update": False}
    elif command == "games list":
        games = [{"id": GAME["id"], "title": GAME["title"]}]
        if "search" in flags:
            games = [game for game in games if value("search").casefold() in game["title"].casefold()]
        data = {"user_id": ACCOUNT, "count": len(games), "games": games}
    elif command == "achievements list":
        assert value("game") == GAME["id"]
        data = {"user_id": ACCOUNT, "game": GAME, "count": len(achievements), "achievements": achievements}
    elif command in {"queue create", "queue add", "queue set-date", "queue remove"}:
        path = Path(value("file"))
        queue = ({"schema_version": 1, "user_id": ACCOUNT, "game": GAME, "items": []}
                 if command == "queue create" else json.loads(path.read_text(encoding="utf-8")))
        assert command != "queue create" or not path.exists()
        if command == "queue create":
            assert value("game") == GAME["id"]
        action = value("action") if "action" in flags else "unlock"
        if action not in {"unlock", "lock"}:
            return failure("INVALID_ARGUMENT", "Unknown achievement action.")
        if action == "lock" and "unlocked-at" in flags:
            return failure("INVALID_ARGUMENT", "Lock requests have no requested date.")
        for identifier in flags.get("achievement", []):
            assert identifier in by_id
            if command == "queue remove":
                queue["items"] = [item for item in queue["items"] if item["achievement_id"] != identifier]
            elif command == "queue set-date":
                for item in queue["items"]:
                    if item["achievement_id"] == identifier:
                        if item.get("action") == "lock":
                            return failure("INVALID_ARGUMENT", "Lock requests have no requested date.")
                        item["unlocked_at"] = value("unlocked-at")
            else:
                achievement = by_id[identifier]
                if any(item["achievement_id"] == identifier for item in queue["items"]):
                    return failure("INVALID_ARGUMENT", "An achievement can appear only once.")
                item = {"achievement_id": identifier, "key": achievement["key"], "name": achievement["name"]}
                if action == "lock":
                    if not achievement["unlocked"]:
                        return failure("ACHIEVEMENT_ALREADY_LOCKED", "Choose an unlocked achievement.", 5)
                    item.update(action="lock", previous_unlocked_at=achievement["unlocked_at"])
                else:
                    item["unlocked_at"] = value("unlocked-at")
                    if "action" in flags:
                        item["action"] = "unlock"
                queue["items"].append(item)
        queue["updated_at"] = datetime.now(timezone.utc).isoformat()
        queue.setdefault("created_at", queue["updated_at"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(queue), encoding="utf-8")
        data = queue
    elif command == "queue show":
        data = json.loads(Path(value("file")).read_text(encoding="utf-8"))
    elif command == "queue apply":
        queue = json.loads(Path(value("file")).read_text(encoding="utf-8"))
        dry_run = "yes" not in flags
        partial = not dry_run and os.environ.get("GOG_SKILL_FIXTURE_PARTIAL") == "1"
        for item in queue["items"]:
            current = by_id[item["achievement_id"]]
            if (item.get("action") == "lock" and current["unlocked"]
                    and current["unlocked_at"] != item["previous_unlocked_at"]):
                return failure("ACHIEVEMENT_CHANGED", "The original unlock date changed.", 5)
        results = []
        for index, item in enumerate(queue["items"]):
            action = item.get("action", "unlock")
            current = by_id[item["achievement_id"]]
            requested = item.get("unlocked_at")
            skipped = current["unlocked"] == (action == "unlock")
            if skipped:
                status = "skipped_already_unlocked" if action == "unlock" else "skipped_already_locked"
            elif dry_run:
                status = "pending"
            elif partial:
                status = "unconfirmed" if index == 0 else "not_attempted"
            else:
                status = "locked" if action == "lock" else "restored"
            actual = (requested if status == "restored" else None if status in {"locked", "unconfirmed", "not_attempted"}
                      else current["unlocked_at"])
            result = {"achievement_id": item["achievement_id"], "name": item["name"], "status": status,
                      "requested_unlocked_at": requested,
                      "previous_unlocked_at": item.get("previous_unlocked_at", current["unlocked_at"]),
                      "actual_unlocked_at": actual}
            if "action" in item:
                result["action"] = action
            results.append(result)
            if status in {"restored", "locked"}:
                state[item["achievement_id"]] = {"unlocked": status == "restored", "unlocked_at": actual}
        if not dry_run:
            state_path.write_text(json.dumps(state), encoding="utf-8")
        data = {"dry_run": dry_run, "complete": not partial, "user_id": ACCOUNT, "game": GAME, "results": results}
        if partial:
            print(json.dumps({"ok": False, "error": {"code": "APPLY_INCOMPLETE", "message": "Fixture result is uncertain.", "details": {"report": data}}}))
            return 6
    else:
        print(json.dumps({"ok": False, "error": {"code": "FIXTURE_COMMAND_UNSUPPORTED", "message": command}}))
        return 2
    print(json.dumps({"ok": True, "data": data}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
