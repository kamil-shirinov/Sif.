"""Offline guardrails for the preregistration, adapters and report artifact."""
import copy
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from storm.detector import load_calendar, run_detector
from storm.evaluate import for_display, score
from storm.features import pair_features
from storm.oos.acquire import convert
from storm.oos.protocol import DOCS, REGISTRATION, canonical, check_registration, registration, sha256
from storm.oos.report import render
from storm.oos.run import (first_difference, load_window_features, policy_totals,
                           window_labels, evaluate, file_inventory)
from storm.oos.verify import frozen_checkout


def spot():
    idx = pd.date_range("2024-01-01", periods=4320, freq="min", tz="UTC")
    mid = 1.0 + np.sin(np.arange(len(idx)) * 0.51) * 0.00001
    mid[4000:] *= 0.97
    frame = pd.DataFrame({"timestamp": idx})
    for col in ("open", "high", "low", "close"):
        frame[col + "_mid"] = mid
        frame[col + "_bid"] = mid - 0.000005
        frame[col + "_ask"] = mid + 0.000005
    return frame


def test_registration_remains_immutable_without_pinning_current_main():
    spec = check_registration()
    assert spec["config"]["w_comove"] == 0
    assert spec["config"]["storm_minutes"] == 2
    assert spec["config_sha256"] == hashlib.sha256(canonical(spec["config"]).encode()).hexdigest()
    assert len(spec["windows"]) == 8
    assert sum(len(w["pairs"]) for w in spec["windows"]) == 14


@pytest.fixture(scope="module")
def registered_checkout():
    with frozen_checkout() as root:
        yield root


def snapshot_python(root, code):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-c", code], cwd=root / "backend", env=env,
                          capture_output=True, text=True)


def test_registered_core_and_original_wrapper_still_match(registered_checkout):
    result = snapshot_python(registered_checkout,
                             "from storm.oos.protocol import check_frozen; check_frozen()")
    assert result.returncode == 0, result.stderr


def test_core_constant_change_in_registered_core_is_refused(registered_checkout):
    result = snapshot_python(registered_checkout,
                             "import storm.labels; storm.labels.MIN_MOVE_BP = 31.0; "
                             "from storm.oos.protocol import check_frozen; check_frozen()")
    assert result.returncode != 0
    assert "frozen core code fingerprint mismatch" in result.stderr


def test_cross_adapter_preserves_price_labels_and_alarm_timing(tmp_path, monkeypatch):
    import storm.oos.run as runner
    monkeypatch.setattr(runner, "DATA", tmp_path)
    folder = tmp_path / "cross" / "processed"
    folder.mkdir(parents=True)
    bars = spot()
    bars.to_parquet(folder / "EURCHF_SPOT.parquet", index=False)
    cross = load_window_features({"id": "cross"}, [{"pair": "EURCHF", "status": "usable"}])
    usd = pair_features(bars, "USDJPY")
    usd["comove"] = 0
    cfg = registration()["config"]
    calendar = load_calendar()
    expected = run_detector(usd, calendar, cfg)
    actual = run_detector(cross["EURCHF"], calendar, cfg)
    pd.testing.assert_frame_equal(expected.frame, actual.frame)
    assert expected.storm_alarms() == actual.storm_alarms()
    left, right = window_labels({"USDJPY": usd}, calendar), window_labels(cross, calendar)
    assert len(right) > 0
    for column in ("onset_utc", "first_onset_utc", "trough_utc", "move_bp", "duration_min"):
        assert left[column].tolist() == right[column].tolist()
    assert right["pair"].eq("EURCHF").all()
    assert right["usd_move_bp"].isna().all()
    assert cross["EURCHF"]["usd_z"].isna().all()
    alarms = actual.storm_alarms()
    result = score({"EURCHF": alarms}, right, {"EURCHF": cross["EURCHF"]["mid"]}, 1)
    assert result["storms"] > 0


def sides(tmp_path):
    bars = spot()
    for side in ("bid", "ask"):
        raw = pd.DataFrame({"timestamp": bars["timestamp"].astype("int64") // 1_000_000})
        for col in ("open", "high", "low", "close"):
            raw[col] = bars[col + "_" + side]
        raw["volume"] = 1.0
        raw.to_csv(tmp_path / (side + ".csv"), index=False)
    return {"download_start": "2024-01-01", "start": "2024-01-03", "end_exclusive": "2024-01-04"}


def test_conversion_preserves_real_gaps_and_ingest_schema(tmp_path):
    window = sides(tmp_path)
    ask = pd.read_csv(tmp_path / "ask.csv")
    ask.drop(index=[3000]).to_csv(tmp_path / "ask.csv", index=False)
    quality = convert(tmp_path / "bid.csv", tmp_path / "ask.csv", window, tmp_path / "out.parquet")
    out = pd.read_parquet(tmp_path / "out.parquet")
    assert quality["unmatched_bid"] == 1
    assert quality["evaluation_rows"] == 1439
    assert quality["warmup_rows"] == 2880
    assert quality["largest_gap_minutes"] == 2
    assert str(out["timestamp"].dtype) == "datetime64[ns, UTC]"
    assert "settlement_date" in out
    assert len(out) == 4319  # the absent bar is not interpolated
    feat = pair_features(out, "EURUSD")
    assert np.isnan(feat["ret_bp"].loc[pd.Timestamp("2024-01-03 02:01", tz="UTC")])


def test_zero_volume_placeholders_are_never_observed_minutes(tmp_path):
    window = sides(tmp_path)
    for side in ("bid", "ask"):
        path = tmp_path / (side + ".csv")
        raw = pd.read_csv(path)
        raw.loc[3000:3010, "volume"] = 0
        raw.to_csv(path, index=False)
    quality = convert(tmp_path / "bid.csv", tmp_path / "ask.csv", window, tmp_path / "out.parquet")
    assert quality["evaluation_rows"] == 1429
    assert quality["largest_gap_minutes"] == 12
    # A download with no volume cannot certify exclusion of source placeholders.
    raw.drop(columns="volume").to_csv(tmp_path / "ask.csv", index=False)
    with pytest.raises(ValueError, match="missing columns.*volume"):
        convert(tmp_path / "bid.csv", tmp_path / "ask.csv", window, tmp_path / "out.parquet")


@pytest.mark.parametrize("damage", ["duplicate", "crossed", "nonfinite", "bad_ohlc", "coverage", "warmup"])
def test_broken_source_is_rejected_without_price_outlier_filter(tmp_path, damage):
    window = sides(tmp_path)
    bid = pd.read_csv(tmp_path / "bid.csv")
    if damage == "duplicate":
        bid = pd.concat([bid, bid.iloc[:1]])
    elif damage == "crossed":
        for col in ("open", "high", "low", "close"):
            bid.loc[1000, col] += 1
    elif damage == "nonfinite":
        bid.loc[1000, "close"] = np.nan
    elif damage == "bad_ohlc":
        bid.loc[1000, "high"] = 0.5
    elif damage == "coverage":
        bid = bid.iloc[:3000]
    elif damage == "warmup":
        bid = bid.iloc[2500:]
    bid.to_csv(tmp_path / "bid.csv", index=False)
    with pytest.raises(ValueError):
        convert(tmp_path / "bid.csv", tmp_path / "ask.csv", window, tmp_path / "out.parquet")


def test_independent_books_do_not_add_drawdowns():
    def window(equity, dd):
        path = {"final_equity_usd": equity, "max_drawdown_usd": dd, "max_drawdown_pct": dd / 10000,
                "spread_cost_usd": 10.0, "fills": 2, "margin_calls": 0, "cuts": 1, "restores": 1}
        return {"policy": {"status": "supported", "result": {"prepared": path, "unprepared": path}}}
    totals = policy_totals([window(900000, 100000), window(1050000, 50000)])
    assert totals["independent_reset_books"] == 2
    assert totals["prepared"]["pnl_usd"] == -50000
    assert totals["prepared"]["max_window_drawdown_usd"] == 100000
    assert totals["prepared"]["median_window_max_drawdown_usd"] == 75000


def test_joint_windows_pool_storms_and_use_union_days(tmp_path, monkeypatch):
    import storm.oos.run as runner
    monkeypatch.setattr(runner, "DATA", tmp_path)
    windows = [
        {"id": "synthetic-event", "name": "synthetic event", "group": "events", "start": "2024-01-03",
         "end_exclusive": "2024-01-04", "download_start": "2024-01-01", "pairs": ["USDJPY", "EURCHF"]},
        {"id": "synthetic-ordinary", "name": "synthetic ordinary", "group": "ordinary", "start": "2024-01-10",
         "end_exclusive": "2024-01-11", "download_start": "2024-01-08", "pairs": ["EURUSD", "GBPUSD"]},
    ]
    manifest = {"windows": []}
    for w in windows:
        folder = tmp_path / w["id"] / "processed"
        folder.mkdir(parents=True)
        records = []
        for pair in w["pairs"]:
            rec = {"pair": pair, "status": "usable", "reason": None}
            if pair == "GBPUSD":
                rec.update(status="unusable", reason="synthetic missing feed")
            else:
                bars = spot()
                if w["group"] == "ordinary":
                    bars["timestamp"] += pd.Timedelta(days=7)
                bars.to_parquet(folder / f"{pair}_SPOT.parquet", index=False)
            records.append(rec)
        manifest["windows"].append({"id": w["id"], "pairs": records})
    exact = evaluate({"config": registration()["config"], "windows": windows}, manifest)
    total = exact["totals"]["all"]
    assert total["planned_pairs"] == 4 and total["usable_pairs"] == 3
    assert total["metrics"]["days"] == 2  # not three pair-days
    assert total["metrics"]["storms"] == sum(w["metrics"]["storms"] for w in exact["windows"])
    shares = [r["move_ahead_pct"] for w in exact["windows"] for r in w["metrics"]["per_storm"]
              if r["move_ahead_pct"] is not None]
    assert total["metrics"]["median_move_ahead_pct"] == float(np.median(shares))
    assert exact["per_pair_totals"]["GBPUSD"]["usable_windows"] == 0
    assert exact["per_pair_totals"]["GBPUSD"]["metrics"]["false_alarm_episodes_per_day"] is None
    assert exact["windows"][0]["policy"]["excluded_pairs"] == ["EURCHF"]
    # Exercise final serialization/rendering before the one real evaluation.
    report = {"exact": exact, "display": for_display(exact), "provenance": {
        "preregistration_commit": "synthetic", "frozen_config_sha256": "synthetic"}}
    report = json.loads(json.dumps(report, allow_nan=False))
    text = render(report)
    assert "synthetic missing feed" in text
    assert "Frozen external FX holdout results" in text


def test_verification_refuses_changed_and_missing_data(tmp_path, monkeypatch):
    import storm.oos.run as runner
    monkeypatch.setattr(runner, "DATA", tmp_path)
    raw, parquet = tmp_path / "bid.csv", tmp_path / "pair.parquet"
    raw.write_bytes(b"original raw response")
    parquet.write_bytes(b"original parquet")
    manifest = {"windows": [{"pairs": [{"status": "usable", "raw": {
        "bid": {"path": raw.name, "sha256": sha256(raw)}},
        "parquet": {"path": parquet.name, "sha256": sha256(parquet)}}]}]}
    assert len(file_inventory(manifest)) == 2
    raw.write_bytes(b"changed raw response")
    with pytest.raises(ValueError, match="missing/changed"):
        file_inventory(manifest)
    raw.write_bytes(b"original raw response")
    parquet.unlink()
    with pytest.raises(ValueError, match="missing/changed"):
        file_inventory(manifest)


@pytest.mark.parametrize("artifact", ["results.json", "run_started.json"])
def test_primary_run_cannot_overwrite_result_or_restart(tmp_path, monkeypatch, artifact):
    import storm.oos.run as runner
    monkeypatch.setattr(runner, "DOCS", tmp_path)
    monkeypatch.setattr(runner, "RESULTS", tmp_path / "results.json")
    monkeypatch.setattr("sys.argv", ["storm.oos.run"])
    (tmp_path / artifact).write_text("already started")
    with pytest.raises(SystemExit, match="refusing another evaluation"):
        runner.main()


def test_results_markdown_json_agree():
    result = json.loads((DOCS / "results.json").read_text())
    assert (DOCS / "results.md").read_text() == render(result)
    assert result["display"] == for_display(result["exact"])
    assert result["provenance"]["preregistration_sha256"] == sha256(REGISTRATION)
    assert result["provenance"]["frozen_config_sha256"] == registration()["config_sha256"]


def test_report_tampering_and_exact_verification_are_detected():
    result = json.loads((DOCS / "results.json").read_text())
    changed = copy.deepcopy(result)
    changed["exact"]["totals"]["all"]["metrics"]["caught"] += 1
    with pytest.raises(ValueError, match="display values"):
        render(changed)
    changed["display"] = for_display(changed["exact"])
    assert render(changed) != (DOCS / "results.md").read_text()
    assert first_difference(result, changed) is not None
    assert first_difference(result, json.loads(json.dumps(result))) is None
