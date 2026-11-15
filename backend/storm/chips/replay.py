"""Parameter adapter for the frozen equity builder; source and globals stay intact."""
from __future__ import annotations

import json
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pandas as pd

from storm import equity
from storm.detector import run_detector
from storm.export import default_window, storm_alarm_fields, write_bundle, write_index
from storm.validate import validate_bundle, validate_index

from .evaluate import EMPTY_CALENDAR, bars_from_raw, labels
from .protocol import DATA, DOCS, MAIN, check_frozen, save, sha256


def selected_storm(row: dict) -> SimpleNamespace:
    return SimpleNamespace(**{k: pd.Timestamp(v) if k.endswith("_utc") and v is not None else v
                              for k, v in row.items()})


def build(run: equity.EquityRun, storm: SimpleNamespace) -> tuple[dict, dict]:
    """Bind parameters in a copied function namespace, never patch shared modules.

    close/low keys are the builder's interface; values here are the registered
    label's close-price onset and extremum, rather than NVDA's fixed overnight low.
    """
    sym = storm.pair
    feat = run.feats[sym]
    res = run_detector(feat, EMPTY_CALENDAR, run.cfg, exposure=1.0)
    start, end = default_window(feat, storm, res.events)
    start = min(start, storm.first_onset_utc)
    end = max(end, storm.trough_utc, storm.end_utc)
    m = {"close_utc": storm.onset_utc, "close": storm.onset_mid,
         "low_utc": storm.trough_utc, "low": storm.trough_mid, "move_bp": storm.move_bp}

    def stress(_bars, path, price, book, i, as_of):
        candidates = labels(run.feats, as_of=as_of, bars=run.bars)
        candidates = candidates[candidates.trough_utc < as_of]
        q, cash, p = float(path.qty[sym][i]), float(path.cash["USD"][i]), float(price[i])
        rows = []
        for s in candidates.itertuples():
            shocked = p * (1 + s.move_bp / 1e4)
            equity_after = cash + q * shocked
            rows.append({"scenario": f"{s.pair} {s.onset_utc:%d %b %H:%M} UTC: {s.move_bp / 100:+.1f}%, applied to {sym}",
                         "pnl_usd": round(q * (shocked - p)),
                         "margin_call": bool(q and equity_after < book["maintenance_margin"] * abs(q) * shocked)})
        return rows

    def alarm_fields(_storm, alarms, mid, frame_of):
        return storm_alarm_fields(storm, alarms, mid, frame_of)

    namespace = {**vars(equity), "SHIP_SYMBOL": sym, "SYMBOLS": (sym,),
                 "BOOK": {**equity.BOOK, "symbol": sym}, "STORM_ID": storm.storm_id,
                 "TITLE": f"{sym}, {storm.onset_utc:%d %B %Y}",
                 "close_to_low": lambda _bars, until=end: dict(m),
                 "stress_test": stress, "storm_alarm_fields": alarm_fields}
    builder = FunctionType(equity.build_bundle.__code__, namespace, equity.build_bundle.__name__,
                           equity.build_bundle.__defaults__, equity.build_bundle.__closure__)
    bundle, summary = builder(run, start, end)
    bundle["storm"]["first_onset_i"] = int((storm.first_onset_utc - start) / pd.Timedelta(minutes=1))
    bundle["storm"]["label"] = f"{storm.move_bp / 100:+.1f}% in {storm.duration_min} min"
    summary["adapter"] = "frozen equity builder with isolated symbol/book/label/stress parameters"
    return bundle, summary


def prepare(data: Path = DATA) -> list[dict]:
    spec = check_frozen()
    result = json.loads((DOCS / "results.json").read_text())
    manifest = result["acquisition"]
    bars, feats = {}, {}
    for sym, entry in manifest["tickers"].items():
        if entry["status"] != "acquired":
            continue
        if sha256(data / entry["file"]) != entry["sha256"]:
            raise ValueError(f"Changed raw bars for {sym}")
        bars[sym] = bars_from_raw(pd.read_parquet(data / entry["file"]), sym)
        feats[sym] = pd.read_parquet(data / f"{sym}_features.parquet")
    run = equity.EquityRun(bars, feats, spec["config"])
    rows = []
    for selected in result["replay_selection"]:
        storm = selected_storm(selected)
        bundle, summary = build(run, storm)
        # Reports are attached by the separate bounded live crew command.
        path = write_bundle(bundle, data / "bundles")
        errors = validate_bundle(bundle)
        # A null report is permitted during construction; complete bundles are checked again.
        if errors:
            raise ValueError(f"{storm.storm_id}: {errors}")
        rows.append({"storm_id": storm.storm_id, "ticker": storm.pair,
                     "onset_utc": storm.onset_utc, "trough_utc": storm.trough_utc,
                     "move_bp": storm.move_bp, "caught": storm.caught,
                     "alarm_utc": storm.alarm_utc, "move_ahead_pct": storm.move_ahead_pct,
                     "n": bundle["n"], "filled_open_minutes": summary["filled_minutes"],
                     "stress_scenarios": len(bundle["stress"]), "fills": summary["fills"],
                     "ships": summary["ships"], "validator_errors": errors,
                     "staged_file": path.name})
        print(f"staged {storm.storm_id}, move {storm.move_bp:+.1f} bp, caught={storm.caught}", flush=True)
    check_frozen()  # verifies that parameter binding did not mutate the shared code
    save(DOCS / "replays.json", rows)
    return rows


def publish(out: Path = MAIN / "web/public/bundles", data: Path = DATA) -> dict:
    """Use the existing index writer, preserving every entry and its current order."""
    result = json.loads((DOCS / "results.json").read_text())
    old_path = out / "index.json"
    old = json.loads(old_path.read_text())
    previous = [(json.loads((out / e["file"]).read_text()), e["file"]) for e in old["storms"]]
    new = []
    for selected in result["replay_selection"]:
        name = selected["storm_id"] + ".json"
        bundle = json.loads((data / "bundles" / name).read_text())
        if bundle["report"] is None:
            raise ValueError("Live report required before publication")
        errors = validate_bundle(bundle)
        if errors:
            raise ValueError(f"{name}: {errors}")
        if any(e["file"] == name for e in old["storms"]):
            raise ValueError(f"Refusing to replace an existing replay: {name}")
        new.append((bundle, name))
    # Refuse concurrent index changes; caller can retry against the latest complete index.
    if json.loads(old_path.read_text()) != old:
        raise RuntimeError("Index changed during preparation")
    for bundle, _ in new:
        write_bundle(bundle, out)
    write_index(out, previous + new, old["metrics"])
    after = json.loads(old_path.read_text())
    assert after["storms"][:len(old["storms"])] == old["storms"]
    assert after["metrics"] == old["metrics"]
    assert validate_index(after) == []
    evidence = {"existing_entries_preserved": len(previous), "new_entries": len(new),
                "existing_order_preserved": True, "metrics_preserved": True,
                "index_validator_errors": [],
                "bundle_sha256": {name: sha256(out / name) for _, name in new}}
    save(DOCS / "publication.json", evidence)
    return evidence


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.publish:
        print(json.dumps(publish(), indent=2))
    else:
        prepare()
