"""Poll only the requested OOS branch; retain a byte-exact results snapshot once published."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time

from .protocol import DOCS, REPO_ROOT, registration, save


def poll(fetch=True):
    now = datetime.now(timezone.utc)
    if fetch:
        subprocess.run(["git", "fetch", "origin", "lane/cx-oos2"], cwd=REPO_ROOT, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "origin/lane/cx-oos2"], cwd=REPO_ROOT, text=True).strip()
    result = subprocess.run(["git", "show", commit + ":docs/oos/results-2.json"], cwd=REPO_ROOT, capture_output=True)
    row = {"checked_at_utc": now.isoformat(), "commit": commit, "available": result.returncode == 0, "fetched": fetch}
    if result.returncode == 0:
        json.loads(result.stdout)
        target = DOCS / "round2-source-results.json"
        if not target.exists():
            target.write_bytes(result.stdout)
        elif target.read_bytes() != result.stdout:
            row["changed_after_first_capture"] = True
        row["sha256"] = hashlib.sha256(result.stdout).hexdigest()
    path = DOCS / "round2-polls.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    rows.append(row)
    save(path, rows)
    print(json.dumps(row), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--no-fetch",action="store_true")
    args = parser.parse_args()
    spec = registration()
    cutoff = datetime.fromisoformat(spec["round2_cutoff_utc"])
    while True:
        row = poll(not args.no_fetch)
        if row["available"] or args.once or datetime.now(timezone.utc) >= cutoff:
            return
        next_check = min(datetime.now(timezone.utc).timestamp() + 900, cutoff.timestamp())
        while datetime.now(timezone.utc).timestamp() < next_check:
            time.sleep(min(30, next_check - datetime.now(timezone.utc).timestamp()))


if __name__ == "__main__":
    main()
