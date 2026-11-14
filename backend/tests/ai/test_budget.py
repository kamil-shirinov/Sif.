from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import sqlite3

import pytest

from storm.ai import budget
from storm.ai.prices import cost_usd, price_for_model


def test_warn_at_75_and_refuse_at_90(caps, capsys):
    call = budget.reserve("meta", "unknown", 250_000, 0, "threshold-test")
    assert "Warning: meta" in capsys.readouterr().err
    assert budget.spent("meta") == pytest.approx(.75)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve("meta", "unknown", 50_000, 0, "threshold-test")
    assert budget.spent("meta") == pytest.approx(.75)
    assert budget.settle(call, input_tokens=1, output_tokens=1) == pytest.approx(.000018)


def test_conservative_pricing_and_aliases():
    assert price_for_model("unknown/model-id") == (3, 15)
    assert price_for_model("accounts/fireworks/models/deepseek-v4.1-flash") == (.30, 1.20)
    assert price_for_model("muse-spark-1.3") == (1.25, 4.25)
    assert price_for_model("muse-ember-1.0") == (.10, .50)
    assert price_for_model("Kimi K3.1 Pro") == (2, 10)
    assert price_for_model("MiniMax M3.1 Flash") == (.15, .60)
    assert price_for_model("deepseek-v4.1-flash-unmapped") == (3, 15)
    assert cost_usd("muse-spark-1.1", 1_000_000, 1_000_000) == 5.50


def test_missing_or_invalid_caps_fail_closed(tmp_path):
    with pytest.raises(budget.BudgetError):
        budget.reserve("meta", "unknown", 1, 1, "test")
    directory = tmp_path / ".stormscore"
    directory.mkdir()
    (directory / "caps.json").write_text('{"meta":{"start_usd":NaN,"warn_at":0.75,"stop_at":0.9}}')
    with pytest.raises(budget.BudgetError):
        budget.reserve("meta", "unknown", 1, 1, "test")


def test_uncertain_attempt_keeps_reservation(caps):
    call = budget.reserve("meta", "unknown", 10, 20, "test")
    budget.failed(call)
    assert budget.spent("meta") == cost_usd("unknown", 10, 20)
    rejected = budget.reserve("meta", "unknown", 10, 20, "test")
    budget.failed(rejected, definitely_unbilled=True)
    assert budget.spent("meta") == cost_usd("unknown", 10, 20)
    with pytest.raises(budget.BudgetError):
        budget.settle(call, input_tokens=1, output_tokens=1)


def _parallel_reserve(_):
    try:
        # Each process tries to hold $0.30. Only two fit below $0.90.
        budget.reserve("meta", "unknown", 0, 20_000, "parallel-test")
        return True
    except budget.BudgetExceeded:
        return False


def test_parallel_processes_share_atomic_reservations(caps):
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(_parallel_reserve, range(8)))
    assert sum(results) == 2
    assert budget.spent("meta") == pytest.approx(.6)
    with sqlite3.connect(caps.parent / "ledger.sqlite") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
