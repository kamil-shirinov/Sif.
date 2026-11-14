"""Load SGX's raw zips into one parquet file per pair and tenor.

    python -m storm.ingest [--raw DIR] [--out DIR]

Each zip holds one CSV per trading day. Output: data/processed/<PAIR>_<TENOR>.parquet
(tenor SPOT for spot). Spot keeps every column; forwards keep timestamp,
settlement_date, close_mid, close_mid_fp and close_mid_all_in. Timestamps are UTC.

The quality report lists duplicate timestamps and every gap over 5 minutes that is
not the weekend close (Friday ~21:00 UTC to Sunday ~19:00 UTC).
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from .paths import PROCESSED_DIR, RAW_DIR

MAX_GAP = pd.Timedelta(minutes=5)
FORWARD_COLUMNS = ["timestamp", "settlement_date", "close_mid", "close_mid_fp", "close_mid_all_in"]

_NAME = re.compile(
    r"^(?P<pair>[A-Z]{6})_[A-Z]{3}_(?P<kind>SPOT|FORWARD)_(?P<tenor>[0-9A-Z]+)_\d+_\d{8}-\d{8}\.zip$"
)


@dataclass
class Gap:
    after_utc: str
    before_utc: str
    minutes: float


@dataclass
class ZipReport:
    file: str
    pair: str
    tenor: str
    rows: int
    first_utc: str
    last_utc: str
    days: int
    duplicates: int
    gaps: list[Gap] = field(default_factory=list)


def parse_name(name: str) -> tuple[str, str]:
    """`USDJPY_USD_FORWARD_1M_1000000_20260701-20260831.zip` -> ("USDJPY", "1M")."""
    m = _NAME.match(Path(name).name)
    if not m:
        raise ValueError(f"unrecognised SGX zip name: {name}")
    return m["pair"], ("SPOT" if m["kind"] == "SPOT" else m["tenor"])


def is_weekend_close(after: pd.Timestamp, before: pd.Timestamp) -> bool:
    """True when a gap is the normal FX weekend: from Friday evening to Sunday evening UTC."""
    return (
        after.weekday() == 4
        and after.hour >= 20
        and before.weekday() == 6
        and (before - after) <= pd.Timedelta(days=2, hours=2)
    )


def find_gaps(ts: pd.Series, max_gap: pd.Timedelta = MAX_GAP) -> list[Gap]:
    ts = ts.sort_values().reset_index(drop=True)
    dt = ts.diff()
    gaps = []
    for i in dt.index[dt > max_gap]:
        after, before = ts[i - 1], ts[i]
        if not is_weekend_close(after, before):
            gaps.append(Gap(str(after), str(before), dt[i].total_seconds() / 60))
    return gaps


def read_zip(path: Path) -> tuple[pd.DataFrame, ZipReport]:
    """Read every daily CSV in one zip. Returns the cleaned frame and its quality report."""
    pair, tenor = parse_name(path.name)
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith(".csv"))
        if not names:
            raise ValueError(f"{path.name}: no CSV files inside")
        frames = []
        for n in names:
            with z.open(n) as f:
                frames.append(pd.read_csv(f))
    df = pd.concat(frames, ignore_index=True)
    if tenor != "SPOT":
        missing = [c for c in FORWARD_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{path.name}: missing columns {missing}")
        df = df[FORWARD_COLUMNS]

    # pandas 3 parses to microseconds; every module downstream assumes nanoseconds.
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.as_unit("ns")
    df["settlement_date"] = pd.to_datetime(df["settlement_date"], format="%Y-%m-%d")
    df = df.sort_values("timestamp", kind="stable")
    dup_mask = df["timestamp"].duplicated(keep="first")
    duplicates = int(dup_mask.sum())
    df = df[~dup_mask].reset_index(drop=True)

    report = ZipReport(
        file=path.name,
        pair=pair,
        tenor=tenor,
        rows=len(df),
        first_utc=str(df["timestamp"].iloc[0]),
        last_utc=str(df["timestamp"].iloc[-1]),
        days=int(df["timestamp"].dt.normalize().nunique()),
        duplicates=duplicates,
        gaps=find_gaps(df["timestamp"]),
    )
    return df, report


def ingest(raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR) -> list[ZipReport]:
    zips = sorted(raw_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"no zips in {raw_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in zips:
        df, rep = read_zip(path)
        df.to_parquet(out_dir / f"{rep.pair}_{rep.tenor}.parquet", index=False)
        reports.append(rep)
    (out_dir / "ingest_report.json").write_text(
        json.dumps([asdict(r) for r in reports], indent=2)
    )
    return reports


def print_report(reports: list[ZipReport], max_gaps_shown: int = 3) -> None:
    print(f"{'pair':7} {'tenor':5} {'rows':>6} {'days':>4} {'dups':>4} {'gaps>5m':>7}  first -> last (UTC)")
    for r in reports:
        print(
            f"{r.pair:7} {r.tenor:5} {r.rows:6d} {r.days:4d} {r.duplicates:4d} {len(r.gaps):7d}"
            f"  {r.first_utc[:16]} -> {r.last_utc[:16]}"
        )
    for r in reports:
        for g in r.gaps[:max_gaps_shown]:
            print(f"  gap {r.pair}_{r.tenor}: {g.after_utc[:16]} -> {g.before_utc[:16]} ({g.minutes:.0f} min)")
        if len(r.gaps) > max_gaps_shown:
            print(f"  gap {r.pair}_{r.tenor}: ... {len(r.gaps) - max_gaps_shown} more in ingest_report.json")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=PROCESSED_DIR)
    args = ap.parse_args(argv)
    reports = ingest(args.raw, args.out)
    print_report(reports)
    print(f"wrote {len(reports)} parquet files to {args.out}")


if __name__ == "__main__":
    main()
