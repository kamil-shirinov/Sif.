from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import sqlite3
from unittest.mock import patch

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


def _budget_worker_start(barrier):
    global _reservation_barrier
    _reservation_barrier = barrier


def _parallel_reserve(test_home):
    # Spawned processes do not inherit pytest monkeypatches. Use the explicit
    # fixture path rather than depending on process environment or import order.
    with patch.object(Path, "home", return_value=Path(test_home)):
        _reservation_barrier.wait(timeout=30)
        try:
            # Each process tries to hold $0.30. Only two fit below $0.90.
            budget.reserve("meta", "unknown", 0, 20_000, "parallel-test")
            return True
        except budget.BudgetExceeded:
            return False


def test_parallel_processes_share_atomic_reservations(caps):
    # Exercise reservation contention separately from WAL/schema first-open
    # setup (covered below), and release four real processes together per wave.
    assert budget.spent("meta") == 0
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=4, mp_context=context,
                             initializer=_budget_worker_start, initargs=(context.Barrier(4),)) as pool:
        results = list(pool.map(_parallel_reserve, [str(caps.parent.parent)] * 8))
    assert sum(results) == 2
    assert budget.spent("meta") == pytest.approx(.6)
    with sqlite3.connect(caps.parent / "ledger.sqlite") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 2


def test_every_ledger_connection_has_busy_timeout(caps, monkeypatch):
    connect = sqlite3.connect
    timeouts = []

    def track(*args, **kwargs):
        db = connect(*args, **kwargs)
        timeouts.append(db.execute('PRAGMA busy_timeout').fetchone()[0])
        return db

    monkeypatch.setattr(budget.sqlite3, 'connect', track)
    call = budget.reserve('meta', 'unknown', 10, 20, 'timeout-test')
    budget.settle(call, input_tokens=1, output_tokens=1)
    call = budget.reserve('meta', 'unknown', 10, 20, 'timeout-test')
    budget.failed(call, definitely_unbilled=True)
    budget.spent('meta')
    assert len(timeouts) == 5
    assert all(timeout >= 5000 for timeout in timeouts)


def test_reservation_waits_for_other_connection_to_release_lock(caps):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    import threading

    budget.spent('meta')  # Initialize the ledger, then hold a competing write lock.
    started = threading.Event()

    def reserve():
        started.set()
        return budget.reserve('meta', 'unknown', 0, 20_000, 'contended-test')

    with sqlite3.connect(caps.parent / 'ledger.sqlite') as lock:
        lock.execute('BEGIN IMMEDIATE')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reserve)
            try:
                assert started.wait(timeout=5)
                with pytest.raises(TimeoutError):
                    future.result(timeout=.1)
            finally:
                lock.rollback()
            assert future.result(timeout=5)
    assert budget.spent('meta') == pytest.approx(.3)


def test_concurrent_wal_startup_busy_is_retried(caps, monkeypatch):
    connect = sqlite3.connect
    failures, sleeps = [], []

    class StartupRace(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == 'PRAGMA journal_mode=WAL' and not failures:
                failures.append(sql)
                error = sqlite3.OperationalError('database is locked')
                raise error
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(budget.sqlite3, 'connect',
                        lambda *args, **kwargs: connect(*args, factory=StartupRace, **kwargs))
    monkeypatch.setattr(budget.time, 'sleep', sleeps.append)
    assert budget.reserve('meta', 'unknown', 0, 20_000, 'wal-race-test')
    assert budget.spent('meta') == pytest.approx(.3)
    assert len(failures) == 1 and sleeps == [.05]


@pytest.mark.parametrize("model,price", [
    ("kimi-k3p1-pro", (2.00, 10.00)),
    ("deepseek-v4p1-flash", (.30, 1.20)),
    ("minimax-m3p1-flash", (.15, .60)),
    ("ember-1", (3.00, 15.00)),
])
def test_full_fireworks_ids_use_real_prices(caps, monkeypatch, model, price):
    from storm.ai import prices

    # Ember's real price equals today's fallback; distinguish mapped pricing.
    monkeypatch.setattr(prices, "CONSERVATIVE_PRICE", (99, 99))
    full_id = f"accounts/fireworks/models/{model}"
    assert price_for_model(full_id) == price
    assert price_for_model(model) == price
    assert price_for_model(full_id + "-unknown-version") == (99, 99)
    assert cost_usd(full_id, 1000, 2000) == pytest.approx((price[0] + 2 * price[1]) / 1000)
    call = budget.reserve("fireworks", full_id, 1000, 2000, "alias-test")
    charged = budget.settle(call, input_tokens=500, output_tokens=1000)
    assert charged == pytest.approx((.5 * price[0] + price[1]) / 1000)
    assert budget.spent("fireworks") == charged


@pytest.mark.parametrize("message", ["database is locked", "database table is locked"])
def test_python310_lock_detection_without_sqlite_constants(monkeypatch, message):
    monkeypatch.delattr(sqlite3, "SQLITE_BUSY", raising=False)
    monkeypatch.delattr(sqlite3, "SQLITE_LOCKED", raising=False)
    assert budget._is_locked(sqlite3.OperationalError(message))
    assert not budget._is_locked(sqlite3.OperationalError("no such table: ai_calls"))
    assert not hasattr(sqlite3, "SQLITE_BUSY")


@pytest.mark.parametrize("code,locked", [(5, True), (6, True), (5 | (2 << 8), True), (1, False)])
def test_sqlite_primary_and_extended_lock_codes(code, locked):
    error = sqlite3.OperationalError("message supplied by SQLite")
    error.sqlite_errorcode = code
    assert budget._is_locked(error) is locked
