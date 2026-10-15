import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures/cli.py"
GAME_ID = "9007199254740993"
UNLOCK_ID = "90071992547409931"
LOCK_ID = "90071992547409934"
DATE = "2026-10-12T18:30:00Z"
ORIGINAL_DATE = "2026-09-01T12:00:00Z"


class FixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.queue = self.root / "queue.json"
        self.environment = dict(os.environ, GOG_SKILL_FIXTURE_DIR=str(self.root))
        self.environment.pop("GOG_SKILL_FIXTURE_VERSION", None)
        self.environment.pop("GOG_SKILL_FIXTURE_PARTIAL", None)

    def call(self, *arguments):
        result = subprocess.run([sys.executable, str(FIXTURE), *arguments, "--json"],
                                env=self.environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def create_mixed_queue(self):
        code, _ = self.call("queue", "create", "--game", GAME_ID, "--file", str(self.queue),
                            "--achievement", UNLOCK_ID, "--action", "unlock", "--unlocked-at", DATE)
        self.assertEqual(code, 0)
        code, _ = self.call("queue", "add", "--file", str(self.queue),
                            "--achievement", LOCK_ID, "--action", "lock")
        self.assertEqual(code, 0)

    def test_mixed_preview_has_no_writes_and_apply_confirms_each_action(self):
        self.create_mixed_queue()
        lock = json.loads(self.queue.read_text())["items"][1]
        self.assertEqual(lock["previous_unlocked_at"], ORIGINAL_DATE)
        self.assertNotIn("unlocked_at", lock)
        code, response = self.call("queue", "apply", "--file", str(self.queue), "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual([item["status"] for item in response["data"]["results"]], ["pending", "pending"])
        self.assertFalse((self.root / "state.json").exists())
        code, response = self.call("queue", "apply", "--file", str(self.queue), "--yes")
        self.assertEqual(code, 0)
        self.assertEqual([item["status"] for item in response["data"]["results"]], ["restored", "locked"])
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state[UNLOCK_ID], {"unlocked": True, "unlocked_at": DATE})
        self.assertEqual(state[LOCK_ID], {"unlocked": False, "unlocked_at": None})

    def test_lock_with_a_requested_date_is_rejected_without_creating_queue(self):
        code, response = self.call("queue", "create", "--game", GAME_ID, "--file", str(self.queue),
                                   "--achievement", LOCK_ID, "--action", "lock", "--unlocked-at", DATE)
        self.assertEqual(code, 2)
        self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")
        self.assertFalse(self.queue.exists())

    def test_changed_lock_date_blocks_entire_mixed_batch_before_any_write(self):
        self.create_mixed_queue()
        state = {LOCK_ID: {"unlocked": True, "unlocked_at": "2026-09-02T12:00:00Z"}}
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps(state))
        code, response = self.call("queue", "apply", "--file", str(self.queue), "--yes")
        self.assertEqual(code, 5)
        self.assertEqual(response["error"]["code"], "ACHIEVEMENT_CHANGED")
        self.assertEqual(json.loads(state_path.read_text()), state)

    def test_unconfirmed_lock_with_null_date_is_not_reported_as_locked(self):
        code, _ = self.call("queue", "create", "--game", GAME_ID, "--file", str(self.queue),
                            "--achievement", LOCK_ID, "--action", "lock")
        self.assertEqual(code, 0)
        self.environment["GOG_SKILL_FIXTURE_PARTIAL"] = "1"
        code, response = self.call("queue", "apply", "--file", str(self.queue), "--yes")
        self.assertEqual(code, 6)
        item = response["error"]["details"]["report"]["results"][0]
        self.assertEqual(item["action"], "lock")
        self.assertEqual(item["status"], "unconfirmed")
        self.assertIsNone(item["actual_unlocked_at"])
        _, response = self.call("achievements", "list", "--game", GAME_ID)
        self.assertTrue(next(item for item in response["data"]["achievements"] if item["id"] == LOCK_ID)["unlocked"])

    def test_legacy_cli_supports_unlocks_and_rejects_action_options(self):
        self.environment["GOG_SKILL_FIXTURE_VERSION"] = "0.4.0"
        _, response = self.call("--help")
        for command in response["data"]["commands"]:
            self.assertNotIn("action", command["flags"])
        code, _ = self.call("queue", "create", "--game", GAME_ID, "--file", str(self.queue),
                            "--achievement", UNLOCK_ID, "--unlocked-at", DATE)
        self.assertEqual(code, 0)
        code, response = self.call("queue", "add", "--file", str(self.queue),
                                   "--achievement", LOCK_ID, "--action", "lock")
        self.assertEqual(code, 2)
        self.assertEqual(response["error"]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
