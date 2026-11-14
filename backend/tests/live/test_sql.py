import numpy as np
import pandas as pd
import pytest

from storm.live import sql, tiger


def test_candles_query_is_parameterised_and_reads_the_aggregate():
    q = sql.CANDLES_QUERY
    assert "FROM candles_5m" in q
    assert q.count("%s") == 3
    assert "symbol = %s" in q and "bucket >= %s" in q and "bucket < %s" in q


def test_copy_statement_names_columns_in_order():
    stmt = sql.copy_statement("spot_1m", ["ts", "symbol"])
    assert stmt == "COPY spot_1m (ts, symbol) FROM STDIN WITH (FORMAT csv)"


def test_drop_statements_touch_only_this_tools_objects():
    dropped = " ".join(sql.drop_statements())
    for name in ("spot_1m", "forward_1m", "storms", "candles_5m", "vol_1h"):
        assert name in dropped
    assert dropped.count("DROP") == 5 and "DATABASE" not in dropped and "SCHEMA" not in dropped


def test_continuous_aggregates_per_the_brief():
    candles, vol = sql.aggregate_statements()
    assert "timescaledb.continuous" in candles
    assert "first(open_mid, ts)" in candles and "max(high_mid)" in candles
    assert "min(low_mid)" in candles and "last(close_mid, ts)" in candles
    assert "GROUP BY bucket, symbol" in candles
    assert "sqrt(sum(ret_1m * ret_1m))" in vol and "INTERVAL '1 hour'" in vol


def test_hypertables_compress_by_series_and_have_policies():
    settings = " ".join(sql.compression_settings_statements())
    assert "compress_segmentby = 'symbol'" in settings and "compress_segmentby = 'symbol, tenor'" in settings
    policies = sql.compression_policy_statements()
    assert len(policies) == 2 and all("add_compression_policy" in p for p in policies)
    assert [s.split("(")[0] for s in sql.refresh_statements()] == ["CALL refresh_continuous_aggregate"] * 2


def test_schema_declares_every_column_the_loader_writes():
    ddl = " ".join(sql.table_statements())
    for col in sql.SPOT_COLUMNS + sql.FORWARD_COLUMNS + sql.STORM_COLUMNS:
        assert col in ddl
    assert "create_hypertable('spot_1m', 'ts'" in ddl and "create_hypertable('forward_1m', 'ts'" in ddl


# --- frame builders, on a tiny synthetic processed folder ---------------------

def _write_processed(tmp_path):
    ts = pd.to_datetime(["2026-07-03 20:58", "2026-07-03 20:59", "2026-07-05 19:01", "2026-07-05 19:02"], utc=True)
    spot = pd.DataFrame({"timestamp": ts, "settlement_date": pd.Timestamp("2026-07-07")})
    for side in ("bid", "ask", "mid"):
        for leg in ("open", "high", "low", "close"):
            spot[f"{leg}_{side}"] = [1.0, 1.1, 1.2, 1.3]
    spot.to_parquet(tmp_path / "EURUSD_SPOT.parquet")
    fwd = pd.DataFrame({"timestamp": ts, "settlement_date": pd.Timestamp("2026-08-07"),
                        "close_mid": [1.0, 1.1, 1.2, 1.3], "close_mid_fp": 0.01, "close_mid_all_in": [1.01, 1.11, 1.21, 1.31]})
    fwd.to_parquet(tmp_path / "EURUSD_1M.parquet")
    pd.DataFrame({
        "storm_id": ["eurusd-x"], "pair": ["EURUSD"], "onset_utc": ["2026-07-02 12:30"],
        "trough_utc": ["2026-07-02 12:45"], "end_utc": ["2026-07-02 12:45"],
        "move_bp": [63.0], "usd_move_bp": [-62.0], "duration_min": [15], "kind": ["unscheduled"],
        "event": [np.nan], "event_utc": [np.nan],
    }).to_csv(tmp_path / "storms.csv", index=False)
    return tmp_path


def test_returns_are_log_changes_and_null_across_gaps(tmp_path):
    frame = tiger.spot_frame("EURUSD", _write_processed(tmp_path))
    ret = frame["ret_1m"]
    assert np.isnan(ret.iloc[0])                       # nothing before the first bar
    assert ret.iloc[1] == pytest.approx(np.log(1.1 / 1.0))
    assert np.isnan(ret.iloc[2])                       # weekend gap is not a move
    assert ret.iloc[3] == pytest.approx(np.log(1.3 / 1.2))


def test_frames_match_table_column_order(tmp_path):
    processed = _write_processed(tmp_path)
    assert list(tiger.spot_frame("EURUSD", processed).columns) == sql.SPOT_COLUMNS
    fwd = tiger.forward_frame("EURUSD", "1M", processed)
    assert list(fwd.columns) == sql.FORWARD_COLUMNS
    assert set(fwd["tenor"]) == {"1M"} and fwd["close_fp"].eq(0.01).all()
    storms = tiger.storms_frame(processed)
    assert list(storms.columns) == sql.STORM_COLUMNS
    assert storms["onset"].iloc[0] == pd.Timestamp("2026-07-02 12:30", tz="UTC")


class FakeCopy:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data):
        self.sink.append(data.decode())


class FakeCursor:
    def __init__(self):
        self.statements, self.chunks = [], []

    def copy(self, statement):
        self.statements.append(statement)
        return FakeCopy(self.chunks)


def test_copy_frame_batches_and_writes_nulls_as_empty_fields(tmp_path):
    frame = tiger.spot_frame("EURUSD", _write_processed(tmp_path))
    cur = FakeCursor()
    assert tiger.copy_frame(cur, "spot_1m", frame, batch=3) == 4
    assert len(cur.chunks) == 2 and cur.statements[0] == sql.copy_statement("spot_1m", sql.SPOT_COLUMNS)
    first_row = cur.chunks[0].splitlines()[0]
    assert first_row.startswith("2026-07-03 20:58:00+0000,EURUSD,2026-07-07,")
    assert first_row.endswith(",")                     # NULL return on the first bar
    assert len(first_row.split(",")) == len(sql.SPOT_COLUMNS)


def test_missing_processed_data_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="storm.ingest"):
        tiger.load(processed=tmp_path)
