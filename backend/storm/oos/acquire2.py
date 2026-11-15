"""Acquire registration 2 month by month, before any detector evaluation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

import pandas as pd

from .acquire import OHLC, read_side
from .protocol import sha256
from .protocol2 import DATA2, REGISTRATION2, check_frozen2


def convert_month(bid, ask, window, output):
    b, a = read_side(bid), read_side(ask)
    f = b.join(a, how="inner", lsuffix="_bid", rsuffix="_ask")
    lo, start, end = (pd.Timestamp(window[k], tz="UTC") for k in
                      ("download_start", "start", "end_exclusive"))
    if ((f.index < lo) | (f.index >= end)).any():
        raise ValueError("source outside registered range")
    if (f[["open_ask", "close_ask"]].to_numpy() < f[["open_bid", "close_bid"]].to_numpy()).any():
        raise ValueError("negative open/close spread")
    observed = f.index[(f.index >= start) & (f.index < end)]
    weekdays = int((pd.date_range(start, end, freq="D", inclusive="left").weekday < 5).sum())
    coverage = len(observed) / (1440 * weekdays)
    warm = int((f.index < start).sum())
    if window["id"] == "2025-01" and warm < 720:
        raise ValueError(f"insufficient initial warm-up: {warm} < 720")
    if coverage < 0.5:
        raise ValueError(f"insufficient monthly weekday coverage: {coverage} < 0.5")
    gaps = f.index.to_series().diff().dropna()
    quality = {"bid_rows": len(b), "ask_rows": len(a), "joined_rows": len(f),
               "evaluation_rows": len(observed), "warmup_rows": warm, "weekday_coverage": coverage,
               "unmatched_bid": len(b.index.difference(a.index)), "unmatched_ask": len(a.index.difference(b.index)),
               "gaps_over_one_minute": int((gaps > pd.Timedelta(minutes=1)).sum()),
               "largest_gap_minutes": float(gaps.max() / pd.Timedelta(minutes=1)),
               "first_utc": f.index[0].isoformat(), "last_utc": f.index[-1].isoformat()}
    for c in OHLC:
        f[c + "_mid"] = (f[c + "_bid"] + f[c + "_ask"]) / 2
    f.insert(0, "settlement_date", f.index.tz_localize(None).normalize())
    output.parent.mkdir(parents=True, exist_ok=True)
    f.reset_index().to_parquet(output, index=False)
    return quality


def acquire_pair(cli, window, pair, hard_stop):
    folder = DATA2 / window["id"]
    raw = folder / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rec = {"pair": pair, "status": "unusable", "reason": None, "raw": {}}
    try:
        for side in ("bid", "ask"):
            seconds = (hard_stop - pd.Timestamp.now(tz="UTC")).total_seconds()
            if seconds <= 0:
                raise subprocess.TimeoutExpired("hard acquisition deadline", 0)
            path = raw / f"{pair}_{side}.csv"
            cmd = [str(cli), "-i", pair.lower(), "-from", window["download_start"],
                   "-to", window["end_exclusive"], "-t", "m1", "-p", side, "-f", "csv", "-v",
                   "-dir", str(raw), "-fn", f"{pair}_{side}", "-bs", "5", "-bp", "1000",
                   "--retries", "3", "-rp", "10000", "--no-fail-after-retries", "-s"]
            env = dict(os.environ)
            env.update(NODE_OPTIONS="--require=" + str(Path(__file__).with_name("transport2.cjs")),
                       OOS_FEED_CACHE=str(DATA2 / "feed-cache"),
                       OOS_TRANSPORT_LOG=str(raw / f"{pair}_{side}_http.jsonl"))
            if (DATA2 / "exhausted-urls.json").exists():
                env['OOS_BLOCKED_URLS'] = str(DATA2 / "exhausted-urls.json")
            with (raw / f"{pair}_{side}.log").open("w") as log:
                done = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
                                      timeout=max(1, min(600, seconds)), check=False)
            if path.exists():
                rec["raw"][side] = {"path": str(path.relative_to(DATA2)), "sha256": sha256(path)}
            if done.returncode or not path.exists():
                raise ValueError(f"{side} download failed (exit {done.returncode}); see retained log")
        out = folder / "processed" / f"{pair}_SPOT.parquet"
        rec["quality"] = convert_month(raw / f"{pair}_bid.csv", raw / f"{pair}_ask.csv", window, out)
        rec["parquet"] = {"path": str(out.relative_to(DATA2)), "sha256": sha256(out)}
        rec["status"] = "usable"
    except subprocess.TimeoutExpired as exc:
        if pd.Timestamp.now(tz="UTC") >= hard_stop:
            rec.update(status="not_completed_by_deadline", reason="hard acquisition cutoff")
        else:
            rec["reason"] = f"transport timeout: {exc}"
    except (ValueError, OSError, KeyError) as exc:
        rec["reason"] = str(exc)
    rec["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    print(window["id"], pair, rec["status"], rec["reason"] or "", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", type=Path, required=True)
    args = ap.parse_args()
    spec = check_frozen2()
    if sha256(args.cli.resolve()) != spec["downloader"]["cli_sha256"]:
        raise SystemExit("pinned CLI source differs from registration 2")
    DATA2.mkdir(parents=True, exist_ok=True)
    marker = DATA2 / "acquisition_started.json"
    with marker.open("x") as out:
        out.write(json.dumps({"started_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                              "preregistration_sha256": sha256(REGISTRATION2)}, indent=2) + "\n")
    manifest = {"preregistration_sha256": sha256(REGISTRATION2), "started_utc": json.loads(marker.read_text())["started_utc"],
                "months": [], "selected_months": [], "selected_end": None}
    stop_new = pd.Timestamp(spec["deadline"]["last_new_month_start_utc"])
    hard_stop = pd.Timestamp(spec["deadline"]["hard_acquisition_stop_utc"])
    stopped = False
    with ThreadPoolExecutor(max_workers=3) as pool:
        for w in spec["months"]:
            if stopped or pd.Timestamp.now(tz="UTC") >= stop_new:
                records = [{"pair": p, "status": "not_completed_by_deadline", "reason": "month not started before cutoff", "raw": {}}
                           for p in spec["pairs"]]
                completed = False
                stopped = True
            else:
                jobs = [pool.submit(acquire_pair, args.cli, w, p, hard_stop) for p in spec["pairs"]]
                records = [job.result() for job in jobs]
                completed = all(r["status"] in ("usable", "unusable") for r in records)
                completed &= all(pd.Timestamp(r["finished_utc"]) < hard_stop for r in records)
                if completed:
                    manifest["selected_months"].append(w["id"])
                    manifest["selected_end"] = w["end_exclusive"]
                else:
                    stopped = True
            manifest["months"].append({**w, "completed": bool(completed), "pairs": records})
            manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
            temp = DATA2 / "manifest.tmp"
            temp.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
            temp.replace(DATA2 / "manifest.json")
            print("Month finalized:", w["id"], "selected:", completed, flush=True)


if __name__ == "__main__":
    main()
