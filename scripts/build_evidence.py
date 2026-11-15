#!/usr/bin/env python3
"""Build web/public/evidence.json, the Explorer's data, from the published result files.

Re-runnable, never edited by hand: every number in the output is copied from these sources (nothing is computed except
counts and medians over rows the sources list, marked as such):

  web/public/bundles/index.json        SGX storms with replay bundles, and the August test metrics
  web/public/bundles/<storm>.json      July rows (alarm and share ahead), from each replay bundle's `storm` block
  docs/results_snapshot.json           SGX storm counts (all months)
  docs/stats/units/sgx-august.json     August per-storm rows (method v1)
  docs/oos/results.json                round 1: crisis events 2015-2024 and ordinary months
  docs/oos/results-2.json              round 2: January to July 2025 (partial)
  docs/chips/results.json              chip stocks
  docs/stats/results.json              intervals and the random-timing test across all of them

Usage: python3 scripts/build_evidence.py   (from the repo root)
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = ROOT / "web" / "public" / "bundles"
OUT = ROOT / "web" / "public" / "evidence.json"

SOURCES = {
    "index": BUNDLES / "index.json",
    "snapshot": ROOT / "docs" / "results_snapshot.json",
    "sgx_august": ROOT / "docs" / "stats" / "units" / "sgx-august.json",
    "oos_round1": ROOT / "docs" / "oos" / "results.json",
    "oos_round2": ROOT / "docs" / "oos" / "results-2.json",
    "chips": ROOT / "docs" / "chips" / "results.json",
    "stats": ROOT / "docs" / "stats" / "results.json",
}


def load(path: Path):
    with path.open() as f:
        return json.load(f)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rnd(x, nd=1):
    return None if x is None else round(float(x), nd)


def headline(m: dict) -> dict:
    """The headline numbers of a metrics block, as published."""
    return {
        "storms": m.get("storms"),
        "alarmed": m.get("alarmed"),
        "caught": m.get("caught"),
        "median_move_ahead_pct": rnd(m.get("median_move_ahead_pct")),
        "median_minutes_to_alarm": rnd(m.get("median_minutes_to_alarm")),
        "false_alarm_episodes_per_day": rnd(m.get("false_alarm_episodes_per_day"), 2),
        "days": rnd(m.get("days"), 1),
    }


def row(s: dict, replays: dict[str, str], group: str | None = None, in_sample: bool = False) -> dict:
    """One storm row from a published per-storm record (the detector's own `caught`, never recomputed)."""
    sid = s["storm_id"]
    alarmed = s.get("alarm_utc") is not None
    return {
        "id": sid,
        "date": (s.get("onset_utc") or "")[:16].replace("T", " "),
        "instrument": s.get("pair"),
        "kind": s.get("kind"),
        "move_bp": rnd(s.get("move_bp")),
        "alarmed": alarmed,
        "share_ahead_pct": rnd(s.get("move_ahead_pct")) if alarmed else None,
        "caught": bool(s.get("caught")),
        "group": group,
        "in_sample": in_sample,
        "bundle": replays.get(sid),
    }


def main():
    index = load(SOURCES["index"])
    replays = {s["storm_id"]: s["file"] for s in index["storms"] if s.get("source") != "scenario"}
    snapshot = load(SOURCES["snapshot"])
    datasets = []

    # ---- SGX FX, July (tuning, in-sample): rows from the replay bundles' storm blocks ----
    july_rows = []
    for s in index["storms"]:
        if s.get("source") != "sgx" or "-2026-07-" not in s["storm_id"]:
            continue
        b = load(BUNDLES / s["file"])
        st = b["storm"]
        alarmed = st.get("alarm_i") is not None
        ahead = st.get("move_ahead_pct") if alarmed else None
        onset_utc = b["t0"] + st["onset_i"] * b["step_s"]
        from datetime import datetime, timezone

        july_rows.append(
            {
                "id": s["storm_id"],
                "date": datetime.fromtimestamp(onset_utc, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "instrument": s["symbol"],
                "kind": st.get("kind"),
                "move_bp": rnd(st.get("move_bp")),
                "alarmed": alarmed,
                "share_ahead_pct": rnd(ahead),
                # The bundle carries no `caught` flag: this is the metric's own definition (docs/metrics.md),
                # at least half of the move still ahead when the alarm sounds.
                "caught": ahead is not None and ahead >= 50,
                "group": None,
                "in_sample": True,
                "bundle": s["file"],
            }
        )
    july_rows.sort(key=lambda r: r["date"])
    if july_rows:
        aheads = [r["share_ahead_pct"] for r in july_rows if r["share_ahead_pct"] is not None]
        datasets.append(
            {
                "id": "sgx-july",
                "title": "SGX FX, July 2026",
                "period": "1 to 31 July 2026",
                "labels": ["tuning month", "in-sample"],
                "note": "The detector was tuned on July. These storms are the replays we show; they are not evidence that it works.",
                "headline": {
                    "storms": len(july_rows),
                    "alarmed": sum(r["alarmed"] for r in july_rows),
                    "caught": sum(r["caught"] for r in july_rows),
                    "median_move_ahead_pct": rnd(statistics.median(aheads)) if aheads else None,
                    "median_minutes_to_alarm": None,
                    "false_alarm_episodes_per_day": None,
                    "days": None,
                },
                "headline_note": "Counted over the July replay bundles (caught: at least half the move ahead).",
                "storms": july_rows,
            }
        )

    # ---- SGX FX, August (test) ----
    aug = load(SOURCES["sgx_august"])["result"]["methods"]["v1"]
    m = index.get("metrics") or {}
    datasets.append(
        {
            "id": "sgx-august",
            "title": "SGX FX, August 2026",
            "period": "1 to 31 August 2026",
            "labels": ["test month", "never seen in tuning"],
            "note": f"Held out while tuning. {snapshot.get('by_kind.all_months.combined.storms', '?')} storms over July and August in all.",
            "headline": headline({**aug, **{k: m[k] for k in ("storms", "alarmed", "caught", "median_move_ahead_pct", "false_alarm_episodes_per_day") if k in m}}),
            "headline_note": None,
            "storms": sorted((row(s, replays) for s in aug["per_storm"]), key=lambda r: r["date"]),
        }
    )

    # ---- round 1: crisis events 2015-2024 and ordinary months ----
    r1 = load(SOURCES["oos_round1"])["display"]
    r1_rows = []
    for w in r1["windows"]:
        for s in w["metrics"].get("per_storm") or []:
            r1_rows.append(row(s, replays, group=w["name"]))
    datasets.append(
        {
            "id": "oos-round1",
            "title": "Crisis events 2015 to 2024, and ordinary months",
            "period": "6 event windows and 2 ordinary months",
            "labels": ["round 1", "pre-registered", "out of sample"],
            "note": "Rules and thresholds frozen and registered before the data was downloaded (docs/oos/preregistration.md).",
            "headline": headline(r1["totals"]["all"]["metrics"]),
            "headline_note": None,
            "storms": sorted(r1_rows, key=lambda r: r["date"]),
        }
    )

    # ---- round 2: January to July 2025 ----
    r2 = load(SOURCES["oos_round2"])["display"]
    months = r2.get("selected_months") or []
    datasets.append(
        {
            "id": "oos-round2",
            "title": "January to July 2025",
            "period": f"{months[0]} to {months[-1]}" if months else "2025",
            "labels": ["round 2", "pre-registered", "partial"],
            "note": f"Partial: {r2.get('usable_pair_months')} of {r2.get('planned_pair_months')} planned pair-months could be used (docs/oos/results-2.md).",
            "headline": headline(r2["metrics"]),
            "headline_note": None,
            "storms": sorted((row(s, replays) for s in r2["metrics"]["per_storm"]), key=lambda r: r["date"]),
        }
    )

    # ---- chip stocks ----
    chips = load(SOURCES["chips"])
    chip_rows = [row(s, replays, in_sample=s.get("pair") == "NVDA") for s in chips["storms"]]
    datasets.append(
        {
            "id": "chips",
            "title": "Chip stocks",
            "period": "13 new tickers, plus NVDA",
            "labels": ["pre-registered", "new tickers", "NVDA in-sample"],
            "note": "The headline is the new tickers only; NVDA was looked at before the rules were frozen, so its rows are marked in-sample.",
            "headline": headline(chips["pooled"]["new_tickers"]),
            "headline_note": None,
            "storms": sorted(chip_rows, key=lambda r: r["date"]),
        }
    )

    # ---- statistics across all of them ----
    stats = load(SOURCES["stats"])
    titles = {
        "sgx_august": "SGX August",
        "oos_round1": "Round 1",
        "oos_round2": "Round 2 (partial)",
        "chips_new": "Chip stocks, new tickers",
        "pooled_fx": "All FX pooled",
        "pooled_all": "Everything pooled",
    }
    groups = []
    for gid, title in titles.items():
        g = stats["groups"].get(gid)
        if not g:
            continue
        p = g["point"]
        iv = g.get("intervals") or {}
        ch = (g.get("chance") or {}).get("caught_storms") or {}
        ci = lambda k: [rnd(x, 3) for x in (iv.get(k) or {}).get("ci95") or []] or None  # noqa: E731
        groups.append(
            {
                "id": gid,
                "title": title,
                "storms": p.get("storms"),
                "alarmed": p.get("alarmed"),
                "caught": p.get("caught"),
                "alarmed_share": rnd(p.get("alarmed_share"), 3),
                "alarmed_share_ci95": ci("alarmed_share"),
                "caught_share": rnd(p.get("caught_share"), 3),
                "caught_share_ci95": ci("caught_share"),
                "random_timing": {
                    "caught": ch.get("statistic"),
                    "null_median": ch.get("null_median"),
                    "null_ci95": ch.get("null_ci95"),
                    "p_value": rnd(ch.get("p_value"), 4),
                    "holm_p_value": rnd(ch.get("holm_p_value"), 4),
                    "replicates": ch.get("replicates"),
                }
                if ch
                else None,
            }
        )

    out = {
        "schema_version": 1,
        "generated_by": "scripts/build_evidence.py",
        "book": "The trading book in every replay is synthetic: $1M equity, labelled as such.",
        "sources": {k: {"path": str(p.relative_to(ROOT)), "sha256": sha256(p)} for k, p in SOURCES.items()},
        "datasets": datasets,
        "stats": {
            "note": "95% bootstrap intervals; the random-timing test moves the alarms to random times and counts how often chance catches as many storms (one-sided).",
            "groups": groups,
        },
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    n = sum(len(d["storms"]) for d in datasets)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(datasets)} datasets, {n} storms, {len(groups)} stats groups")


if __name__ == "__main__":
    main()
