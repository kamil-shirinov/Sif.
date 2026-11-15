"""Write web/pages/index.json: the public (GitHub Pages) build's storm index, with no market data.

    python scripts/build_pages_index.py           # from web/public/bundles/index.json (local, gitignored)
    python scripts/build_pages_index.py --check   # fail if web/pages/index.json holds anything not allowed

The local index lists every exported storm with its bundle file. The public build ships no bundle except the
synthetic mock storm, because SGX's (and Yahoo's and Dukascopy's) data is not redistributed. So this copy keeps
only the storm list and the backtest metrics, drops `file`, and is marked `"bundles": "withheld"`; the web app
then lists those storms as "Replay in the local demo (market data not redistributed)". Fields are copied by an
allow-list, so a field added to the local index later never reaches the public site by accident.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "web" / "public" / "bundles" / "index.json"
PUBLIC = ROOT / "web" / "pages" / "index.json"

STORM_FIELDS = ("storm_id", "title", "symbol", "asset_class", "kind", "move_bp", "source")
METRIC_FIELDS = (
    "split", "storms", "alarmed", "caught", "caught_first_onset", "median_move_ahead_pct",
    "median_move_ahead_pct_first_onset", "median_minutes_to_alarm", "median_minutes_to_alarm_first_onset",
    "false_alarms_per_day", "false_alarm_episodes_per_day", "watch_precision",
)
TOP_FIELDS = ("schema_version", "bundles", "note", "storms", "metrics")


def sanitize(local: dict) -> dict:
    metrics = local.get("metrics") or {}
    return {
        "schema_version": 1,
        "bundles": "withheld",
        "note": "Public build: storm list and metrics only. Market data is not redistributed; the replays run in the local demo.",
        "storms": [{k: s[k] for k in STORM_FIELDS if k in s} for s in local["storms"]],
        "metrics": {k: metrics[k] for k in METRIC_FIELDS if k in metrics},
    }


def problems(index: dict) -> list[str]:
    out = []
    if index.get("bundles") != "withheld":
        out.append('"bundles" must be "withheld"')
    out += [f"top-level field {k!r} is not allowed" for k in index if k not in TOP_FIELDS]
    for s in index.get("storms", []):
        out += [f"{s.get('storm_id')}: field {k!r} is not allowed" for k in s if k not in STORM_FIELDS]
    out += [f"metrics field {k!r} is not allowed" for k in (index.get("metrics") or {}) if k not in METRIC_FIELDS]
    return out


def main(argv: list[str]) -> int:
    if "--check" in argv:
        found = problems(json.loads(PUBLIC.read_text()))
        print("\n".join(found) if found else f"{PUBLIC.relative_to(ROOT)}: storm list and metrics only")
        return 1 if found else 0
    index = sanitize(json.loads(LOCAL.read_text()))
    assert not problems(index)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {PUBLIC.relative_to(ROOT)} ({len(index['storms'])} storms, no bundles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
