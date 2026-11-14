"""SQL for the Tiger Data schema. Pure strings: nothing here touches a database.

Every identifier is a constant in this file. User input (symbol, time range) only ever
travels as a bound parameter.
"""
from __future__ import annotations

SPOT_TABLE = "spot_1m"
FORWARD_TABLE = "forward_1m"
STORMS_TABLE = "storms"
CANDLES_VIEW = "candles_5m"
VOL_VIEW = "vol_1h"
HYPERTABLES = (SPOT_TABLE, FORWARD_TABLE)
AGGREGATES = (CANDLES_VIEW, VOL_VIEW)

SPOT_COLUMNS = [
    "ts", "symbol", "settlement_date",
    "open_bid", "open_ask", "open_mid",
    "high_bid", "high_ask", "high_mid",
    "low_bid", "low_ask", "low_mid",
    "close_bid", "close_ask", "close_mid",
    "ret_1m",
]
FORWARD_COLUMNS = ["ts", "symbol", "tenor", "settlement_date", "close_mid", "close_fp", "close_all_in"]
STORM_COLUMNS = [
    "storm_id", "symbol", "onset", "trough", "storm_end", "move_bp", "usd_move_bp",
    "duration_min", "kind", "event", "event_time",
]

CHUNK_INTERVAL = "7 days"
COMPRESS_AFTER = "7 days"
CANDLE_BUCKET_LABEL = "5m"


def drop_statements() -> list[str]:
    """Remove this tool's own objects so --load can be re-run."""
    return [
        f"DROP MATERIALIZED VIEW IF EXISTS {VOL_VIEW} CASCADE",
        f"DROP MATERIALIZED VIEW IF EXISTS {CANDLES_VIEW} CASCADE",
        f"DROP TABLE IF EXISTS {FORWARD_TABLE}",
        f"DROP TABLE IF EXISTS {SPOT_TABLE}",
        f"DROP TABLE IF EXISTS {STORMS_TABLE}",
    ]


def table_statements() -> list[str]:
    return [
        "CREATE EXTENSION IF NOT EXISTS timescaledb",
        f"""CREATE TABLE {SPOT_TABLE} (
            ts timestamptz NOT NULL,
            symbol text NOT NULL,
            settlement_date date,
            open_bid double precision, open_ask double precision, open_mid double precision,
            high_bid double precision, high_ask double precision, high_mid double precision,
            low_bid double precision, low_ask double precision, low_mid double precision,
            close_bid double precision, close_ask double precision, close_mid double precision,
            ret_1m double precision
        )""",
        f"SELECT create_hypertable('{SPOT_TABLE}', 'ts', chunk_time_interval => INTERVAL '{CHUNK_INTERVAL}')",
        f"CREATE INDEX {SPOT_TABLE}_symbol_ts ON {SPOT_TABLE} (symbol, ts DESC)",
        f"""CREATE TABLE {FORWARD_TABLE} (
            ts timestamptz NOT NULL,
            symbol text NOT NULL,
            tenor text NOT NULL,
            settlement_date date,
            close_mid double precision,
            close_fp double precision,
            close_all_in double precision
        )""",
        f"SELECT create_hypertable('{FORWARD_TABLE}', 'ts', chunk_time_interval => INTERVAL '{CHUNK_INTERVAL}')",
        f"CREATE INDEX {FORWARD_TABLE}_symbol_tenor_ts ON {FORWARD_TABLE} (symbol, tenor, ts DESC)",
        f"""CREATE TABLE {STORMS_TABLE} (
            storm_id text PRIMARY KEY,
            symbol text NOT NULL,
            onset timestamptz NOT NULL,
            trough timestamptz,
            storm_end timestamptz,
            move_bp double precision NOT NULL,
            usd_move_bp double precision,
            duration_min integer,
            kind text NOT NULL,
            event text,
            event_time timestamptz
        )""",
    ]


def compression_settings_statements() -> list[str]:
    return [
        f"ALTER TABLE {SPOT_TABLE} SET (timescaledb.compress, "
        "timescaledb.compress_segmentby = 'symbol', timescaledb.compress_orderby = 'ts')",
        f"ALTER TABLE {FORWARD_TABLE} SET (timescaledb.compress, "
        "timescaledb.compress_segmentby = 'symbol, tenor', timescaledb.compress_orderby = 'ts')",
    ]


def compression_policy_statements() -> list[str]:
    return [
        f"SELECT add_compression_policy('{SPOT_TABLE}', INTERVAL '{COMPRESS_AFTER}', if_not_exists => true)",
        f"SELECT add_compression_policy('{FORWARD_TABLE}', INTERVAL '{COMPRESS_AFTER}', if_not_exists => true)",
    ]


def aggregate_statements() -> list[str]:
    """Continuous aggregates. They are created WITH NO DATA and refreshed after the load.

    vol_1h is realised volatility: the root of the summed squared one-minute log
    returns inside the hour, in basis points. Returns across a gap longer than five
    minutes are NULL (see tiger.add_returns), so a weekend is never counted as a move.
    """
    return [
        f"""CREATE MATERIALIZED VIEW {CANDLES_VIEW}
        WITH (timescaledb.continuous, timescaledb.materialized_only = true) AS
        SELECT time_bucket(INTERVAL '5 minutes', ts) AS bucket,
               symbol,
               first(open_mid, ts) AS open,
               max(high_mid) AS high,
               min(low_mid) AS low,
               last(close_mid, ts) AS close,
               count(*) AS bars
        FROM {SPOT_TABLE}
        GROUP BY bucket, symbol
        WITH NO DATA""",
        f"""CREATE MATERIALIZED VIEW {VOL_VIEW}
        WITH (timescaledb.continuous, timescaledb.materialized_only = true) AS
        SELECT time_bucket(INTERVAL '1 hour', ts) AS bucket,
               symbol,
               sqrt(sum(ret_1m * ret_1m)) * 10000.0 AS realised_vol_bp,
               count(ret_1m) AS returns
        FROM {SPOT_TABLE}
        GROUP BY bucket, symbol
        WITH NO DATA""",
    ]


def refresh_statements() -> list[str]:
    return [f"CALL refresh_continuous_aggregate('{name}', NULL, NULL)" for name in AGGREGATES]


def copy_statement(table: str, columns: list[str]) -> str:
    return f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)"


def list_chunks_statement(table: str) -> str:
    return f"SELECT show_chunks('{table}')::text"


def compress_chunk_statement() -> str:
    return "SELECT compress_chunk(%s::regclass, if_not_compressed => true)"


def size_statement(table: str) -> str:
    return f"SELECT hypertable_size('{table}')"


def count_statement(table: str) -> str:
    return f"SELECT count(*) FROM {table}"


# --- API queries -----------------------------------------------------------------

CANDLES_QUERY = f"""
SELECT extract(epoch FROM bucket)::bigint AS t, open, high, low, close
FROM {CANDLES_VIEW}
WHERE symbol = %s AND bucket >= %s AND bucket < %s
ORDER BY bucket
"""

STORMS_QUERY = f"""
SELECT storm_id, symbol, onset, move_bp, kind, event
FROM {STORMS_TABLE}
ORDER BY onset, storm_id
"""

COMPRESSION_STATS_QUERY = """
SELECT coalesce(sum(before_compression_total_bytes), 0)::bigint,
       coalesce(sum(after_compression_total_bytes), 0)::bigint
FROM (
    SELECT * FROM hypertable_compression_stats('spot_1m')
    UNION ALL
    SELECT * FROM hypertable_compression_stats('forward_1m')
) s
"""

AGGREGATES_QUERY = (
    "SELECT view_name FROM timescaledb_information.continuous_aggregates "
    "WHERE view_schema = 'public' ORDER BY view_name"
)

TABLES_EXIST_QUERY = (
    f"SELECT to_regclass('{SPOT_TABLE}') IS NOT NULL AND to_regclass('{FORWARD_TABLE}') IS NOT NULL"
)
