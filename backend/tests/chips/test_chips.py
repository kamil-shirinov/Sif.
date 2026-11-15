"""Offline protocol, boundary, replay and report consistency checks."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd

from storm import equity
from storm.backtest import code_fingerprint
from storm.chips.acquire import requests
from storm.chips.evaluate import bars_from_raw, labels
from storm.chips.protocol import DOCS, check_frozen, registration
from storm.chips.replay import build
from storm.detector import risk_frame
from storm.features import bar_features
from storm.validate import validate_bundle


def test_registration_is_immutable_and_core_is_still_frozen():
    spec = check_frozen()
    assert len(spec["tickers"]) == 14
    assert spec["in_sample"] == ["NVDA"]
    assert spec["config"]["storm_minutes"] == 2
    assert spec["config"]["w_comove"] == 0


def test_acquisition_ranges_cover_all_registered_dates_without_overlap():
    ranges = requests(registration())
    assert ranges[0][1] == pd.Timestamp("2026-11-16", tz="America/New_York")
    assert ranges[-1][0] == pd.Timestamp("2026-10-17", tz="America/New_York")
    for i, (lo, hi) in enumerate(ranges):
        assert 0 < (hi.date() - lo.date()).days <= 7
        if i:
            assert hi == ranges[i - 1][0]


def test_full_retention_adapter_preserves_equity_rules_and_old_sessions():
    idx = pd.date_range("2026-10-20 09:00", periods=800, freq="min", tz="UTC")
    rng = np.random.default_rng(82)
    price = 100 * np.exp(rng.normal(0, .0001, len(idx)).cumsum())
    raw = pd.DataFrame({"timestamp": idx, "open": price, "high": price,
                        "low": price, "close": price, "volume": 1})
    raw.loc[760, ["close", "high"]] *= 1.1
    bars = bars_from_raw(raw, "AMD")
    assert len(bars) == len(raw)
    assert bars.session.eq(20261020).all()
    assert bars.bad_print.sum() == 1
    feat = bar_features(bars).assign(comove=0)
    risk = risk_frame(feat, registration()["config"])
    assert risk.loc[idx[760], "risk"] == 1  # own minute sees the spike
    assert pd.isna(feat.loc[idx[761], "ret_bp"])  # removing the print leaves a two-minute hole
    assert bars_from_raw(raw.assign(timestamp=idx + pd.Timedelta(days=22)), "AMD").session.eq(20261111).all()
    # Within the original demonstration dates, the adapter is bit-for-bit equivalent.
    shifted = raw.assign(timestamp=idx + pd.Timedelta(days=22))
    pd.testing.assert_frame_equal(bars_from_raw(shifted, "AMD"), equity.bars_from_raw(shifted, "AMD"))


def test_labels_cannot_bridge_sessions_or_promote_a_flagged_spike():
    idx = pd.date_range("2026-11-11 10:00", periods=50, freq="min", tz="UTC")
    feat = pd.DataFrame({"mid": [100.] * 25 + [110.] * 25, "sd_24h": 1.,
                         "session": [1] * 25 + [2] * 25, "bad_print": 0}, index=idx)
    assert labels({"ARM": feat}).empty
    feat["session"], feat["mid"] = 1, 100.
    feat.loc[idx[30], ["mid", "bad_print"]] = [120., 1]
    assert labels({"ARM": feat}).empty
    feat["bad_print"] = 0
    assert len(labels({"ARM": feat})) == 1  # same move is a label when it is real


def test_replay_adapter_does_not_mutate_shared_builder_or_freeze_upward_moves():
    idx = pd.date_range("2026-11-11 10:00", periods=400, freq="min", tz="UTC")
    prices = np.full(len(idx), 100.)
    prices[200:216] = np.linspace(100, 110, 16)
    prices[216:] = 110
    bars = pd.DataFrame({"open": prices, "high": prices, "low": prices, "mid": prices,
                         "session": 20261111, "bad_print": 0}, index=idx)
    feat = bars.assign(sd_24h=1., vol_ratio=1., jump=0, comove=0)
    run = equity.EquityRun({"SMCI": bars}, {"SMCI": feat}, registration()["config"])
    storm = SimpleNamespace(pair="SMCI", storm_id="smci-synthetic-test", onset_utc=idx[200],
                            trough_utc=idx[215], end_utc=idx[215], onset_mid=100., trough_mid=110.,
                            first_onset_utc=idx[200], first_onset_mid=100., move_bp=1000., duration_min=15)
    before = code_fingerprint()
    original_book = dict(equity.BOOK)
    bundle, _ = build(run, storm)
    assert validate_bundle(bundle) == []
    assert bundle["symbol"] == "SMCI"
    assert bundle["storm"]["move_bp"] == 1000
    assert bundle["ships"]["prepared"]["cut_i"] is None  # long book gets a fair wind
    assert bundle["series"]["prepared_equity"][-1] > 1_000_000
    assert equity.BOOK == original_book
    assert equity.SHIP_SYMBOL == "NVDA"
    assert code_fingerprint() == before


def test_checked_in_results_preserve_every_ticker_and_recompute_pool_totals():
    result = json.loads((DOCS / "results.json").read_text())
    assert list(result["per_ticker"]) == registration()["tickers"]
    for group, names in {"new_tickers": [t for t in result["per_ticker"] if t != "NVDA"],
                         "nvda_in_sample": ["NVDA"],
                         "all_descriptive": list(result["per_ticker"])}.items():
        pool = result["pooled"][group]
        for key in ("storms", "alarmed", "caught", "false_alarms", "storm_alarms", "storm_state_minutes"):
            assert pool[key] == sum(result["per_ticker"][t][key] for t in names)
        dates = set().union(*(set(result["per_ticker"][t]["trading_dates"]) for t in names))
        assert pool["trading_days"] == len(dates)
        assert pool["false_alarms_per_trading_day"] == pool["false_alarms"] / len(dates)
    expected = sorted([s for s in result["storms"] if s["pair"] != "NVDA"],
                      key=lambda s: (-abs(s["move_bp"]), s["onset_utc"], s["pair"]))[:3]
    assert result["replay_selection"] == expected
    assert len(result["storms"]) == sum(r["storms"] for r in result["per_ticker"].values())
    assert all(s["miss"] == (not s["caught"]) for s in result["storms"])


def test_ai_rows_use_identical_fact_fingerprints_and_private_inspection():
    default_path, private_path = DOCS / "ai_default.json", DOCS / "ai_private.json"
    if not default_path.exists() or not private_path.exists():
        import pytest
        pytest.skip("Live crew artefacts not yet written")
    default, private = (json.loads(p.read_text()) for p in (default_path, private_path))
    facts = lambda row: {d["storm_id"]: d["facts_sha256"] for d in row["details"]}
    assert facts(default) == facts(private)
    assert private["private_mode"] is True
    assert private["inspector_models"] == [private["writer_model"]]


def test_results_markdown_is_exactly_rendered_from_json():
    from storm.chips.report import render

    result = json.loads((DOCS / "results.json").read_text())
    assert (DOCS / "results.md").read_text() == render(result)


def test_tiger_counts_account_for_every_raw_bar_and_modal_is_stopped():
    result = json.loads((DOCS / "results.json").read_text())
    tiger = result["tiger"]
    acquired = {t: a["rows"] for t, a in result["acquisition"]["tickers"].items()}
    assert tiger["loaded_rows"] == acquired
    assert tiger["verified_snapshot_rows"] == sum(acquired.values())
    assert tiger["compressed_chunks"] == tiger["total_chunks"]
    assert tiger["compression_ratio"] == tiger["bytes_before_compression"] / tiger["bytes_after_compression"]
    assert result["modal_runtime"]["stop_exit_code"] == 0
    assert result["modal_runtime"]["observed_running_tasks"] == 0
    assert result["modal_runtime"]["runtime_cost_upper_estimate_usd"] < registration()["budgets_usd"]["modal"]
