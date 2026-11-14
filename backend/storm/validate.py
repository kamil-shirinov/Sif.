"""Validate a replay bundle (or index.json) against contracts/replay_bundle.md.

    python -m storm.validate <file> [<file> ...]

Exit code 0 when every file is valid, 1 otherwise. Checks keys (no missing, no extra),
types, enum values, index ranges, and that every series has length n.

Also accepts the optional additions (still schema_version 1): ships.<name>.restore_i
(int or null); event types squall, fair_wind, cut and restore; watch events' `event`;
storm.event and storm.event_i (scheduled storms only, both or neither); and
report.inspector {verdict: ok | flag, issues: [str]}; source values scenario (a what-if
bundle resized from a real storm) and yahoo (Yahoo Finance bars); series market_open (int
0 or 1 per frame); and index metrics.watch_precision (0..1 or null).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

TOP_KEYS = {
    "schema_version": int, "storm_id": str, "title": str, "symbol": str, "asset_class": str,
    "source": str, "book_is_synthetic": bool, "t0": int, "step_s": int, "n": int,
    "storm": dict, "series": dict, "ships": dict, "events": list, "exposure": dict,
    "stress": list, "report": (dict, type(None)),
}
FLOAT_SERIES = ("open", "high", "low", "mid", "spread_bp", "vol_ratio", "risk",
                "prepared_equity", "unprepared_equity")
INT_SERIES = {"state": {0, 1, 2}, "jump": {0, 1}}
OPTIONAL_INT_SERIES = {"market_open": {0, 1}}
SOURCES = ("sgx", "synthetic", "scenario", "yahoo")
STORM_KEYS = {"onset_i": int, "trough_i": int, "move_bp": "num", "kind": str, "label": str}
STORM_OPTIONAL = {"event": "str", "event_i": "int"}
SHIP_KEYS = {"label": str, "start_equity_usd": "num", "margin_call_i": "int?", "cut_i": "int?",
             "cut_fraction": "num"}
SHIP_OPTIONAL = {"restore_i": "int?"}
EVENT_TYPES = {"watch", "alarm", "margin_call", "all_clear", "squall", "fair_wind", "cut", "restore"}
EVENT_EXTRA = {"watch": {"at_i": "int"}, "alarm": {"move_ahead_pct": "num?"},
               "margin_call": {"ship": "str"}, "all_clear": {}, "squall": {}, "fair_wind": {},
               "cut": {}, "restore": {}}
EVENT_OPTIONAL = {"watch": {"event": "str"}}
EXPOSURE_KEYS = {"as_of_i": int, "positions": list, "net_usd_by_ccy": dict,
                 "leverage": "num?", "margin_buffer_pct": "num?"}
REPORT_KEYS = {"text": str, "verified": bool, "unverified_numbers": list, "model": str}
REPORT_OPTIONAL = {"inspector": dict}
INDEX_STORM_KEYS = {"storm_id": str, "title": str, "symbol": str, "asset_class": str,
                    "kind": str, "move_bp": "num", "file": str}
METRIC_KEYS = {"split": str, "storms": int, "caught": int, "median_move_ahead_pct": "num?",
               "false_alarms_per_day": "num?"}
METRIC_OPTIONAL = {"watch_precision": "num?"}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _type_ok(v, spec) -> bool:
    if spec == "num":
        return _is_num(v)
    if spec == "num?":
        return v is None or _is_num(v)
    if spec in ("int", int):
        return _is_int(v)
    if spec == "int?":
        return v is None or _is_int(v)
    if spec in ("str", str):
        return isinstance(v, str)
    if spec is bool:
        return isinstance(v, bool)
    if isinstance(spec, tuple):
        return isinstance(v, spec)
    return isinstance(v, spec) and not (spec is int and isinstance(v, bool))


def _check_obj(obj, spec: dict, where: str, errors: list[str], strict: bool = True,
               optional: dict | None = None) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{where}: expected object")
        return False
    optional = optional or {}
    for k, t in spec.items():
        if k not in obj:
            errors.append(f"{where}.{k}: missing")
        elif not _type_ok(obj[k], t):
            errors.append(f"{where}.{k}: bad type or value {obj[k]!r}")
    for k, t in optional.items():
        if k in obj and not _type_ok(obj[k], t):
            errors.append(f"{where}.{k}: bad type or value {obj[k]!r}")
    if strict:
        for k in obj.keys() - spec.keys() - optional.keys():
            errors.append(f"{where}.{k}: not in the contract")
    return True


def _check_i(v, n: int, where: str, errors: list[str]) -> None:
    if _is_int(v) and not 0 <= v < n:
        errors.append(f"{where}: frame {v} outside 0..{n - 1}")


def validate_bundle(b: dict) -> list[str]:
    errors: list[str] = []
    if not _check_obj(b, TOP_KEYS, "bundle", errors):
        return errors
    n = b.get("n")
    if b.get("schema_version") != 1:
        errors.append("schema_version: must be 1")
    if b.get("step_s") != 60:
        errors.append("step_s: must be 60")
    if b.get("book_is_synthetic") is not True:
        errors.append("book_is_synthetic: must be true")
    if b.get("source") not in SOURCES:
        errors.append(f"source: must be one of {', '.join(SOURCES)}")
    if b.get("asset_class") not in ("fx", "equity", "crypto"):
        errors.append("asset_class: must be fx, equity or crypto")
    if not _is_int(n) or n <= 0:
        errors.append("n: must be a positive int")
        return errors

    series = b.get("series")
    if isinstance(series, dict):
        expected = set(FLOAT_SERIES) | set(INT_SERIES)
        ints = {**INT_SERIES, **OPTIONAL_INT_SERIES}
        for k in expected - series.keys():
            errors.append(f"series.{k}: missing")
        for k in series.keys() - expected - OPTIONAL_INT_SERIES.keys():
            errors.append(f"series.{k}: not in the contract")
        for k, arr in series.items():
            if not isinstance(arr, list):
                errors.append(f"series.{k}: not an array")
                continue
            if len(arr) != n:
                errors.append(f"series.{k}: length {len(arr)} != n {n}")
            if k in FLOAT_SERIES:
                bad = [i for i, v in enumerate(arr) if not _is_num(v)]
                if bad:
                    errors.append(f"series.{k}: non-numeric at frames {bad[:5]}")
            elif k in ints:
                bad = [i for i, v in enumerate(arr) if not _is_int(v) or v not in ints[k]]
                if bad:
                    errors.append(f"series.{k}: values outside {sorted(ints[k])} at frames {bad[:5]}")
        risk = series.get("risk")
        if isinstance(risk, list) and any(_is_num(v) and not 0 <= v <= 1 for v in risk):
            errors.append("series.risk: values outside 0..1")

    storm = b.get("storm")
    if _check_obj(storm, STORM_KEYS, "storm", errors, optional=STORM_OPTIONAL):
        _check_i(storm.get("onset_i"), n, "storm.onset_i", errors)
        _check_i(storm.get("trough_i"), n, "storm.trough_i", errors)
        _check_i(storm.get("event_i"), n, "storm.event_i", errors)
        if storm.get("kind") not in ("scheduled", "unscheduled"):
            errors.append("storm.kind: must be scheduled or unscheduled")
        if ("event" in storm) != ("event_i" in storm):
            errors.append("storm.event and storm.event_i: give both or neither")
        if "event" in storm and storm.get("kind") != "scheduled":
            errors.append("storm.event: only a scheduled storm has an event")

    ships = b.get("ships")
    if isinstance(ships, dict):
        if set(ships) != {"prepared", "unprepared"}:
            errors.append(f"ships: keys must be prepared and unprepared, got {sorted(ships)}")
        for name, ship in ships.items():
            if _check_obj(ship, SHIP_KEYS, f"ships.{name}", errors, optional=SHIP_OPTIONAL):
                _check_i(ship.get("margin_call_i"), n, f"ships.{name}.margin_call_i", errors)
                _check_i(ship.get("cut_i"), n, f"ships.{name}.cut_i", errors)
                _check_i(ship.get("restore_i"), n, f"ships.{name}.restore_i", errors)
                ci, ri = ship.get("cut_i"), ship.get("restore_i")
                if _is_int(ri) and (not _is_int(ci) or ri < ci):
                    errors.append(f"ships.{name}.restore_i: must come after cut_i")
                cf = ship.get("cut_fraction")
                if _is_num(cf) and not 0 <= cf <= 1:
                    errors.append(f"ships.{name}.cut_fraction: outside 0..1")

    for k, ev in enumerate(b.get("events") or []):
        where = f"events[{k}]"
        t = ev.get("type") if isinstance(ev, dict) else None
        if t not in EVENT_TYPES:
            errors.append(f"{where}.type: {t!r} not in {sorted(EVENT_TYPES)}")
            continue
        _check_obj(ev, {"i": int, "type": str, "text": str, **EVENT_EXTRA[t]}, where, errors,
                   optional=EVENT_OPTIONAL.get(t))
        _check_i(ev.get("i"), n, f"{where}.i", errors)
        if t == "watch":
            _check_i(ev.get("at_i"), n, f"{where}.at_i", errors)
        if t == "margin_call" and ev.get("ship") not in ("prepared", "unprepared"):
            errors.append(f"{where}.ship: must be prepared or unprepared")

    exp = b.get("exposure")
    if _check_obj(exp, EXPOSURE_KEYS, "exposure", errors):
        _check_i(exp.get("as_of_i"), n, "exposure.as_of_i", errors)
        for k, p in enumerate(exp.get("positions") or []):
            _check_obj(p, {"instrument": str, "side": str, "notional_usd": "num"},
                       f"exposure.positions[{k}]", errors)
        for ccy, v in (exp.get("net_usd_by_ccy") or {}).items():
            if not _is_num(v):
                errors.append(f"exposure.net_usd_by_ccy.{ccy}: not a number")

    for k, s in enumerate(b.get("stress") or []):
        _check_obj(s, {"scenario": str, "pnl_usd": "num", "margin_call": bool}, f"stress[{k}]", errors)

    if isinstance(b.get("report"), dict):
        _check_obj(b["report"], REPORT_KEYS, "report", errors, optional=REPORT_OPTIONAL)
        insp = b["report"].get("inspector")
        if isinstance(insp, dict) and _check_obj(insp, {"verdict": str, "issues": list}, "report.inspector", errors):
            if insp.get("verdict") not in ("ok", "flag"):
                errors.append("report.inspector.verdict: must be ok or flag")
            if not all(isinstance(x, str) for x in insp.get("issues") or []):
                errors.append("report.inspector.issues: must be strings")
        if not all(isinstance(x, str) for x in b["report"].get("unverified_numbers") or []):
            errors.append("report.unverified_numbers: must be strings")
    return errors


def validate_index(ix: dict) -> list[str]:
    errors: list[str] = []
    if not _check_obj(ix, {"schema_version": int, "storms": list, "metrics": (dict, type(None))},
                      "index", errors):
        return errors
    if ix.get("schema_version") != 1:
        errors.append("schema_version: must be 1")
    for k, s in enumerate(ix.get("storms") or []):
        _check_obj(s, INDEX_STORM_KEYS, f"storms[{k}]", errors)
    if isinstance(ix.get("metrics"), dict):
        _check_obj(ix["metrics"], METRIC_KEYS, "metrics", errors, optional=METRIC_OPTIONAL)
        wp = ix["metrics"].get("watch_precision")
        if _is_num(wp) and not 0 <= wp <= 1:
            errors.append("metrics.watch_precision: outside 0..1")
    return errors


def validate_file(path: Path) -> list[str]:
    try:
        obj = json.loads(Path(path).read_text(), parse_constant=lambda c: float(c))
    except (OSError, ValueError) as e:
        return [f"cannot read JSON: {e}"]
    if isinstance(obj, dict) and "storms" in obj and "series" not in obj:
        return validate_index(obj)
    return validate_bundle(obj)


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print("usage: python -m storm.validate <file> [<file> ...]")
        return 2
    ok = True
    for p in paths:
        errors = validate_file(Path(p))
        if errors:
            ok = False
            print(f"INVALID {p}")
            for e in errors:
                print(f"  {e}")
        else:
            print(f"OK {p}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
