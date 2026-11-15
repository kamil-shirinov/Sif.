#!/usr/bin/env python
"""Look-ahead check: the detector's output up to time T must not depend on any bar after T.

    cd backend && python ../scripts/causality_check.py [--cutoffs 24] [--out ../docs/causality_check.json]

For each pair and each cut-off T, the detector is run twice: on the full July-August spot series,
and on the series cut off after T (the bars after T are physically absent). Everything the detector
says at or before T must then be identical in the two runs: the per-minute strength, risk, direction
and state, and every episode that started by T (its start, its storm-level alarm if that came by T,
its all-clear if that came by T). A single difference would be look-ahead.

This tests the *detector* (features, risk, episodes, alarms). The storm *labels* are deliberately
not point in time (a label uses the whole history, to find the strongest 15-minute window); they are
used only to score, never as detector input (see docs/metrics.md section 1 and
backend/tests/test_audit2.py::test_1_full_history_labels_are_not_point_in_time_and_label_as_of_is).

Needs data/processed (run the backend pipeline first). No network, no model, nothing is written but
the JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from storm.detector import load_calendar, load_config, run_detector  # noqa: E402
from storm.features import PAIRS, add_comove, load_spot, pair_features  # noqa: E402

FRAME_COLUMNS = ["strength", "risk", "direction", "state"]


def equal(a: pd.Series, b: pd.Series) -> bool:
    x, y = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
    return bool(np.array_equal(x, y, equal_nan=True))


def episode_view(result, cutoff: pd.Timestamp) -> list[tuple]:
    """What the run says about episodes, restricted to what was knowable at the cut-off."""
    out = []
    for e in result.episodes:
        if e.start > cutoff:
            continue
        storm_at = e.storm_at if e.storm_at is not None and e.storm_at <= cutoff else None
        end = e.end if e.end is not None and e.end <= cutoff else None
        out.append((e.start, storm_at, end))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cutoffs", type=int, default=24)
    ap.add_argument("--out", default=str(HERE.parent / "docs" / "causality_check.json"))
    ap.add_argument("--seed", type=int, default=20260815)
    args = ap.parse_args()

    cfg = load_config()
    calendar = load_calendar()
    rng = np.random.default_rng(args.seed)
    report = {"cutoffs_per_pair": args.cutoffs, "seed": args.seed, "pairs": {}, "all_identical": True}
    spots = {p: load_spot(p).sort_values("timestamp").reset_index(drop=True) for p in PAIRS}

    def features(until: pd.Timestamp | None) -> dict[str, pd.DataFrame]:
        """Features of every pair from the bars up to `until` (all bars when None); comove is cross-pair."""
        feats = {p: pair_features(s if until is None else s[s["timestamp"] <= until], p) for p, s in spots.items()}
        return add_comove(feats)

    full_feats = features(None)
    full_runs = {p: run_detector(full_feats[p], calendar, cfg) for p in PAIRS}
    for pair in PAIRS:
        full, full_feat = full_runs[pair], full_feats[pair]
        times = full_feat.index
        # A cut-off needs a full day of warm-up behind it; draw them across the whole series, plus
        # the minutes just before and after the pair's own storm-level alarms, where a leak would show.
        lo = 1500
        picks = set(rng.integers(lo, len(times) - 1, size=args.cutoffs).tolist())
        for alarm, _ in full.storm_alarms()[:6]:
            j = int(times.get_indexer([alarm])[0])
            picks.update(k for k in (j - 1, j, j + 1) if lo <= k < len(times) - 1)
        rows = []
        for j in sorted(picks):
            cutoff = times[j]
            part_feats = features(cutoff)
            part = run_detector(part_feats[pair], calendar, cfg)
            upto = full.frame.loc[:cutoff]
            same_frame = all(equal(upto[c], part.frame.loc[:cutoff][c]) for c in FRAME_COLUMNS)
            same_eps = episode_view(full, cutoff) == episode_view(part, cutoff)
            # Negative control: a deliberately forward-looking series (the mid two bars ahead) must be
            # told apart by the same comparison, or this check would prove nothing.
            leaky_full = full_feat["mid"].shift(-2).loc[:cutoff]
            leaky_part = part_feats[pair]["mid"].shift(-2).loc[:cutoff]
            control_caught = not equal(leaky_full, leaky_part)
            rows.append({"cutoff": cutoff.isoformat(), "frame_identical": same_frame, "episodes_identical": same_eps,
                         "control_caught": control_caught})
        ok = all(r["frame_identical"] and r["episodes_identical"] for r in rows)
        report["pairs"][pair] = {
            "bars": int(len(times)),
            "cutoffs_tested": len(rows),
            "storm_alarms_in_full_run": len(full.storm_alarms()),
            "identical": ok,
            "negative_control_caught_at_every_cutoff": all(r["control_caught"] for r in rows),
            "differences": [r for r in rows if not (r["frame_identical"] and r["episodes_identical"])],
        }
        report["all_identical"] &= ok
        report["negative_control_ok"] = report.get("negative_control_ok", True) and all(r["control_caught"] for r in rows)
        print(f"{pair}: {len(rows)} cut-offs, {'identical' if ok else 'DIFFERENT'}")
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print("all identical" if report["all_identical"] else "LOOK-AHEAD FOUND: see the JSON")
    print("negative control (a price two bars ahead) was caught at every cut-off" if report["negative_control_ok"]
          else "NEGATIVE CONTROL MISSED: the check is not sensitive enough; do not trust it")
    return 0 if report["all_identical"] and report["negative_control_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
