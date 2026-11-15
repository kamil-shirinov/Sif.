"""Download the registered bid/ask candles, then validate and convert without scoring.

python -m storm.oos.acquire --cli /path/to/node_modules/.bin/dukascopy-node
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from .protocol import DATA, REGISTRATION, check_frozen, sha256

OHLC = ("open", "high", "low", "close")


def read_side(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    required = {"timestamp", "volume", *OHLC}
    if not required.issubset(raw):
        raise ValueError(f"{path.name}: missing columns {sorted(required - set(raw))}")
    if raw.empty:
        raise ValueError(f"{path.name}: empty candle file")
    stamp = pd.to_numeric(raw["timestamp"], errors="raise")
    if not np.isfinite(stamp).all() or (stamp % 60_000 != 0).any():
        raise ValueError(f"{path.name}: invalid/non-minute timestamp")
    raw["timestamp"] = pd.to_datetime(stamp, unit="ms", utc=True).dt.as_unit("ns")
    if raw["timestamp"].duplicated().any():
        raise ValueError(f"{path.name}: duplicate timestamps")
    volume = pd.to_numeric(raw["volume"], errors="raise")
    if not np.isfinite(volume).all() or (volume < 0).any():
        raise ValueError(f"{path.name}: invalid volume metadata")
    raw = raw[volume > 0]
    if raw.empty:
        raise ValueError(f"{path.name}: no non-flat candles")
    values = raw[list(OHLC)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(f"{path.name}: nonpositive/nonfinite quotes")
    if ((raw["low"] > raw[["open", "close"]].min(axis=1)) |
        (raw["high"] < raw[["open", "close"]].max(axis=1)) |
        (raw["low"] > raw["high"])).any():
        raise ValueError(f"{path.name}: invalid OHLC bounds")
    return raw[["timestamp", *OHLC]].sort_values("timestamp").set_index("timestamp")


def convert(bid_path: Path, ask_path: Path, window: dict, output: Path) -> dict:
    bid, ask = read_side(bid_path), read_side(ask_path)
    joined = bid.join(ask, how="inner", lsuffix="_bid", rsuffix="_ask")
    lo = pd.Timestamp(window["download_start"], tz="UTC")
    start = pd.Timestamp(window["start"], tz="UTC")
    end = pd.Timestamp(window["end_exclusive"], tz="UTC")
    if ((joined.index < lo) | (joined.index >= end)).any():
        raise ValueError("source timestamps outside registered download range")
    if (joined[["open_ask", "close_ask"]].to_numpy() < joined[["open_bid", "close_bid"]].to_numpy()).any():
        raise ValueError("negative open/close bid-ask spread")
    for col in OHLC:
        joined[f"{col}_mid"] = (joined[f"{col}_bid"] + joined[f"{col}_ask"]) / 2
    warmup = int((joined.index < start).sum())
    evaluated = joined.index[(joined.index >= start) & (joined.index < end)]
    weekdays = int((pd.date_range(start, end, freq="D", inclusive="left").weekday < 5).sum())
    coverage = len(evaluated) / (weekdays * 1440) if weekdays else 0
    gaps = joined.index.to_series().diff().dropna()
    quality = {
        "bid_rows": len(bid), "ask_rows": len(ask), "joined_rows": len(joined),
        "unmatched_bid": int(len(bid.index.difference(ask.index))),
        "unmatched_ask": int(len(ask.index.difference(bid.index))),
        "warmup_rows": warmup, "evaluation_rows": len(evaluated),
        "nominal_weekday_coverage": coverage,
        "first_utc": None if joined.empty else joined.index[0].isoformat(),
        "last_utc": None if joined.empty else joined.index[-1].isoformat(),
        "gaps_over_one_minute": int((gaps > pd.Timedelta(minutes=1)).sum()),
        "largest_gap_minutes": None if gaps.empty else float(gaps.max() / pd.Timedelta(minutes=1)),
        "gaps": [{"after_utc": (t - d).isoformat(), "before_utc": t.isoformat(),
                  "minutes": float(d / pd.Timedelta(minutes=1))}
                 for t, d in gaps[gaps > pd.Timedelta(minutes=1)].items()],
    }
    if warmup < 720:
        raise ValueError(f"insufficient warm-up: {warmup} joined bars < 720")
    if coverage < 0.5:
        raise ValueError(f"insufficient evaluation coverage: {coverage:.6f} < 0.5")
    joined.insert(0, "settlement_date", joined.index.tz_localize(None).normalize())
    output.parent.mkdir(parents=True, exist_ok=True)
    joined.reset_index().to_parquet(output, index=False)
    return quality


def download_pair(cli: Path, window: dict, pair: str) -> dict:
    folder = DATA / window["id"]
    raw = folder / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    record = {"pair": pair, "status": "unusable", "reason": None, "raw": {}}
    for side in ("bid", "ask"):
        path = raw / f"{pair}_{side}.csv"
        log = raw / f"{pair}_{side}.log"
        command = [str(cli), "-i", pair.lower(), "-from", window["download_start"],
                   "-to", window["end_exclusive"], "-t", "m1", "-p", side,
                   "-f", "csv", "-v", "-dir", str(raw), "-fn", f"{pair}_{side}",
                   "-bs", "5", "-bp", "1000", "--retries", "3", "-s"]
        try:
            with log.open("w") as stream:
                env = dict(os.environ)
                env['NODE_OPTIONS'] = '--require=' + str(Path(__file__).with_name('transport.cjs'))
                env['OOS_FEED_CACHE'] = str(DATA / 'feed-cache')
                env['OOS_TRANSPORT_LOG'] = str(raw / f'{pair}_{side}_http.jsonl')
                done = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                      timeout=1800, check=False, env=env)
            if done.returncode != 0:
                raise ValueError(f"{side} download exit={done.returncode}; see {log.relative_to(DATA)}")
            if not path.exists():
                raise ValueError(f"{side} downloader produced no CSV; see {log.relative_to(DATA)}")
            record["raw"][side] = {"path": str(path.relative_to(DATA)), "sha256": sha256(path)}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            record["reason"] = str(exc)
            print(f"{window['id']} {pair}: unusable {exc}", flush=True)
            return record
    output = folder / "processed" / f"{pair}_SPOT.parquet"
    try:
        record["quality"] = convert(raw / f"{pair}_bid.csv", raw / f"{pair}_ask.csv", window, output)
        record["parquet"] = {"path": str(output.relative_to(DATA)), "sha256": sha256(output)}
        record["status"] = "usable"
    except (ValueError, KeyError, OSError) as exc:
        record["reason"] = str(exc)
    print(f"{window['id']} {pair}: {record['status']} {record['reason'] or ''}", flush=True)
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cli", type=Path, required=True)
    ap.add_argument("--retry-transport", action="store_true",
                    help="documented transport-only retry, before any scored run")
    args = ap.parse_args()
    spec = check_frozen()
    manifest_path = DATA / "manifest.json"
    if manifest_path.exists():
        if not args.retry_transport:
            raise SystemExit("acquisition manifest exists; refusing a second acquisition")
        from .protocol import DOCS
        import shutil
        old = json.loads(manifest_path.read_text())
        if (DOCS / "run_started.json").exists() or (DOCS / "results.json").exists():
            raise SystemExit("a scored run already started; transport retry refused")
        if not all(r["status"] == "unusable" for w in old["windows"] for r in w["pairs"]):
            raise SystemExit("transport retry requires the completely failed first attempt")
        if not (DOCS / "amendment-2026-11-15-transport.md").exists():
            raise SystemExit("transport amendment missing")
        if not (DOCS / "amendment-2026-11-15-http.md").exists():
            raise SystemExit("HTTP transport amendment missing")
        attempt = 1
        while (DATA / f"transport-attempt-{attempt}").exists():
            attempt += 1
        if attempt > 2:
            raise SystemExit("both documented acquisition retries have been exhausted")
        archive = DATA / f"transport-attempt-{attempt}"
        archive.mkdir(exist_ok=False)
        for window in old["windows"]:
            shutil.move(str(DATA / window["id"]), str(archive / window["id"]))
        shutil.move(str(manifest_path), str(archive / "manifest.json"))
    package = args.cli.resolve().parent.parent / "package.json"
    # npm bin resolves to package/dist/cli/index.js in the frozen release.
    package = next((p / "package.json" for p in args.cli.resolve().parents
                    if (p / "package.json").exists()), package)
    metadata = json.loads(package.read_text())
    if metadata.get("name") != spec["downloader"]["package"] or metadata.get("version") != spec["downloader"]["version"]:
        raise SystemExit("downloader package/version differs from registration")
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = {"preregistration_sha256": sha256(REGISTRATION),
                "started_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                "downloader": spec["downloader"], "windows": []}
    manifest["transport"] = "node:http, same datafeed host/path, 60s socket timeout; decoder unchanged; see dated amendments"
    # Parallel HTTP acquisition only; no detector evaluation occurs here.
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {(w["id"], p): pool.submit(download_pair, args.cli, w, p)
                 for w in spec["windows"] for p in w["pairs"]}
        for window in spec["windows"]:
            manifest["windows"].append({"id": window["id"], "pairs": [
                tasks[(window["id"], p)].result() for p in window["pairs"]]})
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
