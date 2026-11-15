"""One frozen evaluation of the acquired snapshot, plus reusable pure adapters."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from storm import equity
from storm.detector import run_detector
from storm.evaluate import (FALSE_AFTER, LINK_BEFORE, for_display, market_days, score,
                            v1_alarms_and_squalls)
from storm.features import as_ns
from storm.labels import STORM_COLUMNS, label_all

from .protocol import DATA, DOCS, check_frozen, registration_commit, save, sha256

EMPTY_CALENDAR = pd.DataFrame(columns=["time_utc", "event", "region", "source_url", "verified"])


def bars_from_raw(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Equity conversion without its demonstration-only November 9–13 date slice."""
    frame = raw.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    frame.index = as_ns(pd.DatetimeIndex(frame.index).tz_convert("UTC"))
    flagged = equity.bad_prints(frame)
    sessions = equity.session_ids(frame.index)
    bars = pd.DataFrame({"open": frame.open, "high": frame.high, "low": frame.low, "mid": frame.close,
                         "session": sessions, "bad_print": frame.index.isin(flagged).astype(int)},
                        index=frame.index)
    # Keep any out-of-hours source rows in raw storage/Tiger, but do not trade them.
    bars = bars[bars.session >= 0].copy()
    bars.attrs["bad_prints"] = list(bars.index[bars.bad_print == 1])
    return bars


def labels(feats: dict[str, pd.DataFrame], *, as_of: pd.Timestamp | None = None,
           bars: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Unchanged fifteen-minute labels within each session, using clean prices.

    USD_ is only an internal adapter to labels' FX-only usd_sign dispatcher: its
    +1 sign is the equity's own price direction. Strip it before returning rows.
    For stress snapshots a print is removed only after its next open is observed.
    """
    rows = []
    for sym, full in feats.items():
        part = full if as_of is None else full[full.index <= as_of]
        clean = part.bad_print.eq(0)
        if as_of is not None and bars is not None:
            raw = bars[sym]
            next_seen = pd.Series(raw.index, index=raw.index).shift(-1)
            known = next_seen.reindex(part.index).le(as_of)
            clean = clean | ~known
        part = part[clean]
        for _, session in part.groupby("session", sort=True):
            found = label_all({f"USD_{sym}": session}, EMPTY_CALENDAR)
            found["pair"] = sym
            found["storm_id"] = found.storm_id.str.replace(f"usd_{sym.lower()}-", f"{sym.lower()}-", regex=False)
            if not found.empty:
                rows.append(found)
    if not rows:
        return label_all({}, EMPTY_CALENDAR)
    return pd.concat(rows, ignore_index=True)[STORM_COLUMNS].sort_values(["onset_utc", "pair"]).reset_index(drop=True)


def trading_dates(feats: dict[str, pd.DataFrame]) -> list[int]:
    return sorted({int(s) for f in feats.values() for s in f.session.unique()})


def metrics(feats: dict, detections: dict, storms: pd.DataFrame) -> dict:
    if not feats:
        return {"status": "unavailable", "storms": 0}
    start = min(f.index.min() for f in feats.values())
    end = max(f.index.max() for f in feats.values()) + pd.Timedelta(minutes=1)
    alarms, squalls = v1_alarms_and_squalls(detections, start, end)
    days = len(trading_dates(feats))
    observed_days = market_days(feats, start, end)
    result = score(alarms, storms, {s: f.mid for s, f in feats.items()}, days, squalls)
    result.update(status="evaluated", trading_dates=trading_dates(feats), trading_days=days,
                  observed_days=observed_days, rate_denominator="distinct ET trading dates with observed bars",
                  false_alarms_per_trading_day=result["false_alarms_per_day"],
                  false_alarm_episodes_per_trading_day=result["false_alarm_episodes_per_day"],
                  false_alarms_per_observed_day=result["false_alarms"] / observed_days if observed_days else None,
                  false_alarm_episodes_per_observed_day=result["false_alarm_episodes"] / observed_days if observed_days else None)
    observed = sum(len(f) for f in feats.values())
    in_storm = sum(int(d.frame.state.eq(2).sum()) for d in detections.values())
    result.update(observed_ticker_minutes=observed, storm_state_minutes=in_storm,
                  storm_state_share_pct=100 * in_storm / observed if observed else None,
                  scheduled_watch_metrics=None)
    return result


def snapshot(data: Path = DATA) -> tuple[dict, dict, dict]:
    manifest = json.loads((data / "acquisition.json").read_text())
    if "completed_at_utc" not in manifest:
        raise ValueError("Acquisition incomplete")
    bars = {}
    for sym, info in manifest["tickers"].items():
        if info["status"] != "acquired":
            continue
        path = data / info["file"]
        if sha256(path) != info["sha256"]:
            raise ValueError(f"Acquisition hash mismatch: {sym}")
        bars[sym] = bars_from_raw(pd.read_parquet(path), sym)
    return manifest, bars, equity.equity_features(bars)


def evaluate(data: Path = DATA) -> dict:
    spec = check_frozen()
    marker = DOCS / "run_started.json"
    if marker.exists():
        raise FileExistsError("Frozen detector has already been run; reuse the saved evaluation")
    manifest, bars, feats = snapshot(data)
    save(marker, {"started_at_utc": datetime.now(timezone.utc).isoformat(),
                  "registration_commit": registration_commit(),
                  "acquisition_sha256": sha256(data / "acquisition.json")})
    detections = {s: run_detector(f, EMPTY_CALENDAR, spec["config"], exposure=1.0)
                  for s, f in feats.items()}
    storms = labels(feats)
    individual, alerts, ticker_rows = [], [], {}
    for sym in spec["tickers"]:
        info = manifest["tickers"][sym]
        if sym not in feats:
            ticker_rows[sym] = {"status": "unavailable", "in_sample": sym == "NVDA", "raw_rows": 0, "storms": 0}
            continue
        feat, res, mine = feats[sym], detections[sym], storms[storms.pair == sym]
        m = metrics({sym: feat}, {sym: res}, mine)
        m.update(in_sample=sym == "NVDA", raw_rows=info["rows"], in_hours_rows=len(feat),
                 excluded_out_of_hours=info["rows"] - len(feat),
                 bad_prints=[str(t) for t in bars[sym].attrs["bad_prints"]],
                 bad_print_count=int(feat.bad_print.sum()),
                 warmup_undefined_sd=int(feat.sd_24h.isna().sum()),
                 sd_defined_minutes=int(feat.sd_24h.notna().sum()),
                 risk_defined_minutes=int(res.frame.risk.notna().sum()),
                 first_utc=info["first_utc"], last_utc=info["last_utc"])
        per_storm = {p["storm_id"]: p for p in m["per_storm"]}
        for row in mine.to_dict("records"):
            row.update(per_storm[row["storm_id"]])
            row["miss"] = not row["caught"]
            individual.append(row)
        for alarm, clear in res.storm_alarms():
            near = ((mine.onset_utc - LINK_BEFORE <= alarm) & (alarm <= mine.end_utc + FALSE_AFTER)).any()
            alerts.append({"ticker": sym, "alarm_utc": alarm, "clear_utc": clear,
                           "false_alarm": not bool(near), "risk": float(res.frame.loc[alarm, "risk"])})
        ticker_rows[sym] = m
        feat.to_parquet(data / f"{sym}_features.parquet")
        res.frame.to_parquet(data / f"{sym}_detector.parquet")
    pools = {}
    for name, syms in {"new_tickers": [s for s in feats if s != "NVDA"],
                       "nvda_in_sample": [s for s in feats if s == "NVDA"],
                       "all_descriptive": list(feats)}.items():
        pools[name] = metrics({s: feats[s] for s in syms}, {s: detections[s] for s in syms},
                              storms[storms.pair.isin(syms)])
    ranking = sorted([s for s in individual if s["pair"] != "NVDA"],
                     key=lambda s: (-abs(s["move_bp"]), s["onset_utc"], s["pair"]))[:3]
    shocks = {}
    for sym, b in bars.items():
        try:
            shocks[sym] = equity.close_to_low(b)
        except ValueError:
            shocks[sym] = None
    result = {"schema_version": 1, "status": "evaluated", "preregistration_commit": registration_commit(),
              "base_commit": spec["base_commit"], "config": spec["config"],
              "code_fingerprint": spec["code_fingerprint"], "frozen_sources": spec["source_sha256"],
              "acquisition": manifest, "per_ticker": ticker_rows, "pooled": pools,
              "storms": individual, "detections": alerts, "replay_selection": ranking,
              "november_11_close_to_12_low": shocks, "replays": [], "ai": [], "tiger": None,
              "verification": {}, "completed_evaluation_utc": datetime.now(timezone.utc).isoformat()}
    save(data / "evaluation.json", result)
    save(DOCS / "results.json", result)
    print(json.dumps(for_display({"pooled": pools, "ranking": ranking}), default=str, indent=2))
    return result


if __name__ == "__main__":
    evaluate()
