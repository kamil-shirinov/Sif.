"""Do prices warn before a storm? A small, saved check.

    cd backend && ~/.venvs/stormscore/bin/python ../scripts/no_warning_check.py

For each labelled storm (data/processed/storms.csv) it measures the 90 minutes before the
storm's onset, and before its first_onset, on three things:

  volatility      sd of the one-minute mid returns (bp) in the window
  spread          mean (ask - bid) / mid, in bp, in the window
  forward points  |change in forward points over the window| / spot mid, in bp, for 1W, 1M, 3M

and asks where that window sits among "normal" windows of the same pair: the windows that
end at the same clock time (UTC) on every other day of the data, and that do not touch any
storm (from 60 minutes before an onset to 60 minutes after the end). The rank is a
percentile: 50 = typical, 95 = higher than 95% of normal windows. If prices warned, the
percentiles of the pre-storm windows would pile up near 100. Chance alone puts about 10% of
storms above 90 and 5% above 95.

Writes docs/no_warning_check.json and docs/no_warning_check.md. Needs data/processed (SGX's
data is not redistributed with the repo); the saved result is what the README quotes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from storm.features import PAIRS, load_spot, pair_features  # noqa: E402
from storm.labels import read_storms  # noqa: E402

PRE = pd.Timedelta(minutes=90)
MIN_RETURNS = 80  # of 90; a window with more holes than this is not measured
TENORS = ("1W", "1M", "3M")
MIN_NORMAL = 6  # normal windows needed to rank a storm (an early-Monday storm has 8 Mondays)
FP_MAX_STALE = pd.Timedelta(minutes=5)
EDGE = pd.Timedelta(minutes=60)  # a window within this of a storm is not "normal"
PROCESSED = ROOT / "data" / "processed"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def load_fp(pair: str, tenor: str) -> pd.Series | None:
    path = PROCESSED / f"{pair}_{tenor}.parquet"
    if not path.exists():
        return None
    d = pd.read_parquet(path, columns=["timestamp", "close_mid_fp"]).set_index("timestamp")
    return d["close_mid_fp"].sort_index()


class Pair:
    """One pair's bars and forward points, with the three window measures."""

    def __init__(self, pair: str):
        self.pair = pair
        self.f = pair_features(load_spot(pair), pair)
        self.f.index = pd.DatetimeIndex(self.f.index)
        self.fp = {t: load_fp(pair, t) for t in TENORS}

    def measures(self, end: pd.Timestamp) -> dict[str, float] | None:
        """Measures of the bars in (end - 90 min, end]; None when the window is too thin."""
        w = self.f.loc[end - PRE + pd.Timedelta(seconds=1): end]
        ret = w["ret_bp"].dropna()
        if len(ret) < MIN_RETURNS or w["spread_bp"].notna().sum() < MIN_RETURNS:
            return None
        out = {"volatility_bp": float(ret.std()), "spread_bp": float(w["spread_bp"].mean())}
        for tenor, s in self.fp.items():
            out[f"fwd_pts_{tenor}_bp"] = self._fp_drift(s, end)
        return out

    def _fp_drift(self, s: pd.Series | None, end: pd.Timestamp) -> float:
        if s is None:
            return np.nan
        a, b = self._at(s, end - PRE), self._at(s, end)
        spot = self._at(self.f["mid"], end)
        if np.isnan(a) or np.isnan(b) or np.isnan(spot):
            return np.nan
        return abs(b - a) / spot * 1e4

    @staticmethod
    def _at(s: pd.Series, t: pd.Timestamp) -> float:
        """The last value at or before t, if it is at most 5 minutes old."""
        h = s.loc[:t]
        if h.empty or t - h.index[-1] > FP_MAX_STALE:
            return np.nan
        return float(h.iloc[-1])


def percentile(value: float, base: list[float]) -> float | None:
    b = np.array([x for x in base if not np.isnan(x)])
    if np.isnan(value) or len(b) < MIN_NORMAL:
        return None
    return float(100.0 * ((b < value).sum() + 0.5 * (b == value).sum()) / len(b))


def after_weekly_open(anchor: pd.Timestamp) -> bool:
    """Early Monday UTC: the 90 minutes sit in the first hours after the Sunday-evening open, whose
    spreads and volatility are not those of a mid-week night. Such windows are compared with other Mondays."""
    return anchor.dayofweek == 0 and anchor.hour < 6


def normal_windows(p: Pair, anchor: pd.Timestamp, storms: pd.DataFrame, days: pd.DatetimeIndex) -> list[dict]:
    spans = [(r.onset_utc - PRE - EDGE, r.end_utc + EDGE) for r in storms[storms.pair == p.pair].itertuples()]
    out = []
    for d in days:
        end = d + (anchor - anchor.normalize())
        if d == anchor.normalize() or (after_weekly_open(anchor) and d.dayofweek != 0):
            continue
        if any(lo <= end and end - PRE <= hi for lo, hi in spans):
            continue
        m = p.measures(end)
        if m is not None:
            out.append(m)
    return out


def main() -> None:
    storms = read_storms()
    for c in ("onset_utc", "end_utc", "first_onset_utc"):
        storms[c] = pd.to_datetime(storms[c], utc=True)
    pairs = {p: Pair(p) for p in PAIRS}
    idx = pairs["USDJPY"].f.index
    days = pd.date_range(idx.min().normalize(), idx.max().normalize(), freq="D", tz="UTC")

    result = {"anchors": {}}
    for anchor_col, label in (("onset_utc", "onset"), ("first_onset_utc", "first_onset")):
        rows = []
        for r in storms.itertuples():
            p = pairs[r.pair]
            anchor = getattr(r, anchor_col)
            own = p.measures(anchor)
            if own is None:
                rows.append({"storm_id": r.storm_id, "pair": r.pair, "anchor_utc": f"{anchor:%Y-%m-%d %H:%M}",
                             "skipped": "too few bars in the 90 minutes"})
                continue
            base = normal_windows(p, anchor, storms, days)
            row = {"storm_id": r.storm_id, "pair": r.pair, "kind": r.kind,
                   "anchor_utc": f"{anchor:%Y-%m-%d %H:%M}", "normal_windows": len(base), "measures": {}}
            for k, v in own.items():
                b = [m[k] for m in base]
                med = float(np.nanmedian(b)) if len(b) and not np.all(np.isnan(b)) else np.nan
                row["measures"][k] = {
                    "value": None if np.isnan(v) else round(v, 4),
                    "normal_median": None if np.isnan(med) else round(med, 4),
                    "ratio_to_normal_median": None if np.isnan(med) or med == 0 else round(v / med, 2),
                    "percentile": None if (q := percentile(v, b)) is None else round(q, 1),
                }
            rows.append(row)
        keys = ["volatility_bp", "spread_bp"] + [f"fwd_pts_{t}_bp" for t in TENORS]
        summary = {}
        for group in ("all", "scheduled", "unscheduled"):
            part = [r for r in rows if "measures" in r and (group == "all" or r["kind"] == group)]
            summary[group] = {}
            for k in keys:
                ps = [r["measures"][k]["percentile"] for r in part if r["measures"][k]["percentile"] is not None]
                summary[group][k] = {
                    "storms_measured": len(ps),
                    "median_percentile": round(float(np.median(ps)), 1) if ps else None,
                    "above_50": int(sum(x > 50 for x in ps)),
                    "above_90": int(sum(x >= 90 for x in ps)),
                    "above_95": int(sum(x >= 95 for x in ps)),
                }
        result["anchors"][label] = {"storms": rows, "summary": summary}

    result["provenance"] = {
        "data": {f"{p}_SPOT.parquet": sha(PROCESSED / f"{p}_SPOT.parquet") for p in PAIRS},
        "storms.csv": sha(PROCESSED / "storms.csv"),
        "sha256_prefix_chars": 12,
    }
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "no_warning_check.json").write_text(json.dumps(result, indent=2) + "\n")
    (ROOT / "docs" / "no_warning_check.md").write_text(render(result))
    print("wrote docs/no_warning_check.json and docs/no_warning_check.md")


NAMES = {"volatility_bp": "volatility", "spread_bp": "spread", "fwd_pts_1W_bp": "fwd points 1W",
         "fwd_pts_1M_bp": "fwd points 1M", "fwd_pts_3M_bp": "fwd points 3M"}


def render(res: dict) -> str:
    L = ["# Do prices warn before a storm?", "",
         "Generated by `scripts/no_warning_check.py` from SGX's one-minute bars (1 July to 31 August 2026, "
         "all 13 labelled storms; `docs/metrics.md` defines a storm). The data is not in the repo, so the "
         "result is saved here and in `docs/no_warning_check.json`.", "",
         "## Method", "",
         "For each storm, take the 90 minutes up to and including the onset bar, and measure:", "",
         "- **volatility**: standard deviation of the one-minute mid returns, in bp;",
         "- **spread**: mean of (ask - bid) / mid, in bp;",
         "- **forward points** (1W, 1M, 3M): the absolute change in forward points over the 90 minutes, as bp of the spot mid.", "",
         "Each is ranked against **normal windows of the same pair**: the 90 minutes ending at the same "
         "clock time (UTC) on every other day in the data, skipping any window within 60 minutes of a storm "
         "(60 min before an onset to 60 min after the end) and any window missing more than 10 of its 90 "
         "returns. A storm in the first hours after the Sunday-evening open (before 06:00 UTC on a Monday) is "
         "compared with other Mondays only, since those hours are not like a mid-week night. The same time of day keeps the daily rhythm out of the comparison (US releases at 12:30 "
         "UTC are always busier than the small hours). The **percentile** is the share of normal windows "
         "below the pre-storm window: 50 is typical, 95 is higher than 95% of normal windows. If prices "
         "warned, the percentiles would pile up near 100. Chance alone puts about 10% of storms above 90 and "
         "5% above 95. Each storm is ranked against about 40 "
         "other days, and the 13 storms are not independent (the three pairs often shock together on one release).", "",
         "Two anchors: the storm's `onset` (the start of its strongest 15-minute window), and its "
         "`first_onset` (the start of its first triggering window, which can be hours earlier). `first_onset` "
         "is the stricter test, because the 90 minutes before it contain none of the storm.", ""]
    for label in ("onset", "first_onset"):
        a_ = a = res["anchors"][label]
        L += [f"## Anchor: {label}", "", "| storms | measure | measured | median percentile | above 50 | above 90 | above 95 |",
              "|---|---|---|---|---|---|---|"]
        for group, part in a_["summary"].items():
            for k, v in part.items():
                L.append(f"| {group} | {NAMES[k]} | {v['storms_measured']} | {v['median_percentile']} | "
                         f"{v['above_50']} | {v['above_90']} | {v['above_95']} |")
        L += ["", "Per storm: the window's value as a multiple of the normal median, and its percentile (p95 = higher than 95% of normal windows). Where the normal median is 0 (forward points rarely move) only the percentile is shown.", "",
              "| storm | window ends (UTC) | kind | normal windows | volatility | spread | fwd 1W | fwd 1M | fwd 3M |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in a["storms"]:
            if "measures" not in r:
                L.append(f"| {r['storm_id']} | {r['anchor_utc']} | | | not measured: {r['skipped']} | | | | |")
                continue
            cells = []
            for k in NAMES:
                m = r["measures"][k]
                if m["percentile"] is None:
                    cells.append("n/a")
                elif m["ratio_to_normal_median"] is None:  # the normal median is 0 (forward points rarely move)
                    cells.append(f"p{m['percentile']:.0f}")
                else:
                    cells.append(f"{m['ratio_to_normal_median']}x, p{m['percentile']:.0f}")
            L.append(f"| {r['storm_id']} | {r['anchor_utc']} | {r['kind']} | {r['normal_windows']} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## Provenance", "", "SHA-256 prefixes (12 characters) of what this was computed from:", ""]
    for k, v in res["provenance"]["data"].items():
        L.append(f"- `{k}`: `{v}`")
    L.append(f"- `storms.csv`: `{res['provenance']['storms.csv']}`")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
