#!/usr/bin/env python3
"""Download and probe the native release. No sign-in or GOG requests."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/gog-achievements/scripts/runtime.py"


def main():
    if sys.platform not in {"darwin", "win32"}:
        raise SystemExit("Packaged CLI smoke checks require Mac or Windows.")
    with tempfile.TemporaryDirectory(prefix="gog-skill-smoke-") as temporary:
        arguments = [sys.executable, str(HELPER), "ensure", "--data-dir", temporary]
        for offline in (False, True):
            result = subprocess.run(arguments + (["--offline"] if offline else []),
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    encoding="utf-8", timeout=180, check=False)
            data = json.loads(result.stdout)
            if result.returncode != 0 or not data.get("ok") or not data["data"]["managed"]:
                raise RuntimeError("Native release smoke check failed: " + result.stdout)
            print(json.dumps({"offline": offline, "version": data["data"]["version"],
                              "managed": data["data"]["managed"], "update": data["data"]["update"]["status"]}))


if __name__ == "__main__":
    main()
